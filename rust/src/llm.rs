use std::{
    sync::{Arc, Mutex},
    time::Instant,
};

use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use thiserror::Error;

use crate::{
    config::LlmConfig,
    core::{Axis, Uncertainty},
};

const INTERPRETER_SYSTEM: &str = "PRIORIS_INTERPRETER: Map the free answer to the supplied scale. Never calculate priority. Return only JSON with valeur, incertitude, reformulation, status (ok or abstain), confidence (0..1). Abstain when evidence is insufficient.";
const QUESTION_SYSTEM: &str = "PRIORIS_QUESTION: Select exactly one supplied option from the free answer. Never calculate priority. Return only JSON with value, incertitude, reformulation, status, confidence. Abstain when no option is supported.";
const CHALLENGE_SYSTEM: &str = "PRIORIS_CHALLENGE: Return exactly three short questions, one per future turn, that test deadline reality, social pressure or visibility, avoidance, and missing evidence behind the instinctive quadrant. Return only JSON with questions, status, confidence.";
const CHALLENGE_ANSWER_SYSTEM: &str = "PRIORIS_CHALLENGE_ANSWER: Interpret one answer as at most one factual axis correction. Never calculate priority. Return only JSON with axis, value, uncertainty, reason, status, confidence. Use axis null and abstain without concrete evidence.";
const IMPACT_SYSTEM: &str = "PRIORIS_IMPACT: Independently classify only the shortlisted task ids against the information. Never invent another id or calculate priority. If none matches, impacted is empty and propose a concise new task. Extract an explicit deadline as YYYY-MM-DD and answer direct questions briefly. Return only JSON with impacted, new_task_title, suggested_deadline, direct_answer, explanation, status, confidence.";

#[derive(Debug, Error)]
pub enum LlmError {
    #[error("LLM is disabled")]
    Disabled,
    #[error("provider {0} is not supported by this build")]
    Unsupported(String),
    #[error("model file does not exist: {0}")]
    MissingModel(String),
    #[error("HTTP request failed: {0}")]
    Http(String),
    #[error("invalid provider response: {0}")]
    InvalidResponse(String),
    #[error("embedded inference failed: {0}")]
    Inference(String),
    #[error("the model abstained or confidence was too low")]
    Abstained,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct InterpretedAnswer {
    pub axis: Axis,
    pub value: u8,
    pub uncertainty: Uncertainty,
    pub reformulation: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct InterpretedOption {
    pub value: String,
    pub uncertainty: Uncertainty,
    pub reformulation: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ChallengeCorrection {
    pub axis: Option<Axis>,
    pub value: u8,
    pub uncertainty: Uncertainty,
    pub reason: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ImpactedTask {
    pub id: i64,
    pub impact: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ImpactProposal {
    pub impacted: Vec<ImpactedTask>,
    pub new_task_title: String,
    pub suggested_deadline: String,
    pub direct_answer: String,
    pub explanation: String,
}

#[derive(Clone)]
pub struct LlmService {
    config: LlmConfig,
    last_error: Arc<Mutex<Option<String>>>,
    #[cfg(feature = "embedded-llm")]
    embedded: Arc<Mutex<Option<mistralrs::Model>>>,
}

impl LlmService {
    pub fn new(config: LlmConfig) -> Self {
        Self {
            config,
            last_error: Arc::new(Mutex::new(None)),
            #[cfg(feature = "embedded-llm")]
            embedded: Arc::new(Mutex::new(None)),
        }
    }

    pub fn available(&self) -> bool {
        self.config.enabled
    }

    pub fn provider(&self) -> &str {
        &self.config.provider
    }

    pub fn last_error(&self) -> Option<String> {
        self.last_error.lock().ok().and_then(|value| value.clone())
    }

    pub fn health_check(&self) -> Result<u128, LlmError> {
        let started = Instant::now();
        let result = self.chat("PRIORIS_HEALTH", &json!({"ping": true}).to_string());
        match result {
            Ok(_) => {
                self.set_error(None);
                Ok(started.elapsed().as_millis())
            }
            Err(error) => {
                self.set_error(Some(error.to_string()));
                Err(error)
            }
        }
    }

    pub fn health_check_with_retries(&self, attempts: usize) -> Result<u128, LlmError> {
        let mut last = LlmError::Disabled;
        for _ in 0..attempts.max(1) {
            match self.health_check() {
                Ok(latency) => return Ok(latency),
                Err(error) => last = error,
            }
        }
        Err(last)
    }

    pub fn interpret_axis(
        &self,
        axis: Axis,
        question: &str,
        answer: &str,
    ) -> Result<InterpretedAnswer, LlmError> {
        let payload = json!({
            "axe": axis.code(),
            "question_posee": question,
            "echelle": axis.labels_fr().iter().enumerate().map(|(index, label)| (index.to_string(), json!(*label))).collect::<serde_json::Map<_,_>>(),
            "valeur_max": axis.max(),
            "reponse_utilisateur": answer,
        });
        let value = self.json_chat(INTERPRETER_SYSTEM, &payload)?;
        let interpreted = InterpretedAnswer {
            axis,
            value: value["valeur"]
                .as_u64()
                .ok_or_else(|| LlmError::InvalidResponse(value.to_string()))?
                as u8,
            uncertainty: uncertainty(value["incertitude"].as_u64().unwrap_or(0)),
            reformulation: required_string(&value, "reformulation")?,
        };
        if interpreted.value > axis.max() {
            return Err(LlmError::InvalidResponse(format!(
                "{}={} is outside scale",
                axis.code(),
                interpreted.value
            )));
        }
        Ok(interpreted)
    }

    pub fn interpret_option(
        &self,
        question: &str,
        options: &[(String, String)],
        answer: &str,
    ) -> Result<InterpretedOption, LlmError> {
        let payload = json!({
            "question_posee": question,
            "options": options.iter().map(|(label, value)| json!({"label": label, "value": value})).collect::<Vec<_>>(),
            "reponse_utilisateur": answer,
        });
        let value = self.json_chat(QUESTION_SYSTEM, &payload)?;
        let interpreted = InterpretedOption {
            value: required_string(&value, "value")?,
            uncertainty: uncertainty(value["incertitude"].as_u64().unwrap_or(0)),
            reformulation: required_string(&value, "reformulation")?,
        };
        if !options
            .iter()
            .any(|(_, candidate)| candidate == &interpreted.value)
        {
            return Err(LlmError::InvalidResponse(format!(
                "unknown option {}",
                interpreted.value
            )));
        }
        Ok(interpreted)
    }

    pub fn challenge_questions(
        &self,
        task: &str,
        subjective: &str,
        language: &str,
    ) -> Result<Vec<String>, LlmError> {
        let value = self.json_chat(
            CHALLENGE_SYSTEM,
            &json!({
                "tache": task,
                "classement_instinctif": subjective,
                "langue": language,
            }),
        )?;
        let questions = value["questions"]
            .as_array()
            .ok_or_else(|| LlmError::InvalidResponse(value.to_string()))?
            .iter()
            .filter_map(Value::as_str)
            .map(ToOwned::to_owned)
            .collect::<Vec<_>>();
        if questions.len() != 3 {
            return Err(LlmError::InvalidResponse(
                "the provider must return exactly three questions".to_owned(),
            ));
        }
        Ok(questions)
    }

    pub fn interpret_challenge(
        &self,
        task: &str,
        subjective: &str,
        question: &str,
        answer: &str,
    ) -> Result<ChallengeCorrection, LlmError> {
        let value = self.json_chat(
            CHALLENGE_ANSWER_SYSTEM,
            &json!({
                "tache": task,
                "classement_instinctif": subjective,
                "question_posee": question,
                "reponse_utilisateur": answer,
            }),
        )?;
        let axis = value["axis"]
            .as_str()
            .filter(|value| *value != "null")
            .map(str::parse)
            .transpose()
            .map_err(LlmError::InvalidResponse)?;
        let correction = ChallengeCorrection {
            axis,
            value: value["value"].as_u64().unwrap_or(0) as u8,
            uncertainty: uncertainty(value["uncertainty"].as_u64().unwrap_or(0)),
            reason: required_string(&value, "reason")?,
        };
        if correction
            .axis
            .is_some_and(|axis| correction.value > axis.max())
        {
            return Err(LlmError::InvalidResponse(
                "challenge value outside axis scale".to_owned(),
            ));
        }
        Ok(correction)
    }

    pub fn analyze_impact(
        &self,
        tasks: &[(i64, String)],
        information: &str,
    ) -> Result<ImpactProposal, LlmError> {
        let candidates = shortlist_tasks(tasks, information, 5);
        let value = self.json_chat(IMPACT_SYSTEM, &json!({
            "date_du_jour": chrono::Local::now().date_naive().to_string(),
            "information": information,
            "taches_existantes": candidates.iter().map(|(id, title)| json!({"id": id, "titre": title})).collect::<Vec<_>>(),
        }))?;
        let valid_ids = candidates
            .iter()
            .map(|(id, _)| *id)
            .collect::<std::collections::HashSet<_>>();
        let impacted = value["impacted"]
            .as_array()
            .into_iter()
            .flatten()
            .map(|item| {
                let id = item["id"]
                    .as_i64()
                    .ok_or_else(|| LlmError::InvalidResponse("missing impacted id".to_owned()))?;
                if !valid_ids.contains(&id) {
                    return Err(LlmError::InvalidResponse(format!(
                        "impacted id {id} is outside the shortlist"
                    )));
                }
                Ok(ImpactedTask {
                    id,
                    impact: item["impact"].as_str().unwrap_or_default().to_owned(),
                })
            })
            .collect::<Result<Vec<_>, _>>()?;
        Ok(ImpactProposal {
            impacted,
            new_task_title: value["new_task_title"]
                .as_str()
                .unwrap_or(information)
                .to_owned(),
            suggested_deadline: value["suggested_deadline"]
                .as_str()
                .unwrap_or_default()
                .to_owned(),
            direct_answer: value["direct_answer"]
                .as_str()
                .unwrap_or_default()
                .to_owned(),
            explanation: value["explanation"]
                .as_str()
                .unwrap_or("Analyse terminée.")
                .to_owned(),
        })
    }

    fn json_chat(&self, system: &str, payload: &Value) -> Result<Value, LlmError> {
        let text = self.chat(system, &payload.to_string())?;
        let value = extract_json(&text)?;
        ensure_confident(&value)?;
        Ok(value)
    }

    fn chat(&self, system: &str, user: &str) -> Result<String, LlmError> {
        if !self.config.enabled {
            return Err(LlmError::Disabled);
        }
        let result = match self.config.provider.as_str() {
            "prioris" => Ok(builtin_chat(system, user)),
            "local_gguf" | "embedded" => self.embedded_chat(system, user),
            "anthropic" => self.anthropic_chat(system, user),
            "ollama" | "lmstudio" | "openai" | "copilot" | "custom" => {
                self.openai_chat(system, user)
            }
            value => Err(LlmError::Unsupported(value.to_owned())),
        };
        self.set_error(result.as_ref().err().map(ToString::to_string));
        result
    }

    fn openai_chat(&self, system: &str, user: &str) -> Result<String, LlmError> {
        let base = if !self.config.base_url.is_empty() {
            self.config.base_url.trim_end_matches('/').to_owned()
        } else {
            match self.config.provider.as_str() {
                "ollama" => "http://localhost:11434/v1".to_owned(),
                "lmstudio" => "http://localhost:1234/v1".to_owned(),
                "openai" => "https://api.openai.com/v1".to_owned(),
                "copilot" => "https://api.githubcopilot.com".to_owned(),
                _ => {
                    return Err(LlmError::Unsupported(
                        "custom provider requires base_url".to_owned(),
                    ));
                }
            }
        };
        let mut request = ureq::post(&format!("{base}/chat/completions"))
            .header("Content-Type", "application/json");
        let key = self.config.effective_api_key();
        if !key.is_empty() {
            request = request.header("Authorization", &format!("Bearer {key}"));
        }
        if self.config.provider == "copilot" {
            request = request.header("Copilot-Integration-Id", "prioris-rust");
        }
        let payload = json!({
            "model": self.config.model.to_string_lossy(),
            "temperature": 0,
            "max_tokens": token_budget(system, self.config.max_tokens),
            "messages": [{"role":"system","content":system},{"role":"user","content":user}],
            "response_format": {"type":"json_object"},
        });
        let mut response = request
            .send_json(&payload)
            .map_err(|error| LlmError::Http(error.to_string()))?;
        let body: Value = response
            .body_mut()
            .read_json()
            .map_err(|error| LlmError::InvalidResponse(error.to_string()))?;
        body["choices"][0]["message"]["content"]
            .as_str()
            .map(ToOwned::to_owned)
            .ok_or_else(|| LlmError::InvalidResponse(body.to_string()))
    }

    fn anthropic_chat(&self, system: &str, user: &str) -> Result<String, LlmError> {
        let base = if self.config.base_url.is_empty() {
            "https://api.anthropic.com/v1"
        } else {
            self.config.base_url.trim_end_matches('/')
        };
        let payload = json!({
            "model": self.config.model.to_string_lossy(),
            "max_tokens": token_budget(system, self.config.max_tokens),
            "temperature": 0,
            "system": system,
            "messages": [{"role":"user","content":user}],
        });
        let mut response = ureq::post(&format!("{base}/messages"))
            .header("Content-Type", "application/json")
            .header("x-api-key", &self.config.effective_api_key())
            .header("anthropic-version", "2023-06-01")
            .send_json(&payload)
            .map_err(|error| LlmError::Http(error.to_string()))?;
        let body: Value = response
            .body_mut()
            .read_json()
            .map_err(|error| LlmError::InvalidResponse(error.to_string()))?;
        let text = body["content"]
            .as_array()
            .into_iter()
            .flatten()
            .filter_map(|item| item["text"].as_str())
            .collect::<String>();
        if text.is_empty() {
            Err(LlmError::InvalidResponse(body.to_string()))
        } else {
            Ok(text)
        }
    }

    #[cfg(feature = "embedded-llm")]
    fn embedded_chat(&self, system: &str, user: &str) -> Result<String, LlmError> {
        use mistralrs::{
            Constraint, DeviceMapSetting, GgufModelBuilder, RequestBuilder, TextMessageRole,
        };

        let model_path = &self.config.model;
        if !model_path.is_file() {
            return Err(LlmError::MissingModel(model_path.display().to_string()));
        }
        let mut guard = self
            .embedded
            .lock()
            .map_err(|error| LlmError::Inference(error.to_string()))?;
        let runtime = tokio::runtime::Handle::try_current().ok();
        if guard.is_none() {
            let parent = model_path
                .parent()
                .unwrap_or_else(|| std::path::Path::new("."));
            let filename = model_path
                .file_name()
                .and_then(|value| value.to_str())
                .ok_or_else(|| LlmError::MissingModel(model_path.display().to_string()))?;
            let future = GgufModelBuilder::new(parent.to_string_lossy(), vec![filename])
                .with_device_mapping(DeviceMapSetting::dummy())
                .with_max_num_seqs(1)
                .with_prefix_cache_n(None)
                .build();
            let model = if let Some(handle) = runtime.as_ref() {
                tokio::task::block_in_place(|| handle.block_on(future))
            } else {
                tokio::runtime::Runtime::new()
                    .map_err(|error| LlmError::Inference(error.to_string()))?
                    .block_on(future)
            }
            .map_err(|error| LlmError::Inference(error.to_string()))?;
            *guard = Some(model);
        }
        let messages = RequestBuilder::new()
            .set_constraint(Constraint::JsonSchema(schema_for(system)))
            .set_sampler_max_len(token_budget(system, self.config.max_tokens))
            .add_message(TextMessageRole::System, system)
            .add_message(TextMessageRole::User, user);
        let future = guard
            .as_ref()
            .expect("model initialized")
            .send_chat_request(messages);
        let response = if let Some(handle) = runtime {
            tokio::task::block_in_place(|| handle.block_on(future))
        } else {
            tokio::runtime::Runtime::new()
                .map_err(|error| LlmError::Inference(error.to_string()))?
                .block_on(future)
        }
        .map_err(|error| LlmError::Inference(error.to_string()))?;
        response.choices[0]
            .message
            .content
            .clone()
            .ok_or_else(|| LlmError::InvalidResponse("empty embedded model response".to_owned()))
    }

    #[cfg(not(feature = "embedded-llm"))]
    fn embedded_chat(&self, _system: &str, _user: &str) -> Result<String, LlmError> {
        Err(LlmError::Unsupported(
            "embedded LLM requires the embedded-llm build feature".to_owned(),
        ))
    }

    fn set_error(&self, value: Option<String>) {
        if let Some(message) = value.as_deref() {
            let path = std::path::Path::new("logs/prioris-llm.log");
            if let Some(parent) = path.parent() {
                let _ = std::fs::create_dir_all(parent);
            }
            let timestamp = chrono::Local::now().to_rfc3339();
            let line = format!(
                "{timestamp} provider={} model={} error={message}\n",
                self.config.provider,
                self.config.model.display()
            );
            if let Ok(mut file) = std::fs::OpenOptions::new()
                .create(true)
                .append(true)
                .open(path)
            {
                let _ = std::io::Write::write_all(&mut file, line.as_bytes());
            }
        }
        if let Ok(mut error) = self.last_error.lock() {
            *error = value;
        }
    }
}

fn token_budget(system: &str, configured: usize) -> usize {
    let budget = if system == "PRIORIS_HEALTH" {
        8
    } else if system == INTERPRETER_SYSTEM || system == QUESTION_SYSTEM {
        160
    } else if system == CHALLENGE_ANSWER_SYSTEM {
        128
    } else if system == CHALLENGE_SYSTEM {
        192
    } else if system == IMPACT_SYSTEM {
        320
    } else {
        128
    };
    configured.min(budget)
}

#[cfg(feature = "embedded-llm")]
fn schema_for(system: &str) -> Value {
    let confidence = json!({"type": "number", "minimum": 0, "maximum": 1});
    let status = json!({"type": "string", "enum": ["ok", "abstain"]});
    let (properties, required) = if system == "PRIORIS_HEALTH" {
        (json!({"pong": {"type": "boolean"}}), vec!["pong"])
    } else if system == INTERPRETER_SYSTEM {
        (
            json!({
                "valeur": {"type": "integer", "minimum": 0, "maximum": 5},
                "incertitude": {"type": "integer", "minimum": 0, "maximum": 2},
                "reformulation": {"type": "string", "maxLength": 240}, "status": status,
                "confidence": confidence
            }),
            vec![
                "valeur",
                "incertitude",
                "reformulation",
                "status",
                "confidence",
            ],
        )
    } else if system == QUESTION_SYSTEM {
        (
            json!({
                "value": {"type": "string"},
                "incertitude": {"type": "integer", "minimum": 0, "maximum": 2},
                "reformulation": {"type": "string", "maxLength": 240}, "status": status,
                "confidence": confidence
            }),
            vec![
                "value",
                "incertitude",
                "reformulation",
                "status",
                "confidence",
            ],
        )
    } else if system == CHALLENGE_SYSTEM {
        (
            json!({
                "questions": {"type": "array", "minItems": 3, "maxItems": 3,
                              "items": {"type": "string"}},
                "status": status, "confidence": confidence
            }),
            vec!["questions", "status", "confidence"],
        )
    } else if system == CHALLENGE_ANSWER_SYSTEM {
        (
            json!({
                "axis": {"type": ["string", "null"]},
                "value": {"type": "integer", "minimum": 0, "maximum": 5},
                "uncertainty": {"type": "integer", "minimum": 0, "maximum": 2},
                "reason": {"type": "string"}, "status": status,
                "confidence": confidence
            }),
            vec![
                "axis",
                "value",
                "uncertainty",
                "reason",
                "status",
                "confidence",
            ],
        )
    } else {
        (
            json!({
                "impacted": {"type": "array", "items": {"type": "object",
                    "properties": {"id": {"type": "integer"}, "impact": {"type": "string"}},
                    "required": ["id", "impact"], "additionalProperties": false}},
                "new_task_title": {"type": "string"},
                "suggested_deadline": {"type": "string"},
                "direct_answer": {"type": "string"},
                "explanation": {"type": "string"}, "status": status,
                "confidence": confidence
            }),
            vec![
                "impacted",
                "new_task_title",
                "suggested_deadline",
                "direct_answer",
                "explanation",
                "status",
                "confidence",
            ],
        )
    };
    json!({
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": false
    })
}

fn ensure_confident(value: &Value) -> Result<(), LlmError> {
    if value["status"].as_str() == Some("abstain")
        || value["confidence"]
            .as_f64()
            .is_some_and(|score| score < 0.55)
    {
        return Err(LlmError::Abstained);
    }
    Ok(())
}

fn shortlist_tasks(tasks: &[(i64, String)], information: &str, limit: usize) -> Vec<(i64, String)> {
    const STOPWORDS: &[&str] = &[
        "avec", "cette", "dans", "des", "doit", "elle", "est", "faire", "les", "pour", "que",
        "qui", "sur", "une", "the", "this", "that", "with", "from", "task",
    ];
    let tokenize = |text: &str| {
        text.to_lowercase()
            .split(|character: char| !character.is_alphanumeric())
            .filter(|token| token.chars().count() >= 3 && !STOPWORDS.contains(token))
            .map(str::to_owned)
            .collect::<std::collections::HashSet<_>>()
    };
    let note_tokens = tokenize(information);
    let mut ranked = tasks
        .iter()
        .filter_map(|(id, title)| {
            let title_tokens = tokenize(title);
            let overlap = note_tokens.intersection(&title_tokens).count();
            (overlap > 0).then_some((overlap, *id, title.clone()))
        })
        .collect::<Vec<_>>();
    ranked.sort_by_key(|(overlap, id, _)| (std::cmp::Reverse(*overlap), *id));
    ranked
        .into_iter()
        .take(limit)
        .map(|(_, id, title)| (id, title))
        .collect()
}

fn uncertainty(value: u64) -> Uncertainty {
    match value {
        1 => Uncertainty::Hesitant,
        2 => Uncertainty::Unknown,
        _ => Uncertainty::Certain,
    }
}

fn required_string(value: &Value, key: &str) -> Result<String, LlmError> {
    value[key]
        .as_str()
        .filter(|text| !text.trim().is_empty())
        .map(ToOwned::to_owned)
        .ok_or_else(|| LlmError::InvalidResponse(format!("missing {key}: {value}")))
}

fn extract_json(text: &str) -> Result<Value, LlmError> {
    let start = text
        .find('{')
        .ok_or_else(|| LlmError::InvalidResponse(text.to_owned()))?;
    let end = text
        .rfind('}')
        .ok_or_else(|| LlmError::InvalidResponse(text.to_owned()))?;
    serde_json::from_str(&text[start..=end])
        .map_err(|error| LlmError::InvalidResponse(error.to_string()))
}

fn builtin_chat(system: &str, user: &str) -> String {
    if system == "PRIORIS_HEALTH" {
        return json!({"pong": true}).to_string();
    }
    let payload: Value = serde_json::from_str(user).unwrap_or_default();
    let answer = payload["reponse_utilisateur"]
        .as_str()
        .or_else(|| payload["information"].as_str())
        .unwrap_or_default()
        .to_lowercase();
    match system {
        INTERPRETER_SYSTEM => {
            let max = payload["valeur_max"].as_u64().unwrap_or(4);
            let number = answer
                .split(|character: char| !character.is_ascii_digit())
                .find_map(|value| value.parse::<u64>().ok())
                .map(|value| value.min(max));
            let (value, uncertainty) =
                if answer.contains("ne sais pas") || answer.contains("don't know") {
                    (max / 2, 2)
                } else if let Some(value) = number {
                    (value, 0)
                } else {
                    let positive = ["majeur", "grave", "bloque", "urgent", "important", "oui"]
                        .iter()
                        .any(|word| answer.contains(word));
                    let negative = ["rien", "aucun", "non", "negligeable", "négligeable"]
                        .iter()
                        .any(|word| answer.contains(word));
                    (
                        if positive {
                            max
                        } else if negative {
                            0
                        } else {
                            max / 2
                        },
                        if positive || negative { 0 } else { 1 },
                    )
                };
            json!({"valeur":value,"incertitude":uncertainty,"reformulation":format!("Réponse comprise au niveau {value}.")}).to_string()
        }
        QUESTION_SYSTEM => {
            let options = payload["options"].as_array().cloned().unwrap_or_default();
            let found = options
                .iter()
                .find(|option| {
                    answer.contains(&option["label"].as_str().unwrap_or_default().to_lowercase())
                })
                .or_else(|| options.first());
            json!({"value":found.and_then(|value| value["value"].as_str()).unwrap_or_default(),"incertitude":1,"reformulation":"Option la plus proche proposée."}).to_string()
        }
        CHALLENGE_SYSTEM => {
            let title = payload["tache"].as_str().unwrap_or("cette tâche");
            json!({"questions":[
                format!("Quel fait concret rend vraiment « {title} » urgent ou important ?"),
                "Réagis-tu à une pression externe ou à un impact mesurable ?",
                "Quel élément te ferait changer ton classement instinctif ?"
            ]})
            .to_string()
        }
        CHALLENGE_ANSWER_SYSTEM => {
            if ["deadline", "échéance", "demain", "ce soir", "retard"]
                .iter()
                .any(|word| answer.contains(word))
            {
                json!({"axis":"CDR","value":3,"uncertainty":0,"reason":"Une échéance ou un coût du retard est mentionné."}).to_string()
            } else if ["bloque", "attend", "dépend"]
                .iter()
                .any(|word| answer.contains(word))
            {
                json!({"axis":"BLK","value":4,"uncertainty":0,"reason":"Un blocage concret est mentionné."}).to_string()
            } else {
                json!({"axis":null,"value":0,"uncertainty":1,"reason":"Aucun fait assez précis pour corriger un axe."}).to_string()
            }
        }
        IMPACT_SYSTEM => {
            let tasks = payload["taches_existantes"]
                .as_array()
                .cloned()
                .unwrap_or_default();
            let tokens = answer
                .split_whitespace()
                .filter(|value| value.len() > 3)
                .collect::<Vec<_>>();
            let impacted = tasks.iter().filter_map(|task| {
                let title = task["titre"].as_str()?.to_lowercase();
                tokens.iter().any(|token| title.contains(token)).then(|| json!({"id":task["id"],"impact":"Le texte partage un sujet avec cette tâche."}))
            }).collect::<Vec<_>>();
            json!({
                "impacted": impacted,
                "new_task_title": if impacted.is_empty() { payload["information"].as_str().unwrap_or_default() } else { "" },
                "suggested_deadline":"",
                "direct_answer":"",
                "explanation": if impacted.is_empty() { "Aucune tâche existante ne semble clairement impactée." } else { "Des tâches liées ont été trouvées." }
            }).to_string()
        }
        _ => "{}".to_owned(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn builtin_provider_interprets_without_network() {
        let config = LlmConfig {
            enabled: true,
            ..LlmConfig::default()
        };
        let llm = LlmService::new(config);
        let answer = llm
            .interpret_axis(Axis::INA, Axis::INA.question_fr(), "un vrai problème")
            .unwrap();
        assert!(answer.value >= 2);
    }

    #[test]
    fn disabled_provider_is_explicit() {
        let llm = LlmService::new(LlmConfig::default());
        assert!(matches!(llm.health_check(), Err(LlmError::Disabled)));
    }

    #[test]
    fn interpretation_budget_leaves_room_for_complete_json() {
        assert_eq!(token_budget(INTERPRETER_SYSTEM, 512), 160);
        assert_eq!(token_budget(QUESTION_SYSTEM, 120), 120);
    }
}
