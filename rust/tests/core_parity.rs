use std::collections::{HashMap, HashSet};

use prioris::core::{
    Axis, Effort, Estimate, InterviewSession, PlanTask, Priority, Question, Uncertainty,
    build_day_plan, score,
};

fn axes(values: [u8; 7]) -> HashMap<Axis, u8> {
    Axis::ALL.into_iter().zip(values).collect()
}

#[test]
fn score_matches_python_formula_for_q1() {
    let result = score(
        &axes([5, 4, 4, 3, 4, 4, 3]),
        Estimate::M30_60,
        Some(1),
        &HashMap::new(),
        &HashSet::new(),
        "complet",
        Some(Priority::P1),
    )
    .unwrap();
    assert_eq!(result.urgency, 100.0);
    assert_eq!(result.importance, 100.0);
    assert_eq!(result.global, 100.0);
    assert_eq!(result.quadrant, "Q1");
    assert_eq!(result.priority, Priority::P1);
    assert!(result.gem);
    assert_eq!(result.justification["axes"]["BLK"]["valeur"], 5);
    assert_eq!(result.justification["calculs"]["G"]["total"], 100.0);
    assert_eq!(result.justification["priorite"], "P1");
    assert!(result.justification.get("calculations").is_none());
}

#[test]
fn unknown_uncertainty_uses_axis_median() {
    let mut uncertainty = HashMap::new();
    uncertainty.insert(Axis::BLK, Uncertainty::Unknown);
    let result = score(
        &axes([5, 0, 0, 0, 0, 0, 0]),
        Estimate::Unknown,
        None,
        &uncertainty,
        &HashSet::new(),
        "express",
        None,
    )
    .unwrap();
    assert_eq!(result.urgency, 12.0);
    assert!(result.provisional);
}

#[test]
fn interview_is_strictly_sequential() {
    let mut session = InterviewSession::default();
    assert_eq!(session.next_question(), Some(Question::Subjective));
    session.subjective = Some(Priority::P2);
    session.mark_asked(Question::Subjective);
    assert_eq!(session.next_question(), Some(Question::Impact));
    session
        .answer_axis(Question::Impact, 3, Uncertainty::Certain)
        .unwrap();
    assert_eq!(session.next_question(), Some(Question::Inaction));
    session
        .answer_axis(Question::Inaction, 2, Uncertainty::Certain)
        .unwrap();
    assert_eq!(session.next_question(), Some(Question::Blockage));
}

#[test]
fn strategic_impact_is_independent_from_inaction() {
    let result = score(
        &axes([0, 0, 4, 1, 0, 0, 2]),
        Estimate::H1_2,
        None,
        &HashMap::new(),
        &HashSet::new(),
        "express",
        None,
    )
    .unwrap();
    assert_eq!(result.priority, Priority::P2);
    assert!(result.robust);
}

#[test]
fn uncertain_impact_reports_pivot_and_possible_quadrants() {
    let mut uncertainty = HashMap::new();
    uncertainty.insert(Axis::IMP, Uncertainty::Hesitant);
    let result = score(
        &axes([0, 0, 2, 1, 2, 0, 1]),
        Estimate::H1_2,
        None,
        &uncertainty,
        &HashSet::new(),
        "express",
        None,
    )
    .unwrap();
    assert!(!result.robust);
    assert_eq!(result.pivot_axis.as_deref(), Some("IMP"));
    assert_eq!(result.possible_quadrants, ["Q2", "Q4"]);
}

#[test]
fn planner_prioritizes_p1_and_deadlines() {
    let tasks = vec![
        PlanTask {
            task_id: 1,
            title: "P2 today".into(),
            priority: Priority::P2,
            global_score: 70.0,
            estimate_minutes: Some(30),
            effort: Effort::Medium,
            category: "work".into(),
            gem: false,
            deadline_days: Some(0),
            deadline: None,
        },
        PlanTask {
            task_id: 2,
            title: "P1".into(),
            priority: Priority::P1,
            global_score: 60.0,
            estimate_minutes: Some(30),
            effort: Effort::Medium,
            category: "work".into(),
            gem: false,
            deadline_days: None,
            deadline: None,
        },
    ];
    let plan = build_day_plan(&tasks, 120, 3);
    assert_eq!(plan.items.len(), 2);
    assert_eq!(plan.items[0].task.task_id, 2);
    assert_eq!(plan.usable_capacity_minutes, 96);
}
