use std::{
    collections::HashMap,
    sync::{Arc, Mutex},
};

use chrono::{Local, NaiveDate};
use teloxide::prelude::*;

use crate::{
    config::Config,
    core::{
        Effort, Estimate, InterviewSession, Priority, Question, Uncertainty, build_day_plan,
        question_axis, score,
    },
    llm::LlmService,
    store::Store,
    vault,
};

enum Flow {
    Category {
        title: String,
    },
    Deadline {
        title: String,
        category: String,
    },
    Interview {
        title: String,
        category: String,
        deadline: Option<String>,
        session: InterviewSession,
    },
}

struct State {
    store: Store,
    llm: LlmService,
    config: Config,
    flows: HashMap<ChatId, Flow>,
}

pub async fn run(config: Config, llm: LlmService) -> anyhow::Result<()> {
    let bot = Bot::new(config.telegram.token.clone());
    let state = Arc::new(Mutex::new(State {
        store: Store::open(&config.database.path)?,
        llm,
        config,
        flows: HashMap::new(),
    }));
    teloxide::repl(bot, move |bot: Bot, message: Message| {
        let state = Arc::clone(&state);
        async move {
            let text = message.text().unwrap_or_default().trim().to_owned();
            let answer = {
                let mut state = state.lock().expect("telegram state lock");
                process_message(&mut state, message.chat.id, &text)
            };
            bot.send_message(message.chat.id, answer).await?;
            respond(())
        }
    })
    .await;
    Ok(())
}

fn process_message(state: &mut State, chat_id: ChatId, text: &str) -> String {
    if text.starts_with('/') {
        return command(state, chat_id, text);
    }
    let Some(flow) = state.flows.remove(&chat_id) else {
        return "Utilise /add <titre>, /today, /list, /done <id>, /scan, /goals, /info <texte> ou /llm.".to_owned();
    };
    match flow {
        Flow::Category { title } => {
            let category = state
                .store
                .categories()
                .ok()
                .and_then(|values| {
                    values
                        .into_iter()
                        .find(|value| {
                            value.code.eq_ignore_ascii_case(text)
                                || value.label.eq_ignore_ascii_case(text)
                        })
                        .map(|value| value.code)
                })
                .or_else(|| state.store.create_category(text).ok())
                .unwrap_or_else(|| "travail".to_owned());
            state
                .flows
                .insert(chat_id, Flow::Deadline { title, category });
            "Cette tâche a-t-elle une date limite ? Réponds non ou AAAA-MM-JJ.".to_owned()
        }
        Flow::Deadline { title, category } => {
            let deadline = if ["non", "no", "aucune", "none"]
                .iter()
                .any(|value| text.eq_ignore_ascii_case(value))
            {
                None
            } else if NaiveDate::parse_from_str(text, "%Y-%m-%d").is_ok() {
                Some(text.to_owned())
            } else {
                state
                    .flows
                    .insert(chat_id, Flow::Deadline { title, category });
                return "Date invalide. Réponds non ou utilise le format AAAA-MM-JJ.".to_owned();
            };
            let mut session = InterviewSession {
                deadline_days: deadline
                    .as_deref()
                    .and_then(|value| NaiveDate::parse_from_str(value, "%Y-%m-%d").ok())
                    .map(|value| (value - Local::now().date_naive()).num_days()),
                ..InterviewSession::default()
            };
            let question = session
                .next_question()
                .expect("new interview has a question");
            state.flows.insert(
                chat_id,
                Flow::Interview {
                    title,
                    category,
                    deadline,
                    session,
                },
            );
            render_question(question)
        }
        Flow::Interview {
            title,
            category,
            deadline,
            mut session,
        } => {
            let Some(question) = session.next_question() else {
                return finish_interview(state, title, category, deadline, session);
            };
            let options = options(question);
            let parsed = text
                .parse::<usize>()
                .ok()
                .filter(|value| *value >= 1 && *value <= options.len())
                .map(|value| options[value - 1].1.clone());
            let value = if let Some(value) = parsed {
                value
            } else if state.llm.available() {
                if let Some(axis) = question_axis(question) {
                    match state
                        .llm
                        .interpret_axis(axis, question_text(question), text)
                    {
                        Ok(value) => value.value.to_string(),
                        Err(error) => {
                            state.flows.insert(
                                chat_id,
                                Flow::Interview {
                                    title,
                                    category,
                                    deadline,
                                    session,
                                },
                            );
                            return format!(
                                "LLM indisponible ({error}). Réponds avec le numéro d'une option.\n{}",
                                render_question(question)
                            );
                        }
                    }
                } else {
                    match state
                        .llm
                        .interpret_option(question_text(question), &options, text)
                    {
                        Ok(value) => value.value,
                        Err(error) => {
                            state.flows.insert(
                                chat_id,
                                Flow::Interview {
                                    title,
                                    category,
                                    deadline,
                                    session,
                                },
                            );
                            return format!(
                                "LLM indisponible ({error}). Réponds avec le numéro d'une option.\n{}",
                                render_question(question)
                            );
                        }
                    }
                }
            } else {
                state.flows.insert(
                    chat_id,
                    Flow::Interview {
                        title,
                        category,
                        deadline,
                        session,
                    },
                );
                return format!("Réponds par un numéro.\n{}", render_question(question));
            };
            if let Err(error) = apply_answer(&mut session, question, &value) {
                state.flows.insert(
                    chat_id,
                    Flow::Interview {
                        title,
                        category,
                        deadline,
                        session,
                    },
                );
                return format!("Réponse invalide : {error}");
            }
            if let Some(next) = session.next_question() {
                state.flows.insert(
                    chat_id,
                    Flow::Interview {
                        title,
                        category,
                        deadline,
                        session,
                    },
                );
                render_question(next)
            } else {
                finish_interview(state, title, category, deadline, session)
            }
        }
    }
}

fn command(state: &mut State, chat_id: ChatId, text: &str) -> String {
    let (name, argument) = text.split_once(' ').unwrap_or((text, ""));
    match name.split('@').next().unwrap_or(name) {
        "/start" | "/help" => "PRIORIS Rust\n/add <titre>\n/today\n/list\n/done <id>\n/scan\n/goals\n/info <texte>\n/llm".to_owned(),
        "/add" if argument.trim().is_empty() => "Usage : /add <titre>".to_owned(),
        "/add" => {
            state.flows.insert(chat_id, Flow::Category { title: argument.trim().to_owned() });
            let categories = state.store.categories().unwrap_or_default().into_iter().map(|value| value.label).collect::<Vec<_>>().join(", ");
            format!("Choisis une catégorie ou écris-en une nouvelle :\n{categories}")
        }
        "/list" => match state.store.tasks() {
            Ok(tasks) if tasks.is_empty() => "Aucune tâche.".to_owned(),
            Ok(tasks) => tasks.into_iter().map(|task| format!("#{} {} {} ({:.1})", task.id, task.priority.map_or("-", Priority::as_str), task.title, task.global_score.unwrap_or(0.0))).collect::<Vec<_>>().join("\n"),
            Err(error) => error.to_string(),
        },
        "/done" => match argument.trim().parse::<i64>() {
            Ok(id) => match state.store.mark_done(id) { Ok(true) => format!("Tâche #{id} terminée."), Ok(false) => "Tâche introuvable.".to_owned(), Err(error) => error.to_string() },
            Err(_) => "Usage : /done <id>".to_owned(),
        },
        "/today" => {
            let today = Local::now().date_naive();
            match state.store.current_tasks_for_plan(today) {
                Ok(tasks) => {
                    let plan = build_day_plan(&tasks, 480, 3);
                    let _ = state.store.save_plan(&today.to_string(), 480, 3, &plan);
                    vault::render_plan(&plan, &today.to_string(), 3)
                }
                Err(error) => error.to_string(),
            }
        }
        "/scan" => {
            let tasks = vault::find_unprioritized(&state.config.obsidian.vault_path, &state.config.obsidian.prioris_dir);
            format!("{} tâche(s) Obsidian non priorisée(s). Lance la GUI pour l'évaluation interactive avec aperçu d'écriture.", tasks.len())
        }
        "/goals" => match state.store.goals() {
            Ok(goals) if goals.is_empty() => "Aucun objectif actif.".to_owned(),
            Ok(goals) => goals.into_iter().map(|goal| format!("#{} {} ({}/{})", goal.id, goal.title, goal.done_count, goal.task_count)).collect::<Vec<_>>().join("\n"),
            Err(error) => error.to_string(),
        },
        "/llm" => if !state.llm.available() { "LLM désactivé. Le scoring local reste disponible.".to_owned() } else { match state.llm.health_check_with_retries(3) { Ok(ms) => format!("LLM opérationnel ({ms} ms)."), Err(error) => format!("LLM KO après 3 essais : {error}. Voir logs/prioris-llm.log") } },
        "/info" if argument.trim().is_empty() => "Usage : /info <information ou question>".to_owned(),
        "/info" => {
            if !state.llm.available() { return "LLM indisponible. Saisie manuelle : /info #12 CDR=4 car la date est vendredi.".to_owned(); }
            let tasks = state.store.tasks().unwrap_or_default().into_iter().map(|task| (task.id, task.title)).collect::<Vec<_>>();
            match state.llm.analyze_impact(&tasks, argument.trim()) {
                Ok(proposal) if proposal.impacted.is_empty() => format!("{}\nNouvelle tâche proposée : {}\nDate proposée : {}\nUtilise /add pour confirmer.", proposal.explanation, proposal.new_task_title, proposal.suggested_deadline),
                Ok(proposal) => {
                    let mut lines = vec![proposal.direct_answer, proposal.explanation];
                    lines.extend(proposal.impacted.into_iter().map(|task| format!("#{} : {}", task.id, task.impact)));
                    lines.push("Aucune modification automatique : confirme dans la GUI ou ajoute manuellement l'information.".to_owned());
                    lines.join("\n")
                }
                Err(error) => format!("Analyse impossible : {error}"),
            }
        }
        _ => "Commande inconnue. Utilise /help.".to_owned(),
    }
}

fn finish_interview(
    state: &mut State,
    title: String,
    category: String,
    deadline: Option<String>,
    session: InterviewSession,
) -> String {
    let (axes, defaulted) = session.final_axes();
    let estimate = session.estimate.unwrap_or(Estimate::Unknown);
    let result = match score(
        &axes,
        estimate,
        session.deadline_days,
        &session.uncertainties,
        &defaulted,
        if session.full_mode {
            "complet"
        } else {
            "express"
        },
        session.subjective,
    ) {
        Ok(value) => value,
        Err(error) => return error.to_string(),
    };
    let id = match state
        .store
        .create_task(&title, &category, deadline.as_deref(), "telegram", None)
    {
        Ok(value) => value,
        Err(error) => return error.to_string(),
    };
    if let Err(error) = state.store.save_evaluation(
        id,
        &result,
        session.subjective,
        estimate,
        Effort::from_u8(session.effort),
    ) {
        return error.to_string();
    }
    let robustness = if result.robust {
        format!("Quadrant robuste : {}", result.quadrant)
    } else {
        format!(
            "Quadrant sensible : {} · axe pivot {}",
            result.possible_quadrants.join(" / "),
            result.pivot_axis.as_deref().unwrap_or("indéterminé")
        )
    };
    format!(
        "#{} {} · {} · score {:.1}/100\nUrgence {:.1} · Importance {:.1}\n{}",
        id,
        result.priority.as_str(),
        result.quadrant,
        result.global,
        result.urgency,
        result.importance,
        robustness
    )
}

fn render_question(question: Question) -> String {
    let mut lines = vec![question_text(question).to_owned()];
    lines.extend(
        options(question)
            .iter()
            .enumerate()
            .map(|(index, (label, _))| format!("{}. {label}", index + 1)),
    );
    lines.push("Réponds par un numéro ou en texte libre si le LLM fonctionne.".to_owned());
    lines.join("\n")
}

fn question_text(question: Question) -> &'static str {
    match question {
        Question::Subjective => "Instinctivement, tu la classes comment ?",
        Question::Inaction => crate::core::Axis::INA.question_fr(),
        Question::Blockage => crate::core::Axis::BLK.question_fr(),
        Question::DelayCost => crate::core::Axis::CDR.question_fr(),
        Question::Goal => crate::core::Axis::ALN.question_fr(),
        Question::Estimate => "Combien de temps faut-il ?",
        Question::Impact => crate::core::Axis::IMP.question_fr(),
        Question::Horizon => crate::core::Axis::HOR.question_fr(),
        Question::Irreversibility => crate::core::Axis::IRR.question_fr(),
        Question::Effort => "Quel niveau d'effort mental ?",
        Question::Requester => "Qui demande cette tâche ?",
        Question::Visibility => "Quel est son niveau de visibilité ?",
        Question::Pressure => "Quel niveau de pression ressens-tu ?",
    }
}

fn options(question: Question) -> Vec<(String, String)> {
    if let Some(axis) = question_axis(question) {
        return axis
            .labels_fr()
            .iter()
            .enumerate()
            .map(|(index, label)| ((*label).to_owned(), index.to_string()))
            .collect();
    }
    match question {
        Question::Subjective => [Priority::P1, Priority::P2, Priority::P3, Priority::P4]
            .into_iter()
            .map(|value| (value.as_str().to_owned(), value.as_str().to_owned()))
            .collect(),
        Question::Estimate => [
            Estimate::Lt15,
            Estimate::M15_30,
            Estimate::M30_60,
            Estimate::H1_2,
            Estimate::H2_4,
            Estimate::Gt4,
            Estimate::Unknown,
        ]
        .into_iter()
        .map(|value| (value.db_value().to_owned(), value.db_value().to_owned()))
        .collect(),
        Question::Effort => vec![
            ("Faible".into(), "1".into()),
            ("Moyen".into(), "2".into()),
            ("Élevé".into(), "3".into()),
        ],
        Question::Requester => vec![
            ("Moi".into(), "moi".into()),
            ("Collègue".into(), "collegue".into()),
            ("Manager".into(), "manager".into()),
            ("Client".into(), "client".into()),
        ],
        Question::Visibility | Question::Pressure => (0..=3)
            .map(|value| (value.to_string(), value.to_string()))
            .collect(),
        _ => Vec::new(),
    }
}

fn apply_answer(
    session: &mut InterviewSession,
    question: Question,
    value: &str,
) -> Result<(), String> {
    if question_axis(question).is_some() {
        return session.answer_axis(
            question,
            value.parse().map_err(|_| "invalid axis value".to_owned())?,
            Uncertainty::Certain,
        );
    }
    match question {
        Question::Subjective => session.subjective = Some(value.parse()?),
        Question::Estimate => session.estimate = Some(value.parse()?),
        Question::Effort => {
            session.effort = value.parse().map_err(|_| "invalid effort".to_owned())?
        }
        Question::Requester => session.requester = value.to_owned(),
        Question::Visibility => {
            session.visibility = value.parse().map_err(|_| "invalid visibility".to_owned())?
        }
        Question::Pressure => {
            session.pressure = value.parse().map_err(|_| "invalid pressure".to_owned())?
        }
        _ => return Err("unexpected answer".to_owned()),
    }
    session.mark_asked(question);
    Ok(())
}
