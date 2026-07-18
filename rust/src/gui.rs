use std::path::PathBuf;

use chrono::{Local, NaiveDate};
use eframe::egui;

use crate::{
    config::Config,
    core::{
        Effort, Estimate, InterviewSession, Priority, Question, ScoreResult, Uncertainty,
        build_day_plan, question_axis, score,
    },
    llm::{ChallengeCorrection, ImpactProposal, LlmService},
    store::{Category, Store},
    vault::{self, VaultTask},
};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum View {
    Tasks,
    Today,
    Goals,
    Obsidian,
    Info,
    Llm,
    Configuration,
}

struct FinishTask {
    title: String,
    category: String,
    custom_category: String,
    deadline: Option<String>,
    source: String,
    vault_task: Option<VaultTask>,
    session: InterviewSession,
    result: ScoreResult,
}

enum AddAction {
    None,
    Cancel,
    Finish(Box<FinishTask>),
}

struct PendingInterpretation {
    value: String,
    uncertainty: Uncertainty,
    reformulation: String,
}

struct AddFlow {
    title: String,
    category: String,
    custom_category: String,
    has_deadline: bool,
    deadline: String,
    source: String,
    vault_task: Option<VaultTask>,
    metadata_done: bool,
    session: InterviewSession,
    free_answer: String,
    pending_interpretation: Option<PendingInterpretation>,
    challenge_initialized: bool,
    challenge_questions: Vec<String>,
    challenge_index: usize,
    challenge_answer: String,
    pending_correction: Option<ChallengeCorrection>,
    error: String,
}

impl AddFlow {
    fn blank(default_category: String) -> Self {
        Self {
            title: String::new(),
            category: default_category,
            custom_category: String::new(),
            has_deadline: false,
            deadline: Local::now().date_naive().to_string(),
            source: "gui".to_owned(),
            vault_task: None,
            metadata_done: false,
            session: InterviewSession::default(),
            free_answer: String::new(),
            pending_interpretation: None,
            challenge_initialized: false,
            challenge_questions: Vec::new(),
            challenge_index: 0,
            challenge_answer: String::new(),
            pending_correction: None,
            error: String::new(),
        }
    }

    fn from_vault(task: VaultTask, default_category: String) -> Self {
        let mut flow = Self::blank(default_category);
        flow.title = task.title.clone();
        flow.deadline = task.due.clone().unwrap_or_else(|| flow.deadline.clone());
        flow.has_deadline = task.due.is_some();
        flow.source = "obsidian".to_owned();
        flow.vault_task = Some(task);
        flow
    }
}

pub struct PriorisApp {
    config: Config,
    config_draft: Config,
    config_path: PathBuf,
    store: Store,
    llm: LlmService,
    view: View,
    add_flow: Option<AddFlow>,
    status: String,
    energy: u8,
    capacity: u32,
    today_preview: String,
    goal_title: String,
    goal_category: String,
    vault_tasks: Vec<VaultTask>,
    info_text: String,
    impact: Option<ImpactProposal>,
    show_secrets: bool,
}

impl PriorisApp {
    pub fn new(config: Config, config_path: PathBuf, llm: LlmService) -> anyhow::Result<Self> {
        let store = Store::open(&config.database.path)?;
        Ok(Self {
            goal_category: "perso".to_owned(),
            config_draft: config.clone(),
            config,
            config_path,
            store,
            llm,
            view: View::Tasks,
            add_flow: None,
            status: "Prêt".to_owned(),
            energy: 3,
            capacity: 480,
            today_preview: String::new(),
            goal_title: String::new(),
            vault_tasks: Vec::new(),
            info_text: String::new(),
            impact: None,
            show_secrets: false,
        })
    }

    fn finish_task(&mut self, task: FinishTask) {
        let category = if task.custom_category.trim().is_empty() {
            task.category
        } else {
            match self.store.create_category(&task.custom_category) {
                Ok(code) => code,
                Err(error) => {
                    self.status = format!("Catégorie invalide : {error}");
                    return;
                }
            }
        };
        let obsidian_path = task
            .vault_task
            .as_ref()
            .map(|value| value.relative_path.as_str());
        let task_id = match self.store.create_task(
            &task.title,
            &category,
            task.deadline.as_deref(),
            &task.source,
            obsidian_path,
        ) {
            Ok(id) => id,
            Err(error) => {
                self.status = format!("Création impossible : {error}");
                return;
            }
        };
        let estimate = task.session.estimate.unwrap_or(Estimate::Unknown);
        let effort = Effort::from_u8(task.session.effort);
        if let Err(error) = self.store.save_evaluation(
            task_id,
            &task.result,
            task.session.subjective,
            estimate,
            effort,
        ) {
            self.status = format!("Évaluation non enregistrée : {error}");
            return;
        }
        if let Some(vault_task) = task.vault_task
            && let Err(error) = vault::apply_result(
                &self.config.obsidian.vault_path,
                &self.config.obsidian.prioris_dir,
                &vault_task,
                task_id,
                task.result.priority.as_str(),
                &task.result.justification,
            )
        {
            self.status = format!("Tâche #{task_id} créée, écriture Obsidian impossible : {error}");
            return;
        }
        self.status = format!(
            "Tâche #{task_id} créée : {} ({:.1}/100)",
            task.result.priority.as_str(),
            task.result.global,
        );
        self.view = View::Tasks;
    }

    fn navigation(&mut self, ui: &mut egui::Ui) {
        ui.horizontal_wrapped(|ui| {
            if ui.button("＋ Ajouter").clicked() {
                let default = self
                    .store
                    .categories()
                    .ok()
                    .and_then(|values| values.first().cloned())
                    .map_or_else(|| "travail".to_owned(), |value| value.code);
                self.add_flow = Some(AddFlow::blank(default));
            }
            for (view, label) in [
                (View::Tasks, "Liste"),
                (View::Today, "Plan du jour"),
                (View::Goals, "Objectifs"),
                (View::Obsidian, "Obsidian"),
                (View::Info, "Info / question"),
                (View::Llm, "LLM"),
                (View::Configuration, "Configuration"),
            ] {
                if ui.selectable_label(self.view == view, label).clicked() {
                    self.view = view;
                }
            }
            ui.separator();
            let (color, label) = if !self.llm.available() {
                (egui::Color32::GRAY, "LLM désactivé")
            } else if self.llm.last_error().is_some() {
                (egui::Color32::RED, "LLM KO")
            } else {
                (egui::Color32::GREEN, "LLM prêt")
            };
            ui.colored_label(color, "●");
            ui.label(label);
        });
    }

    fn tasks_view(&mut self, ui: &mut egui::Ui) {
        ui.heading("Tâches");
        match self.store.tasks() {
            Ok(tasks) if tasks.is_empty() => {
                ui.label("Aucune tâche.");
            }
            Ok(tasks) => {
                egui::ScrollArea::vertical().show(ui, |ui| {
                    egui::Grid::new("tasks_grid")
                        .striped(true)
                        .min_col_width(80.0)
                        .show(ui, |ui| {
                            ui.strong("Id");
                            ui.strong("Priorité");
                            ui.strong("Tâche");
                            ui.strong("Catégorie");
                            ui.strong("Score");
                            ui.strong("Action");
                            ui.end_row();
                            for task in tasks {
                                ui.label(format!("#{}", task.id));
                                ui.label(task.priority.map_or("-", Priority::as_str));
                                ui.label(&task.title);
                                ui.label(&task.category);
                                ui.label(
                                    task.global_score.map_or_else(
                                        || "-".to_owned(),
                                        |value| format!("{value:.1}"),
                                    ),
                                );
                                if task.status != "faite"
                                    && ui
                                        .small_button("✓")
                                        .on_hover_text("Marquer faite")
                                        .clicked()
                                {
                                    match self.store.mark_done(task.id) {
                                        Ok(true) => {
                                            if !self
                                                .config
                                                .obsidian
                                                .vault_path
                                                .as_os_str()
                                                .is_empty()
                                            {
                                                let _ = vault::check_task(
                                                    &self.config.obsidian.vault_path,
                                                    &self.config.obsidian.prioris_dir,
                                                    task.id,
                                                );
                                            }
                                            self.status = format!("Tâche #{} terminée", task.id);
                                        }
                                        Ok(false) => self.status = "Tâche introuvable".to_owned(),
                                        Err(error) => self.status = error.to_string(),
                                    }
                                }
                                ui.end_row();
                            }
                        });
                });
            }
            Err(error) => {
                ui.colored_label(egui::Color32::RED, error.to_string());
            }
        }
    }

    fn today_view(&mut self, ui: &mut egui::Ui) {
        ui.heading("Plan du jour");
        ui.horizontal(|ui| {
            ui.label("Énergie");
            ui.add(egui::Slider::new(&mut self.energy, 1..=5));
            ui.label("Capacité (min)");
            ui.add(egui::DragValue::new(&mut self.capacity).range(30..=1440));
            if ui.button("Calculer").clicked() {
                let today = Local::now().date_naive();
                match self.store.current_tasks_for_plan(today) {
                    Ok(tasks) => {
                        let plan = build_day_plan(&tasks, self.capacity, self.energy);
                        let content = vault::render_plan(&plan, &today.to_string(), self.energy);
                        self.today_preview = content.clone();
                        match self.store.save_plan(
                            &today.to_string(),
                            self.capacity,
                            self.energy,
                            &plan,
                        ) {
                            Ok(_) => {
                                self.status =
                                    format!("Plan calculé : {} tâche(s)", plan.items.len())
                            }
                            Err(error) => self.status = error.to_string(),
                        }
                    }
                    Err(error) => self.status = error.to_string(),
                }
            }
        });
        if !self.today_preview.is_empty() {
            ui.separator();
            ui.label("Aperçu avant écriture dans Obsidian :");
            ui.add(
                egui::TextEdit::multiline(&mut self.today_preview)
                    .desired_rows(18)
                    .font(egui::TextStyle::Monospace),
            );
            if ui.button("Confirmer l'export Obsidian").clicked() {
                match vault::write_note(
                    &self.config.obsidian.vault_path,
                    "PRIORIS/Plan du jour.md",
                    &self.today_preview,
                ) {
                    Ok(path) => self.status = format!("Écrit : {}", path.display()),
                    Err(error) => self.status = error.to_string(),
                }
            }
        }
    }

    fn goals_view(&mut self, ui: &mut egui::Ui) {
        ui.heading("Objectifs");
        ui.horizontal(|ui| {
            ui.text_edit_singleline(&mut self.goal_title);
            ui.text_edit_singleline(&mut self.goal_category);
            if ui.button("Ajouter").clicked() && !self.goal_title.trim().is_empty() {
                match self
                    .store
                    .create_goal(self.goal_title.trim(), self.goal_category.trim())
                {
                    Ok(id) => {
                        self.status = format!("Objectif #{id} créé");
                        self.goal_title.clear();
                    }
                    Err(error) => self.status = error.to_string(),
                }
            }
        });
        match self.store.goals() {
            Ok(goals) => {
                for goal in goals {
                    ui.label(format!(
                        "#{} {} · {} · {}/{}",
                        goal.id, goal.title, goal.category, goal.done_count, goal.task_count
                    ));
                }
            }
            Err(error) => {
                ui.colored_label(egui::Color32::RED, error.to_string());
            }
        }
    }

    fn obsidian_view(&mut self, ui: &mut egui::Ui) {
        ui.heading("Obsidian");
        ui.label(format!(
            "Vault : {}",
            self.config.obsidian.vault_path.display()
        ));
        if ui.button("Scanner").clicked() {
            self.vault_tasks = vault::find_unprioritized(
                &self.config.obsidian.vault_path,
                &self.config.obsidian.prioris_dir,
            );
            self.status = format!("{} tâche(s) non priorisée(s)", self.vault_tasks.len());
        }
        if let Some(task) = self.vault_tasks.first().cloned() {
            ui.separator();
            ui.label(format!(
                "Prochaine : {} ({})",
                task.title, task.relative_path
            ));
            if ui.button("Évaluer cette tâche").clicked() {
                let default = self
                    .store
                    .categories()
                    .ok()
                    .and_then(|values| values.first().cloned())
                    .map_or_else(|| "travail".to_owned(), |value| value.code);
                self.add_flow = Some(AddFlow::from_vault(task, default));
                self.vault_tasks.remove(0);
            }
        }
    }

    fn info_view(&mut self, ui: &mut egui::Ui) {
        ui.heading("Information ou question");
        ui.add(
            egui::TextEdit::multiline(&mut self.info_text)
                .desired_rows(5)
                .hint_text("Exemple : la livraison doit être terminée vendredi."),
        );
        if ui.button("Analyser").clicked() {
            if !self.llm.available() {
                self.status =
                    "LLM indisponible. Exemple manuel : #12 CDR=4 car la date est vendredi."
                        .to_owned();
            } else {
                let tasks = self
                    .store
                    .tasks()
                    .unwrap_or_default()
                    .into_iter()
                    .map(|task| (task.id, task.title))
                    .collect::<Vec<_>>();
                match self.llm.analyze_impact(&tasks, &self.info_text) {
                    Ok(proposal) => self.impact = Some(proposal),
                    Err(error) => self.status = format!("Analyse LLM impossible : {error}"),
                }
            }
        }
        if let Some(proposal) = &self.impact {
            ui.separator();
            if !proposal.direct_answer.is_empty() {
                ui.label(format!("Réponse : {}", proposal.direct_answer));
            }
            ui.label(&proposal.explanation);
            for task in &proposal.impacted {
                ui.label(format!("#{} : {}", task.id, task.impact));
            }
            if proposal.impacted.is_empty() {
                ui.label(format!(
                    "Nouvelle tâche proposée : {}",
                    proposal.new_task_title
                ));
                if ui.button("Créer cette tâche").clicked() {
                    let default = self
                        .store
                        .categories()
                        .ok()
                        .and_then(|values| values.first().cloned())
                        .map_or_else(|| "travail".to_owned(), |value| value.code);
                    let mut flow = AddFlow::blank(default);
                    flow.title = proposal.new_task_title.clone();
                    if !proposal.suggested_deadline.is_empty() {
                        flow.has_deadline = true;
                        flow.deadline = proposal.suggested_deadline.clone();
                    }
                    self.add_flow = Some(flow);
                }
            } else if ui
                .button("Ajouter l'information aux tâches proposées")
                .clicked()
            {
                for task in &proposal.impacted {
                    let _ = self
                        .store
                        .add_task_note(task.id, "info_llm", &self.info_text);
                }
                self.status =
                    "Informations ajoutées. Aucun score n'a été modifié sans réévaluation."
                        .to_owned();
            }
        }
    }

    fn llm_view(&mut self, ui: &mut egui::Ui) {
        ui.heading("Diagnostic LLM");
        ui.label(format!("Provider : {}", self.llm.provider()));
        ui.label(format!("Activé : {}", self.llm.available()));
        if ui.button("Tester avec 3 tentatives").clicked() {
            match self.llm.health_check_with_retries(3) {
                Ok(ms) => self.status = format!("LLM opérationnel ({ms} ms)"),
                Err(error) => self.status = format!("LLM KO : {error}. Voir logs/prioris-llm.log"),
            }
        }
        if let Some(error) = self.llm.last_error() {
            ui.colored_label(egui::Color32::RED, error);
        }
    }

    fn configuration_view(&mut self, ui: &mut egui::Ui) {
        ui.heading("Configuration");
        ui.label(self.config_path.display().to_string());
        ui.horizontal(|ui| {
            if ui.button("Recharger").clicked() {
                match Config::load(&self.config_path) {
                    Ok(config) => {
                        self.config_draft = config;
                        self.status = "Configuration relue depuis le fichier.".to_owned();
                    }
                    Err(error) => self.status = format!("Rechargement impossible : {error}"),
                }
            }
            ui.checkbox(&mut self.show_secrets, "Afficher les secrets");
        });

        egui::ScrollArea::vertical().show(ui, |ui| {
            ui.separator();
            ui.strong("Telegram");
            egui::Grid::new("configuration_telegram")
                .num_columns(2)
                .spacing([16.0, 8.0])
                .show(ui, |ui| {
                    ui.label("Token");
                    ui.add(
                        egui::TextEdit::singleline(&mut self.config_draft.telegram.token)
                            .password(!self.show_secrets)
                            .desired_width(460.0),
                    );
                    ui.end_row();
                });

            ui.separator();
            ui.strong("Stockage et interface");
            egui::Grid::new("configuration_storage")
                .num_columns(2)
                .spacing([16.0, 8.0])
                .show(ui, |ui| {
                    ui.label("Base SQLite");
                    path_editor(ui, &mut self.config_draft.database.path);
                    ui.end_row();
                    ui.label("Langue");
                    ui.text_edit_singleline(&mut self.config_draft.ui.language);
                    ui.end_row();
                });

            ui.separator();
            ui.strong("Obsidian");
            egui::Grid::new("configuration_obsidian")
                .num_columns(2)
                .spacing([16.0, 8.0])
                .show(ui, |ui| {
                    ui.label("Vault");
                    path_editor(ui, &mut self.config_draft.obsidian.vault_path);
                    ui.end_row();
                    ui.label("Dossier PRIORIS");
                    ui.text_edit_singleline(&mut self.config_draft.obsidian.prioris_dir);
                    ui.end_row();
                });

            ui.separator();
            ui.strong("LLM");
            ui.checkbox(&mut self.config_draft.llm.enabled, "Activé");
            egui::Grid::new("configuration_llm")
                .num_columns(2)
                .spacing([16.0, 8.0])
                .show(ui, |ui| {
                    ui.label("Provider");
                    egui::ComboBox::from_id_salt("configuration_llm_provider")
                        .selected_text(&self.config_draft.llm.provider)
                        .show_ui(ui, |ui| {
                            for provider in [
                                "prioris",
                                "local_gguf",
                                "ollama",
                                "lmstudio",
                                "openai",
                                "anthropic",
                                "copilot",
                                "custom",
                            ] {
                                ui.selectable_value(
                                    &mut self.config_draft.llm.provider,
                                    provider.to_owned(),
                                    provider,
                                );
                            }
                        });
                    ui.end_row();
                    ui.label("Modèle");
                    path_editor(ui, &mut self.config_draft.llm.model);
                    ui.end_row();
                    ui.label("URL de base");
                    ui.text_edit_singleline(&mut self.config_draft.llm.base_url);
                    ui.end_row();
                    ui.label("Clé API");
                    ui.add(
                        egui::TextEdit::singleline(&mut self.config_draft.llm.api_key)
                            .password(!self.show_secrets)
                            .desired_width(460.0),
                    );
                    ui.end_row();
                    ui.label("Variable de clé API");
                    ui.text_edit_singleline(&mut self.config_draft.llm.api_key_env);
                    ui.end_row();
                    ui.label("Timeout (s)");
                    ui.add(
                        egui::DragValue::new(&mut self.config_draft.llm.timeout_s)
                            .range(1..=3600),
                    );
                    ui.end_row();
                    ui.label("Tokens maximum");
                    ui.add(
                        egui::DragValue::new(&mut self.config_draft.llm.max_tokens)
                            .range(1..=32768),
                    );
                    ui.end_row();
                    ui.label("Conserver en mémoire");
                    ui.checkbox(&mut self.config_draft.llm.keep_warm, "");
                    ui.end_row();
                });

            ui.separator();
            if ui.button("Enregistrer").clicked() {
                let restart_required = self.config.database != self.config_draft.database
                    || self.config.telegram != self.config_draft.telegram;
                match self.config_draft.save(&self.config_path) {
                    Ok(()) => {
                        self.config = self.config_draft.clone();
                        self.llm = LlmService::new(self.config.llm.clone());
                        self.status = if restart_required {
                            "Configuration enregistrée. Redémarre PRIORIS pour appliquer Telegram ou la nouvelle base SQLite."
                                .to_owned()
                        } else {
                            "Configuration enregistrée et appliquée à la GUI.".to_owned()
                        };
                    }
                    Err(error) => self.status = format!("Enregistrement impossible : {error}"),
                }
            }
        });
    }
}

impl eframe::App for PriorisApp {
    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        let context = ui.ctx().clone();
        egui::CentralPanel::default().show(ui, |ui| {
            self.navigation(ui);
            ui.separator();
            match self.view {
                View::Tasks => self.tasks_view(ui),
                View::Today => self.today_view(ui),
                View::Goals => self.goals_view(ui),
                View::Obsidian => self.obsidian_view(ui),
                View::Info => self.info_view(ui),
                View::Llm => self.llm_view(ui),
                View::Configuration => self.configuration_view(ui),
            }
            ui.separator();
            ui.label(&self.status);
        });

        if let Some(mut flow) = self.add_flow.take() {
            let categories = self.store.categories().unwrap_or_default();
            let mut open = true;
            let mut action = AddAction::None;
            egui::Window::new(format!(
                "Entretien — {}",
                if flow.title.is_empty() {
                    "nouvelle tâche"
                } else {
                    &flow.title
                }
            ))
            .open(&mut open)
            .collapsible(false)
            .resizable(true)
            .default_width(760.0)
            .show(&context, |ui| {
                action = render_add_flow(ui, &mut flow, &categories, &self.llm)
            });
            if !open && matches!(action, AddAction::None) {
                action = AddAction::Cancel;
            }
            match action {
                AddAction::None => self.add_flow = Some(flow),
                AddAction::Cancel => self.status = "Création annulée".to_owned(),
                AddAction::Finish(task) => self.finish_task(*task),
            }
        }
    }
}

fn render_add_flow(
    ui: &mut egui::Ui,
    flow: &mut AddFlow,
    categories: &[Category],
    llm: &LlmService,
) -> AddAction {
    if !flow.metadata_done {
        ui.label("Titre");
        ui.text_edit_singleline(&mut flow.title);
        ui.label("Catégorie");
        egui::ComboBox::from_id_salt("category")
            .selected_text(
                categories
                    .iter()
                    .find(|value| value.code == flow.category)
                    .map_or(flow.category.as_str(), |value| value.label.as_str()),
            )
            .show_ui(ui, |ui| {
                for category in categories {
                    ui.selectable_value(&mut flow.category, category.code.clone(), &category.label);
                }
            });
        ui.label("Nouvelle catégorie (facultatif, elle sera mémorisée)");
        ui.text_edit_singleline(&mut flow.custom_category);
        ui.checkbox(&mut flow.has_deadline, "Cette tâche a une date limite");
        if flow.has_deadline {
            ui.text_edit_singleline(&mut flow.deadline);
        }
        let mut cancel = false;
        let mut start = false;
        ui.horizontal(|ui| {
            cancel = ui.button("Annuler").clicked();
            start = ui.button("Commencer l'entretien").clicked();
        });
        if cancel {
            return AddAction::Cancel;
        }
        if start {
            if flow.title.trim().is_empty() {
                flow.error = "Le titre est obligatoire.".to_owned();
            } else if flow.has_deadline {
                match NaiveDate::parse_from_str(&flow.deadline, "%Y-%m-%d") {
                    Ok(date) => {
                        flow.session.deadline_days =
                            Some((date - Local::now().date_naive()).num_days());
                        flow.metadata_done = true;
                        flow.error.clear();
                    }
                    Err(_) => flow.error = "Date invalide, format attendu : AAAA-MM-JJ.".to_owned(),
                }
            } else {
                flow.metadata_done = true;
                flow.error.clear();
            }
        }
        if !flow.error.is_empty() {
            ui.colored_label(egui::Color32::RED, &flow.error);
        }
        return AddAction::None;
    }

    if let Some(question) = flow.session.next_question() {
        ui.label(format!(
            "Mode : {}",
            if flow.session.full_mode {
                "complet"
            } else {
                "express"
            }
        ));
        ui.heading(question_text(question));
        if let Some(pending) = flow.pending_interpretation.take() {
            ui.label(&pending.reformulation);
            ui.label(format!("Réponse proposée : {}", pending.value));
            let mut keep = true;
            ui.horizontal(|ui| {
                if ui.button("Confirmer").clicked() {
                    if let Err(error) = apply_answer(
                        &mut flow.session,
                        question,
                        &pending.value,
                        pending.uncertainty,
                    ) {
                        flow.error = error;
                    }
                    flow.free_answer.clear();
                    keep = false;
                }
                if ui.button("Refuser").clicked() {
                    keep = false;
                }
            });
            if keep {
                flow.pending_interpretation = Some(pending);
            }
        } else {
            for (label, value) in question_options(question) {
                if ui.button(label).clicked()
                    && let Err(error) =
                        apply_answer(&mut flow.session, question, value, Uncertainty::Certain)
                {
                    flow.error = error;
                }
            }
            if llm.available() {
                ui.separator();
                ui.label("Réponse libre interprétée par le LLM");
                ui.horizontal(|ui| {
                    ui.text_edit_singleline(&mut flow.free_answer);
                    if ui.button("Interpréter").clicked() && !flow.free_answer.trim().is_empty() {
                        let result = if let Some(axis) = question_axis(question) {
                            llm.interpret_axis(axis, question_text(question), &flow.free_answer)
                                .map(|value| PendingInterpretation {
                                    value: value.value.to_string(),
                                    uncertainty: value.uncertainty,
                                    reformulation: value.reformulation,
                                })
                        } else {
                            let options = question_options(question)
                                .into_iter()
                                .map(|(label, value)| (label.to_owned(), value.to_owned()))
                                .collect::<Vec<_>>();
                            llm.interpret_option(
                                question_text(question),
                                &options,
                                &flow.free_answer,
                            )
                            .map(|value| PendingInterpretation {
                                value: value.value,
                                uncertainty: value.uncertainty,
                                reformulation: value.reformulation,
                            })
                        };
                        match result {
                            Ok(value) => flow.pending_interpretation = Some(value),
                            Err(error) => {
                                flow.error =
                                    format!("LLM indisponible : {error}. Utilise les boutons.")
                            }
                        }
                    }
                });
            }
        }
        if !flow.error.is_empty() {
            ui.colored_label(egui::Color32::RED, &flow.error);
        }
        return AddAction::None;
    }

    if llm.available() && !flow.challenge_initialized {
        flow.challenge_initialized = true;
        match llm.challenge_questions(
            &flow.title,
            flow.session.subjective.map_or("P4", Priority::as_str),
            "fr",
        ) {
            Ok(questions) => flow.challenge_questions = questions,
            Err(error) => flow.error = format!("Challenges LLM ignorés : {error}"),
        }
    }
    if flow.challenge_index < flow.challenge_questions.len() {
        let question = flow.challenge_questions[flow.challenge_index].clone();
        ui.label(format!(
            "Vérification anti-biais {}/{}",
            flow.challenge_index + 1,
            flow.challenge_questions.len()
        ));
        ui.heading(question.clone());
        if let Some(correction) = flow.pending_correction.take() {
            ui.label(&correction.reason);
            if let Some(axis) = correction.axis {
                ui.label(format!(
                    "Correction proposée : {} = {}",
                    axis.code(),
                    correction.value
                ));
            }
            let mut keep = true;
            ui.horizontal(|ui| {
                if ui.button("Appliquer").clicked() {
                    if let Some(axis) = correction.axis {
                        let _ = flow.session.set_axis_probe(
                            axis,
                            correction.value,
                            correction.uncertainty,
                        );
                    }
                    flow.challenge_index += 1;
                    flow.challenge_answer.clear();
                    keep = false;
                }
                if ui.button("Ignorer").clicked() {
                    flow.challenge_index += 1;
                    flow.challenge_answer.clear();
                    keep = false;
                }
            });
            if keep {
                flow.pending_correction = Some(correction);
            }
        } else {
            ui.text_edit_singleline(&mut flow.challenge_answer);
            if ui.button("Interpréter cette réponse").clicked()
                && !flow.challenge_answer.trim().is_empty()
            {
                match llm.interpret_challenge(
                    &flow.title,
                    flow.session.subjective.map_or("P4", Priority::as_str),
                    &question,
                    &flow.challenge_answer,
                ) {
                    Ok(value) => flow.pending_correction = Some(value),
                    Err(error) => flow.error = error.to_string(),
                }
            }
        }
        return AddAction::None;
    }

    let (axes, defaulted) = flow.session.final_axes();
    let result = match score(
        &axes,
        flow.session.estimate.unwrap_or(Estimate::Unknown),
        flow.session.deadline_days,
        &flow.session.uncertainties,
        &defaulted,
        if flow.session.full_mode {
            "complet"
        } else {
            "express"
        },
        flow.session.subjective,
    ) {
        Ok(value) => value,
        Err(error) => {
            flow.error = error.to_string();
            return AddAction::None;
        }
    };
    ui.heading(format!(
        "{} · {} · {:.1}/100",
        result.priority.as_str(),
        result.quadrant,
        result.global
    ));
    ui.label(format!(
        "Urgence {:.1} · Importance {:.1}",
        result.urgency, result.importance
    ));
    if result.robust {
        ui.label(format!("Quadrant robuste : {}", result.quadrant));
    } else {
        ui.label(format!(
            "Quadrant sensible : {} · axe pivot {}",
            result.possible_quadrants.join(" / "),
            result.pivot_axis.as_deref().unwrap_or("indéterminé")
        ));
    }
    ui.label("Toutes les réponses confirmées, y compris les corrections anti-biais, sont incluses dans ce calcul.");
    ui.horizontal(|ui| {
        if ui.button("Annuler").clicked() {
            return AddAction::Cancel;
        }
        if ui.button("Enregistrer").clicked() {
            return AddAction::Finish(Box::new(FinishTask {
                title: flow.title.trim().to_owned(),
                category: flow.category.clone(),
                custom_category: flow.custom_category.clone(),
                deadline: flow.has_deadline.then(|| flow.deadline.clone()),
                source: flow.source.clone(),
                vault_task: flow.vault_task.clone(),
                session: flow.session.clone(),
                result,
            }));
        }
        AddAction::None
    })
    .inner
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

fn question_options(question: Question) -> Vec<(&'static str, &'static str)> {
    if let Some(axis) = question_axis(question) {
        return axis
            .labels_fr()
            .iter()
            .enumerate()
            .map(|(index, label)| {
                (
                    *label,
                    match index {
                        0 => "0",
                        1 => "1",
                        2 => "2",
                        3 => "3",
                        4 => "4",
                        _ => "5",
                    },
                )
            })
            .collect();
    }
    match question {
        Question::Subjective => vec![
            ("P1 — urgent et important", "P1"),
            ("P2 — important, pas urgent", "P2"),
            ("P3 — urgent, pas important", "P3"),
            ("P4 — ni urgent ni important", "P4"),
        ],
        Question::Estimate => vec![
            ("<15 min", "<15 min"),
            ("15–30 min", "15–30 min"),
            ("30–60 min", "30–60 min"),
            ("1–2 h", "1–2 h"),
            ("2–4 h", "2–4 h"),
            (">4 h", ">4 h"),
            ("Je ne sais pas", "inconnue"),
        ],
        Question::Effort => vec![("Faible", "1"), ("Moyen", "2"), ("Élevé", "3")],
        Question::Requester => vec![
            ("Moi", "moi"),
            ("Collègue", "collegue"),
            ("Manager", "manager"),
            ("Client", "client"),
        ],
        Question::Visibility | Question::Pressure => vec![
            ("Aucune", "0"),
            ("Faible", "1"),
            ("Forte", "2"),
            ("Très forte", "3"),
        ],
        _ => Vec::new(),
    }
}

fn apply_answer(
    session: &mut InterviewSession,
    question: Question,
    value: &str,
    uncertainty: Uncertainty,
) -> Result<(), String> {
    if question_axis(question).is_some() {
        return session.answer_axis(
            question,
            value.parse().map_err(|_| "invalid axis value".to_owned())?,
            uncertainty,
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

fn path_editor(ui: &mut egui::Ui, path: &mut PathBuf) {
    let mut value = path.to_string_lossy().into_owned();
    if ui
        .add(egui::TextEdit::singleline(&mut value).desired_width(460.0))
        .changed()
    {
        *path = PathBuf::from(value);
    }
}

pub fn run(config: Config, config_path: PathBuf, llm: LlmService) -> anyhow::Result<()> {
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([1100.0, 760.0])
            .with_min_inner_size([760.0, 520.0]),
        ..Default::default()
    };
    eframe::run_native(
        "PRIORIS",
        options,
        Box::new(move |_context| Ok(Box::new(PriorisApp::new(config, config_path, llm)?))),
    )
    .map_err(|error| anyhow::anyhow!(error.to_string()))
}
