use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Axis {
    BLK,
    CDR,
    IMP,
    IRR,
    INA,
    HOR,
    ALN,
}

impl Axis {
    pub const ALL: [Self; 7] = [
        Self::BLK,
        Self::CDR,
        Self::IMP,
        Self::IRR,
        Self::INA,
        Self::HOR,
        Self::ALN,
    ];

    pub const fn code(self) -> &'static str {
        match self {
            Self::BLK => "BLK",
            Self::CDR => "CDR",
            Self::IMP => "IMP",
            Self::IRR => "IRR",
            Self::INA => "INA",
            Self::HOR => "HOR",
            Self::ALN => "ALN",
        }
    }

    pub const fn max(self) -> u8 {
        match self {
            Self::BLK => 5,
            Self::CDR | Self::IMP | Self::INA | Self::HOR => 4,
            Self::IRR | Self::ALN => 3,
        }
    }

    pub const fn median(self) -> u8 {
        match self {
            Self::BLK | Self::CDR | Self::IMP | Self::INA | Self::HOR => 2,
            Self::IRR | Self::ALN => 1,
        }
    }

    pub const fn question_fr(self) -> &'static str {
        match self {
            Self::INA => "Si personne n'y touche pendant un mois, que se passe-t-il concrètement ?",
            Self::BLK => "Qui est bloqué si ce n'est pas fait cette semaine ?",
            Self::IMP => "Quelle différence réelle entre fait et pas fait ?",
            Self::HOR => "Quand le problème deviendra-t-il visible ?",
            Self::CDR => "Comment le coût évolue-t-il si tu attends ?",
            Self::IRR => "Peut-on revenir en arrière ou rattraper plus tard ?",
            Self::ALN => "Cette tâche contribue-t-elle à un de tes objectifs de vie ?",
        }
    }

    pub const fn labels_fr(self) -> &'static [&'static str] {
        match self {
            Self::BLK => &[
                "Personne",
                "Moi seul",
                "Une autre personne",
                "Une équipe ou plusieurs personnes",
                "Un acteur critique",
                "Plusieurs équipes ou une chaîne critique",
            ],
            Self::CDR => &[
                "Rien",
                "Il s'accumule doucement",
                "Il s'accumule nettement",
                "Il s'aggrave",
                "Falaise à une date",
            ],
            Self::IMP => &[
                "Négligeable",
                "Un peu de confort",
                "Différence notable",
                "Différence majeure",
                "Structurant",
            ],
            Self::IRR => &[
                "Réversible",
                "Rattrapable avec effort",
                "Rattrapable jusqu'à une date",
                "Irréversible",
            ],
            Self::INA => &[
                "Rien",
                "Une gêne",
                "Un vrai problème",
                "Une crise",
                "Dégâts irrécupérables",
            ],
            Self::HOR => &[
                "Jamais",
                "Dans plus d'un mois",
                "Dans 2 à 4 semaines",
                "Cette semaine",
                "Déjà visible",
            ],
            Self::ALN => &[
                "Aucun objectif",
                "Contribution indirecte",
                "Contribution directe",
                "Contribution majeure",
            ],
        }
    }
}

impl std::str::FromStr for Axis {
    type Err = String;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        Self::ALL
            .into_iter()
            .find(|axis| axis.code().eq_ignore_ascii_case(value))
            .ok_or_else(|| format!("unknown axis: {value}"))
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
#[repr(u8)]
pub enum Uncertainty {
    #[default]
    Certain = 0,
    Hesitant = 1,
    Unknown = 2,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
pub enum Estimate {
    Lt15,
    M15_30,
    M30_60,
    H1_2,
    H2_4,
    Gt4,
    #[default]
    Unknown,
}

impl Estimate {
    pub const fn minutes(self) -> u32 {
        match self {
            Self::Lt15 => 10,
            Self::M15_30 => 22,
            Self::M30_60 => 45,
            Self::H1_2 => 90,
            Self::H2_4 => 180,
            Self::Gt4 => 300,
            Self::Unknown => 60,
        }
    }

    pub const fn db_value(self) -> &'static str {
        match self {
            Self::Lt15 => "<15 min",
            Self::M15_30 => "15–30 min",
            Self::M30_60 => "30–60 min",
            Self::H1_2 => "1–2 h",
            Self::H2_4 => "2–4 h",
            Self::Gt4 => ">4 h",
            Self::Unknown => "inconnue",
        }
    }
}

impl std::str::FromStr for Estimate {
    type Err = String;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        match value {
            "<15 min" => Ok(Self::Lt15),
            "15–30 min" | "15-30 min" => Ok(Self::M15_30),
            "30–60 min" | "30-60 min" => Ok(Self::M30_60),
            "1–2 h" | "1-2 h" => Ok(Self::H1_2),
            "2–4 h" | "2-4 h" => Ok(Self::H2_4),
            ">4 h" => Ok(Self::Gt4),
            "inconnue" | "unknown" | "" => Ok(Self::Unknown),
            _ => Err(format!("unknown estimate: {value}")),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
#[repr(u8)]
pub enum Effort {
    Low = 1,
    #[default]
    Medium = 2,
    High = 3,
}

impl Effort {
    pub fn from_u8(value: u8) -> Self {
        match value {
            1 => Self::Low,
            3 => Self::High,
            _ => Self::Medium,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Priority {
    P1,
    P2,
    P3,
    P4,
}

impl Priority {
    pub const fn level(self) -> i8 {
        match self {
            Self::P1 => 1,
            Self::P2 => 2,
            Self::P3 => 3,
            Self::P4 => 4,
        }
    }

    pub const fn as_str(self) -> &'static str {
        match self {
            Self::P1 => "P1",
            Self::P2 => "P2",
            Self::P3 => "P3",
            Self::P4 => "P4",
        }
    }
}

impl std::str::FromStr for Priority {
    type Err = String;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        match value.to_ascii_uppercase().as_str() {
            "P1" => Ok(Self::P1),
            "P2" => Ok(Self::P2),
            "P3" => Ok(Self::P3),
            "P4" => Ok(Self::P4),
            _ => Err(format!("unknown priority: {value}")),
        }
    }
}

pub fn horizon_from_deadline(deadline_days: Option<i64>) -> u8 {
    match deadline_days {
        None => Axis::HOR.median(),
        Some(days) if days <= 0 => 4,
        Some(days) if days <= 7 => 3,
        Some(days) if days <= 30 => 2,
        Some(_) => 1,
    }
}
