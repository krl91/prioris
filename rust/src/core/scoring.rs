use std::collections::{HashMap, HashSet};

use serde::{Deserialize, Serialize};
use thiserror::Error;

use super::{Axis, Estimate, Priority, Uncertainty};

pub const ALGORITHM_VERSION: u8 = 1;
pub const URGENT_THRESHOLD: f64 = 55.0;
pub const IMPORTANT_THRESHOLD: f64 = 50.0;

#[derive(Debug, Error, PartialEq, Eq)]
pub enum ScoreError {
    #[error("missing axis {0}")]
    MissingAxis(&'static str),
    #[error("axis {axis} value {value} is outside 0..{max}")]
    OutOfRange {
        axis: &'static str,
        value: u8,
        max: u8,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ScoreResult {
    pub urgency: f64,
    pub importance: f64,
    pub global: f64,
    pub quadrant: String,
    pub priority: Priority,
    pub provisional: bool,
    pub gem: bool,
    pub leverage: f64,
    pub justification: serde_json::Value,
}

pub fn score(
    raw_axes: &HashMap<Axis, u8>,
    estimate: Estimate,
    deadline_days: Option<i64>,
    uncertainties: &HashMap<Axis, Uncertainty>,
    defaulted_axes: &HashSet<Axis>,
    mode: &str,
    subjective: Option<Priority>,
) -> Result<ScoreResult, ScoreError> {
    for axis in Axis::ALL {
        let Some(&value) = raw_axes.get(&axis) else {
            return Err(ScoreError::MissingAxis(axis.code()));
        };
        if value > axis.max() {
            return Err(ScoreError::OutOfRange {
                axis: axis.code(),
                value,
                max: axis.max(),
            });
        }
    }

    let mut axes = raw_axes.clone();
    let mut replaced = Vec::new();
    for (&axis, &uncertainty) in uncertainties {
        if uncertainty == Uncertainty::Unknown {
            axes.insert(axis, axis.median());
            replaced.push(axis);
        }
    }

    let term = |axis: Axis, weight: f64| weight * axes[&axis] as f64 / axis.max() as f64;
    let urgency_terms = [
        (Axis::BLK, term(Axis::BLK, 30.0)),
        (Axis::CDR, term(Axis::CDR, 40.0)),
        (Axis::HOR, term(Axis::HOR, 30.0)),
    ];
    let importance_terms = [
        (Axis::IMP, term(Axis::IMP, 35.0)),
        (Axis::INA, term(Axis::INA, 25.0)),
        (Axis::IRR, term(Axis::IRR, 20.0)),
        (Axis::ALN, term(Axis::ALN, 20.0)),
    ];
    let mut urgency = urgency_terms.iter().map(|(_, value)| value).sum::<f64>();
    let mut importance = importance_terms.iter().map(|(_, value)| value).sum::<f64>();
    let mut adjustments = Vec::new();

    if deadline_days.is_some_and(|days| days <= 7) && axes[&Axis::CDR] == 4 {
        if urgency < 70.0 {
            adjustments.push(
                serde_json::json!({"regle": "plancher_deadline", "avant": urgency, "apres": 70.0}),
            );
        }
        urgency = urgency.max(70.0);
    }
    if axes[&Axis::IRR] == 3 && axes[&Axis::INA] >= 3 {
        if importance < 70.0 {
            adjustments.push(serde_json::json!({"regle": "plancher_irreversibilite", "avant": importance, "apres": 70.0}));
        }
        importance = importance.max(70.0);
    }
    if axes[&Axis::ALN] == 3 {
        if importance < 55.0 {
            adjustments.push(serde_json::json!({"regle": "plancher_objectifs", "avant": importance, "apres": 55.0}));
        }
        importance = importance.max(55.0);
    }

    let global = 0.6 * importance + 0.4 * urgency;
    let (quadrant, priority) = match (
        urgency >= URGENT_THRESHOLD,
        importance >= IMPORTANT_THRESHOLD,
    ) {
        (true, true) => ("Q1", Priority::P1),
        (false, true) => ("Q2", Priority::P2),
        (true, false) => ("Q3", Priority::P3),
        (false, false) => ("Q4", Priority::P4),
    };
    let estimate_minutes = estimate.minutes();
    let gem = importance >= 45.0 && estimate != Estimate::Unknown && estimate_minutes <= 60;
    let leverage = importance / (estimate_minutes as f64 / 60.0).max(0.25);
    let provisional = !replaced.is_empty() || estimate == Estimate::Unknown;

    let axes_json = Axis::ALL
        .into_iter()
        .map(|axis| {
            (
                axis.code().to_string(),
                serde_json::json!({
                    "valeur": axes[&axis],
                    "brut": raw_axes[&axis],
                    "defaut": defaulted_axes.contains(&axis),
                    "incertitude_amortie": replaced.contains(&axis),
                }),
            )
        })
        .collect::<serde_json::Map<String, serde_json::Value>>();
    let urgency_json = urgency_terms
        .into_iter()
        .map(|(axis, value)| (axis.code().to_string(), serde_json::json!(round2(value))))
        .collect::<serde_json::Map<String, serde_json::Value>>();
    let importance_json = importance_terms
        .into_iter()
        .map(|(axis, value)| (axis.code().to_string(), serde_json::json!(round2(value))))
        .collect::<serde_json::Map<String, serde_json::Value>>();
    let subjective_gap = subjective.map(|value| priority.level() - value.level());
    let justification = serde_json::json!({
        "version_algo": ALGORITHM_VERSION,
        "mode": mode,
        "axes": axes_json,
        "ponderations": {
            "U": {"BLK": 30, "CDR": 40, "HOR": 30},
            "I": {"IMP": 35, "INA": 25, "IRR": 20, "ALN": 20},
        },
        "calculs": {
            "U": {"termes": urgency_json, "total": round2(urgency)},
            "I": {"termes": importance_json, "total": round2(importance)},
            "G": {"formule": "0.6*I + 0.4*U", "total": round2(global)},
        },
        "ajustements": adjustments,
        "seuils": {"urgent": URGENT_THRESHOLD, "important": IMPORTANT_THRESHOLD},
        "quadrant": quadrant,
        "priorite": priority.as_str(),
        "subjective": subjective.map(Priority::as_str),
        "ecart_subjectif": subjective_gap,
        "pepite": gem,
        "levier_par_h": round1(leverage),
        "provisoire": provisional,
    });

    Ok(ScoreResult {
        urgency,
        importance,
        global,
        quadrant: quadrant.to_owned(),
        priority,
        provisional,
        gem,
        leverage,
        justification,
    })
}

fn round1(value: f64) -> f64 {
    (value * 10.0).round() / 10.0
}

fn round2(value: f64) -> f64 {
    (value * 100.0).round() / 100.0
}
