use std::collections::{HashMap, HashSet};

use serde::{Deserialize, Serialize};
use thiserror::Error;

use super::{Axis, Estimate, Priority, Uncertainty};

pub const ALGORITHM_VERSION: u8 = 2;
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
    pub robust: bool,
    pub possible_quadrants: Vec<String>,
    pub pivot_axis: Option<String>,
    pub justification: serde_json::Value,
}

fn weights_urgency(axis: Axis) -> Option<f64> {
    match axis {
        Axis::BLK => Some(30.0),
        Axis::CDR => Some(40.0),
        Axis::HOR => Some(30.0),
        _ => None,
    }
}

fn weights_importance(axis: Axis) -> Option<f64> {
    match axis {
        Axis::IMP => Some(35.0),
        Axis::INA => Some(25.0),
        Axis::IRR => Some(20.0),
        Axis::ALN => Some(20.0),
        _ => None,
    }
}

fn score_pair(axes: &HashMap<Axis, u8>, deadline_days: Option<i64>) -> (f64, f64) {
    let mut urgency = Axis::ALL
        .into_iter()
        .filter_map(|axis| weights_urgency(axis).map(|weight| (axis, weight)))
        .map(|(axis, weight)| weight * axes[&axis] as f64 / axis.max() as f64)
        .sum::<f64>();
    let mut importance = Axis::ALL
        .into_iter()
        .filter_map(|axis| weights_importance(axis).map(|weight| (axis, weight)))
        .map(|(axis, weight)| weight * axes[&axis] as f64 / axis.max() as f64)
        .sum::<f64>();
    if deadline_days.is_some_and(|days| days <= 7) && axes[&Axis::CDR] == 4 {
        urgency = urgency.max(70.0);
    }
    if axes[&Axis::IRR] == 3 && axes[&Axis::INA] >= 3 {
        importance = importance.max(70.0);
    }
    if axes[&Axis::ALN] == 3 && (axes[&Axis::IMP] >= 2 || axes[&Axis::INA] >= 2) {
        importance = importance.max(55.0);
    }
    (urgency, importance)
}

fn quadrant(urgent: bool, important: bool) -> &'static str {
    match (urgent, important) {
        (true, true) => "Q1",
        (false, true) => "Q2",
        (true, false) => "Q3",
        (false, false) => "Q4",
    }
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
    let (urgency, importance) = score_pair(&axes, deadline_days);
    let mut adjustments = Vec::new();

    if deadline_days.is_some_and(|days| days <= 7) && axes[&Axis::CDR] == 4 {
        let raw = urgency_terms.iter().map(|(_, value)| value).sum::<f64>();
        if raw < 70.0 {
            adjustments.push(
                serde_json::json!({"regle": "plancher_deadline", "avant": raw, "apres": 70.0}),
            );
        }
    }
    if axes[&Axis::IRR] == 3 && axes[&Axis::INA] >= 3 {
        let raw = importance_terms.iter().map(|(_, value)| value).sum::<f64>();
        if raw < 70.0 {
            adjustments.push(serde_json::json!({"regle": "plancher_irreversibilite", "avant": raw, "apres": 70.0}));
        }
    }
    if axes[&Axis::ALN] == 3 && (axes[&Axis::IMP] >= 2 || axes[&Axis::INA] >= 2) {
        let raw = importance_terms.iter().map(|(_, value)| value).sum::<f64>();
        if raw < 55.0 {
            adjustments.push(
                serde_json::json!({"regle": "plancher_objectifs", "avant": raw, "apres": 55.0}),
            );
        }
    } else if axes[&Axis::ALN] == 3 {
        adjustments.push(serde_json::json!({
            "regle": "garde_fou_objectifs",
            "motif": "ALN alone is insufficient without impact or inaction cost"
        }));
    }

    let ranges = Axis::ALL
        .into_iter()
        .map(|axis| {
            let value = axes[&axis];
            let range = if axis == Axis::IMP && defaulted_axes.contains(&axis) {
                (0, axis.max())
            } else {
                match uncertainties
                    .get(&axis)
                    .copied()
                    .unwrap_or(Uncertainty::Certain)
                {
                    Uncertainty::Unknown => (
                        axis.median().saturating_sub(1),
                        (axis.median() + 1).min(axis.max()),
                    ),
                    Uncertainty::Hesitant => (value.saturating_sub(1), (value + 1).min(axis.max())),
                    Uncertainty::Certain => (value, value),
                }
            };
            (axis, range)
        })
        .collect::<HashMap<_, _>>();
    let lower = ranges
        .iter()
        .map(|(&axis, &(low, _))| (axis, low))
        .collect();
    let upper = ranges
        .iter()
        .map(|(&axis, &(_, high))| (axis, high))
        .collect();
    let (u_min, i_min) = score_pair(&lower, deadline_days);
    let (u_max, i_max) = score_pair(&upper, deadline_days);
    let urgent_states: &[bool] = if u_max < URGENT_THRESHOLD {
        &[false]
    } else if u_min >= URGENT_THRESHOLD {
        &[true]
    } else {
        &[false, true]
    };
    let important_states: &[bool] = if i_max < IMPORTANT_THRESHOLD {
        &[false]
    } else if i_min >= IMPORTANT_THRESHOLD {
        &[true]
    } else {
        &[false, true]
    };
    let possible_quadrants = ["Q1", "Q2", "Q3", "Q4"]
        .into_iter()
        .filter(|candidate| {
            urgent_states.iter().any(|urgent| {
                important_states
                    .iter()
                    .any(|important| quadrant(*urgent, *important) == *candidate)
            })
        })
        .map(str::to_owned)
        .collect::<Vec<_>>();
    let robust = possible_quadrants.len() == 1;
    let u_crosses = u_min < URGENT_THRESHOLD && u_max >= URGENT_THRESHOLD;
    let i_crosses = i_min < IMPORTANT_THRESHOLD && i_max >= IMPORTANT_THRESHOLD;
    let pivot_axis = Axis::ALL
        .into_iter()
        .filter_map(|axis| {
            let (low, high) = ranges[&axis];
            let weight = if u_crosses {
                weights_urgency(axis)
            } else {
                None
            }
            .or_else(|| {
                if i_crosses {
                    weights_importance(axis)
                } else {
                    None
                }
            })?;
            (high > low).then_some((weight * f64::from(high - low) / f64::from(axis.max()), axis))
        })
        .max_by(|left, right| left.0.total_cmp(&right.0))
        .map(|(_, axis)| axis.code().to_owned());

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
    let gem = importance >= IMPORTANT_THRESHOLD
        && estimate != Estimate::Unknown
        && estimate_minutes <= 60;
    let leverage = importance / (estimate_minutes as f64 / 60.0).max(0.25);
    let provisional = !replaced.is_empty()
        || estimate == Estimate::Unknown
        || defaulted_axes.contains(&Axis::IMP)
        || !robust;

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
        "robustesse": {
            "robuste": robust,
            "U_intervalle": [round2(u_min), round2(u_max)],
            "I_intervalle": [round2(i_min), round2(i_max)],
            "quadrants_possibles": possible_quadrants,
            "axe_pivot": pivot_axis,
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
        robust,
        possible_quadrants,
        pivot_axis,
        justification,
    })
}

fn round1(value: f64) -> f64 {
    (value * 10.0).round() / 10.0
}

fn round2(value: f64) -> f64 {
    (value * 100.0).round() / 100.0
}
