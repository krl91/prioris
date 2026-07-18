use std::collections::{HashMap, HashSet};

use serde::{Deserialize, Serialize};

use super::{Axis, Estimate, Priority, Uncertainty, horizon_from_deadline};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Question {
    Subjective,
    Inaction,
    Blockage,
    DelayCost,
    Goal,
    Estimate,
    Impact,
    Horizon,
    Irreversibility,
    Effort,
    Requester,
    Visibility,
    Pressure,
}

const EXPRESS_FLOW: [Question; 6] = [
    Question::Subjective,
    Question::Inaction,
    Question::Blockage,
    Question::DelayCost,
    Question::Goal,
    Question::Estimate,
];
const FULL_EXTRA: [Question; 7] = [
    Question::Impact,
    Question::Horizon,
    Question::Irreversibility,
    Question::Effort,
    Question::Requester,
    Question::Visibility,
    Question::Pressure,
];

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InterviewSession {
    pub deadline_days: Option<i64>,
    pub full_mode: bool,
    pub asked: Vec<Question>,
    pub axes: HashMap<Axis, u8>,
    pub uncertainties: HashMap<Axis, Uncertainty>,
    pub subjective: Option<Priority>,
    pub estimate: Option<Estimate>,
    pub effort: u8,
    pub requester: String,
    pub visibility: u8,
    pub pressure: u8,
}

impl Default for InterviewSession {
    fn default() -> Self {
        Self {
            deadline_days: None,
            full_mode: false,
            asked: Vec::new(),
            axes: HashMap::new(),
            uncertainties: HashMap::new(),
            subjective: None,
            estimate: None,
            effort: 2,
            requester: "moi".to_owned(),
            visibility: 0,
            pressure: 0,
        }
    }
}

impl InterviewSession {
    pub fn next_question(&mut self) -> Option<Question> {
        if self.subjective == Some(Priority::P1)
            || self.axes.get(&Axis::INA).is_some_and(|value| *value >= 3)
            || self.deadline_days.is_some_and(|days| days < 7)
        {
            self.full_mode = true;
        }
        EXPRESS_FLOW
            .iter()
            .chain(
                self.full_mode
                    .then_some(FULL_EXTRA.iter())
                    .into_iter()
                    .flatten(),
            )
            .copied()
            .find(|question| !self.asked.contains(question))
    }

    pub fn answer_axis(
        &mut self,
        question: Question,
        value: u8,
        uncertainty: Uncertainty,
    ) -> Result<(), String> {
        let axis =
            question_axis(question).ok_or_else(|| "question is not an axis question".to_owned())?;
        if value > axis.max() {
            return Err(format!(
                "{} must be between 0 and {}",
                axis.code(),
                axis.max()
            ));
        }
        self.axes.insert(axis, value);
        self.uncertainties.insert(axis, uncertainty);
        self.mark_asked(question);
        Ok(())
    }

    pub fn set_axis_probe(
        &mut self,
        axis: Axis,
        value: u8,
        uncertainty: Uncertainty,
    ) -> Result<(), String> {
        if value > axis.max() {
            return Err(format!(
                "{} must be between 0 and {}",
                axis.code(),
                axis.max()
            ));
        }
        self.axes.insert(axis, value);
        self.uncertainties.insert(axis, uncertainty);
        Ok(())
    }

    pub fn mark_asked(&mut self, question: Question) {
        if !self.asked.contains(&question) {
            self.asked.push(question);
        }
    }

    pub fn final_axes(&self) -> (HashMap<Axis, u8>, HashSet<Axis>) {
        let mut axes = self.axes.clone();
        let mut defaulted = HashSet::new();
        for (axis, value) in [
            (Axis::HOR, horizon_from_deadline(self.deadline_days)),
            (Axis::IRR, 1),
            (
                Axis::IMP,
                self.axes.get(&Axis::INA).copied().unwrap_or(0).min(3),
            ),
            (Axis::ALN, 0),
        ] {
            if let std::collections::hash_map::Entry::Vacant(entry) = axes.entry(axis) {
                entry.insert(value);
                defaulted.insert(axis);
            }
        }
        (axes, defaulted)
    }
}

pub fn question_axis(question: Question) -> Option<Axis> {
    match question {
        Question::Inaction => Some(Axis::INA),
        Question::Blockage => Some(Axis::BLK),
        Question::DelayCost => Some(Axis::CDR),
        Question::Goal => Some(Axis::ALN),
        Question::Impact => Some(Axis::IMP),
        Question::Horizon => Some(Axis::HOR),
        Question::Irreversibility => Some(Axis::IRR),
        _ => None,
    }
}
