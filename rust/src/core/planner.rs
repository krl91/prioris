use std::collections::{HashMap, HashSet};

use serde::{Deserialize, Serialize};

use super::{Effort, Priority};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct PlanTask {
    pub task_id: i64,
    pub title: String,
    pub priority: Priority,
    pub global_score: f64,
    pub estimate_minutes: Option<u32>,
    pub effort: Effort,
    pub category: String,
    pub gem: bool,
    pub deadline_days: Option<i64>,
    pub deadline: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct PlanItem {
    pub task: PlanTask,
    pub duration_minutes: u32,
    pub partial: bool,
    pub note: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct DayPlan {
    pub items: Vec<PlanItem>,
    pub sacrificed: Vec<PlanTask>,
    pub excluded: Vec<(PlanTask, String)>,
    pub usable_capacity_minutes: u32,
    pub minutes_per_category: HashMap<String, u32>,
    pub warnings: Vec<String>,
}

fn energy_adjustment(energy: u8, effort: Effort) -> Option<i32> {
    match energy {
        0 | 1 => match effort {
            Effort::Low => Some(0),
            Effort::Medium => Some(-25),
            Effort::High => None,
        },
        2 => match effort {
            Effort::Low | Effort::Medium => Some(0),
            Effort::High => Some(-25),
        },
        3 => Some(0),
        _ => match effort {
            Effort::Low => Some(-10),
            Effort::Medium => Some(0),
            Effort::High => Some(10),
        },
    }
}

fn deadline_bonus(days: Option<i64>) -> i32 {
    let Some(days) = days else { return 0 };
    [(0, 40), (1, 35), (3, 28), (7, 20), (14, 12), (30, 6)]
        .into_iter()
        .find_map(|(max_days, bonus)| (days <= max_days).then_some(bonus))
        .unwrap_or(0)
}

fn task_value(task: &PlanTask, energy: u8) -> f64 {
    task.global_score
        + if task.gem { 10.0 } else { 0.0 }
        + deadline_bonus(task.deadline_days) as f64
        + energy_adjustment(energy, task.effort).unwrap_or(0) as f64
}

pub fn build_day_plan(tasks: &[PlanTask], capacity_minutes: u32, energy: u8) -> DayPlan {
    let usable = (capacity_minutes as f64 * 0.8) as u32;
    let mut remaining = usable;
    let mut items = Vec::new();
    let mut excluded = Vec::new();
    let mut warnings = Vec::new();
    let mut major_count = 0_u8;

    let mut candidates = tasks.to_vec();
    candidates.sort_by(|left, right| {
        let left_group = if left.priority == Priority::P1 { 0 } else { 1 };
        let right_group = if right.priority == Priority::P1 { 0 } else { 1 };
        left_group
            .cmp(&right_group)
            .then_with(|| task_value(right, energy).total_cmp(&task_value(left, energy)))
            .then_with(|| left.task_id.cmp(&right.task_id))
    });

    for task in candidates {
        if task.priority == Priority::P4 {
            excluded.push((task, "P4: never scheduled".to_owned()));
            continue;
        }
        let Some(duration) = task.estimate_minutes else {
            excluded.push((task, "unknown estimate".to_owned()));
            continue;
        };
        let forced_p1 = task.priority == Priority::P1;
        let adjustment = energy_adjustment(energy, task.effort);
        if adjustment.is_none() && !forced_p1 {
            excluded.push((task, "effort incompatible with today's energy".to_owned()));
            continue;
        }
        let major = duration >= 60 || task.effort == Effort::High;
        if major && major_count >= 3 {
            excluded.push((task, "maximum of three major tasks reached".to_owned()));
            continue;
        }
        let mut note = String::new();
        if adjustment.is_none() && forced_p1 {
            note = "Demanding P1 with very low energy: start with 25 minutes or renegotiate"
                .to_owned();
            warnings.push(note.clone());
        }
        if let Some(days) = task
            .deadline_days
            .filter(|_| deadline_bonus(task.deadline_days) > 0)
        {
            let deadline_note = if days < 0 {
                "deadline overdue".to_owned()
            } else if days == 0 {
                "deadline today".to_owned()
            } else {
                format!("deadline D-{days}")
            };
            if !note.is_empty() {
                note.push_str("; ");
            }
            note.push_str(&deadline_note);
        }
        let (selected_duration, partial) = if duration <= remaining {
            (duration, false)
        } else if task.global_score >= 60.0 && remaining >= 60 {
            (60, true)
        } else {
            excluded.push((task, "insufficient remaining capacity".to_owned()));
            continue;
        };
        remaining -= selected_duration;
        major_count += u8::from(major);
        items.push(PlanItem {
            task,
            duration_minutes: selected_duration,
            partial,
            note,
        });
    }

    let planned_ids = items
        .iter()
        .map(|item| item.task.task_id)
        .collect::<HashSet<_>>();
    let excluded_ids = excluded
        .iter()
        .map(|(task, _)| task.task_id)
        .collect::<HashSet<_>>();
    let sacrificed = tasks
        .iter()
        .filter(|task| {
            !planned_ids.contains(&task.task_id) && !excluded_ids.contains(&task.task_id)
        })
        .cloned()
        .collect::<Vec<_>>();
    let mut minutes_per_category = HashMap::new();
    for item in &items {
        *minutes_per_category
            .entry(item.task.category.clone())
            .or_insert(0) += item.duration_minutes;
    }

    DayPlan {
        items,
        sacrificed,
        excluded,
        usable_capacity_minutes: usable,
        minutes_per_category,
        warnings,
    }
}
