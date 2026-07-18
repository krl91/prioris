"""Normalized scoring axes and planning attributes.

Pure module: no I/O, no external dependency.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# ---------------------------------------------------------------- axes score
class Axis(str, Enum):
    BLK = "BLK"  # real blockage           0..5
    CDR = "CDR"  # delay cost              0..4
    IMP = "IMP"  # impact                  0..4
    IRR = "IRR"  # irreversibility         0..3
    INA = "INA"  # one-month inaction      0..4
    HOR = "HOR"  # visibility horizon      0..4
    ALN = "ALN"  # goal alignment          0..3


AXIS_MAX: dict[Axis, int] = {
    Axis.BLK: 5, Axis.CDR: 4, Axis.IMP: 4, Axis.IRR: 3,
    Axis.INA: 4, Axis.HOR: 4, Axis.ALN: 3,
}

# Value used by the uncertainty dampener.
# Intentionally conservative for ALN/IRR to avoid inflating importance.
AXIS_MEDIAN: dict[Axis, int] = {
    Axis.BLK: 2, Axis.CDR: 2, Axis.IMP: 2, Axis.IRR: 1,
    Axis.INA: 2, Axis.HOR: 2, Axis.ALN: 1,
}

# Each label should be a natural answer to its axis question. It is both a UI
# button and the scale provided to the LLM for NLU.
AXIS_LABELS: dict[Axis, list[str]] = {
    Axis.BLK: ["Personne", "Moi seul", "Une autre personne",
               "Une équipe ou plusieurs personnes", "Un acteur critique",
               "Plusieurs équipes ou une chaîne critique"],
    Axis.CDR: ["Rien — le coût ne bouge pas", "Il s'accumule doucement",
               "Il s'accumule nettement", "Il s'aggrave de plus en plus",
               "Falaise : tout se joue à une date"],
    Axis.IMP: ["Négligeable", "Un peu de confort en plus",
               "Une différence notable", "Une différence majeure",
               "Structurant pour la suite"],
    Axis.IRR: ["Réversible à tout moment", "Rattrapable avec effort",
               "Rattrapable jusqu'à une date", "Irréversible"],
    Axis.INA: ["Rien du tout", "Une gêne", "Un vrai problème",
               "Une crise", "Des dégâts irrécupérables"],
    Axis.HOR: ["Jamais", "Dans plus d'un mois", "Dans 2 à 4 semaines",
               "Cette semaine", "C'est déjà visible"],
    Axis.ALN: ["Aucun objectif", "Contribution indirecte",
               "Contribution directe", "Contribution majeure"],
}

AXIS_QUESTIONS: dict[Axis, str] = {
    Axis.INA: "Si personne n'y touche pendant un mois, que se passe-t-il concrètement ?",
    Axis.BLK: "Qui est bloqué si ce n'est pas fait cette semaine ?",
    Axis.IMP: "Quelle différence réelle entre « fait » et « pas fait » ?",
    Axis.HOR: "Quand le problème deviendra-t-il visible ?",
    Axis.CDR: "Comment le coût évolue-t-il si tu attends ?",
    Axis.IRR: "Peut-on revenir en arrière ou rattraper plus tard ?",
    Axis.ALN: "Cette tâche contribue-t-elle à un de tes objectifs de vie ?",
}


class Incertitude(int, Enum):
    SUR = 0
    HESITANT = 1
    NE_SAIT_PAS = 2


# --------------------------------------------- planning attributes
class Estimation(str, Enum):
    LT15 = "<15 min"
    M15_30 = "15–30 min"
    M30_60 = "30–60 min"
    H1_2 = "1–2 h"
    H2_4 = "2–4 h"
    GT4 = ">4 h"
    INCONNUE = "inconnue"


# Median minutes. INCONNUE maps to 60, but the evaluation is provisional and
# the task is never scheduled in a plan.
ESTIMATION_MIN: dict[Estimation, int] = {
    Estimation.LT15: 10, Estimation.M15_30: 22, Estimation.M30_60: 45,
    Estimation.H1_2: 90, Estimation.H2_4: 180, Estimation.GT4: 300,
    Estimation.INCONNUE: 60,
}


class Effort(int, Enum):
    FAIBLE = 1
    MOYEN = 2
    ELEVE = 3


class Demandeur(str, Enum):
    MOI = "moi"
    COLLEGUE = "collegue"
    MANAGER = "manager"
    CLIENT = "client"


class Priorite(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"

    @property
    def niveau(self) -> int:
        return int(self.value[1])


# Quadrant legend used by renderers and buttons.
QUADRANT_INFO: dict[str, dict] = {
    "Q1": {"p": "P1", "emoji": "🔥", "nom": "Urgent et important",
           "action": "faire en premier"},
    "Q2": {"p": "P2", "emoji": "🎯", "nom": "Important, pas urgent",
           "action": "planifier — le quadrant des objectifs"},
    "Q3": {"p": "P3", "emoji": "⚡", "nom": "Urgent, pas important",
           "action": "déléguer ou traiter vite et petit"},
    "Q4": {"p": "P4", "emoji": "🗑", "nom": "Ni urgent ni important",
           "action": "reporter ou abandonner sans culpabilité"},
}

PRIORITE_LABELS: dict[Priorite, str] = {
    Priorite(info["p"]): f"{info['p']} {info['emoji']} {info['nom']}"
    for info in QUADRANT_INFO.values()
}


@dataclass(frozen=True)
class Metadata:
    """Metadata outside the score, used only by bias detection.

    In express interviews, these keep neutral defaults; dependent biases are
    simply not evaluated.
    """
    demandeur: Demandeur = Demandeur.MOI
    visibilite: int = 0          # 0..3
    pression: int = 0            # 0..3
    temps_investi_h: float = 0.0
    subjective: Priorite | None = None


# ----------------------------------------------- express defaults
def hor_from_deadline(deadline_days: int | None) -> int:
    """Derive HOR from the deadline in express mode. No deadline means median."""
    if deadline_days is None:
        return AXIS_MEDIAN[Axis.HOR]
    if deadline_days <= 0:
        return 4
    if deadline_days <= 7:
        return 3
    if deadline_days <= 30:
        return 2
    return 1


def express_defaults(deadline_days: int | None) -> dict[Axis, int]:
    """Deterministic defaults for axes not asked in express mode.

    IMP is deliberately absent: impact and inaction are independent concepts,
    so every interview asks IMP explicitly.
    """
    return {
        Axis.HOR: hor_from_deadline(deadline_days),
        Axis.IRR: 1,
    }
