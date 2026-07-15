"""Small UI translation layer.

French remains the default. This module intentionally keeps all mappings close
to the UI adapters so the deterministic core does not depend on presentation
language.
"""
from __future__ import annotations

from .core import interview as itv
from .core.axes import Axis, Demandeur, Effort, Estimation, Priorite
from .core.interview import Q

Language = str


def normalize_language(value: str | None) -> Language:
    """Return a supported language code, defaulting to French."""
    lang = (value or "fr").strip().lower()
    return "en" if lang in {"en", "eng", "english"} else "fr"


AXIS_LABELS_I18N: dict[Language, dict[Axis, list[str]]] = {
    "fr": {
        Axis.BLK: ["Personne", "Moi seul", "Une autre personne", "Une équipe",
                   "Le client", "Plusieurs équipes"],
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
    },
    "en": {
        Axis.BLK: ["Nobody", "Only me", "One other person", "A team",
                   "The client", "Several teams"],
        Axis.CDR: ["Nothing, the cost does not change", "It slowly accumulates",
                   "It clearly accumulates", "It keeps getting worse",
                   "Cliff edge: everything depends on a date"],
        Axis.IMP: ["Negligible", "A little more comfort",
                   "A noticeable difference", "A major difference",
                   "Structuring for what comes next"],
        Axis.IRR: ["Reversible at any time", "Recoverable with effort",
                   "Recoverable until a date", "Irreversible"],
        Axis.INA: ["Nothing at all", "An annoyance", "A real problem",
                   "A crisis", "Irrecoverable damage"],
        Axis.HOR: ["Never", "In more than one month", "In 2 to 4 weeks",
                   "This week", "It is already visible"],
        Axis.ALN: ["No goal", "Indirect contribution",
                   "Direct contribution", "Major contribution"],
    },
}


AXIS_QUESTIONS_I18N: dict[Language, dict[Axis, str]] = {
    "fr": {
        Axis.INA: "Si personne n'y touche pendant un mois, que se passe-t-il concrètement ?",
        Axis.BLK: "Qui est bloqué si ce n'est pas fait cette semaine ?",
        Axis.IMP: "Quelle différence réelle entre « fait » et « pas fait » ?",
        Axis.HOR: "Quand le problème deviendra-t-il visible ?",
        Axis.CDR: "Comment le coût évolue-t-il si tu attends ?",
        Axis.IRR: "Peut-on revenir en arrière ou rattraper plus tard ?",
        Axis.ALN: "Cette tâche contribue-t-elle à un de tes objectifs de vie ?",
    },
    "en": {
        Axis.INA: "If nobody touches this for one month, what concretely happens?",
        Axis.BLK: "Who is blocked if this is not done this week?",
        Axis.IMP: "What is the real difference between done and not done?",
        Axis.HOR: "When will the problem become visible?",
        Axis.CDR: "How does the cost evolve if you wait?",
        Axis.IRR: "Can this be reversed or recovered later?",
        Axis.ALN: "Does this task contribute to one of your life goals?",
    },
}


QUADRANT_INFO_I18N: dict[Language, dict[str, dict[str, str]]] = {
    "fr": {
        "Q1": {"p": "P1", "emoji": "🔥", "nom": "Urgent et important",
               "action": "faire en premier"},
        "Q2": {"p": "P2", "emoji": "🎯", "nom": "Important, pas urgent",
               "action": "planifier — le quadrant des objectifs"},
        "Q3": {"p": "P3", "emoji": "⚡", "nom": "Urgent, pas important",
               "action": "déléguer ou traiter vite et petit"},
        "Q4": {"p": "P4", "emoji": "🗑", "nom": "Ni urgent ni important",
               "action": "reporter ou abandonner sans culpabilité"},
    },
    "en": {
        "Q1": {"p": "P1", "emoji": "🔥", "nom": "Urgent and important",
               "action": "do first"},
        "Q2": {"p": "P2", "emoji": "🎯", "nom": "Important, not urgent",
               "action": "schedule"},
        "Q3": {"p": "P3", "emoji": "⚡", "nom": "Urgent, not important",
               "action": "delegate or handle small and fast"},
        "Q4": {"p": "P4", "emoji": "🗑", "nom": "Neither urgent nor important",
               "action": "defer or drop without guilt"},
    },
}


UI_TEXT: dict[Language, dict[str, str]] = {
    "fr": {
        "subjective": "Instinctivement, tu la classes comment ?",
        "estimate": "Temps nécessaire, réalistement ?",
        "effort": "Quel effort cognitif demande-t-elle ?",
        "requester": "Qui demande cette tâche ?",
        "visibility": "À quel point est-elle visible (réunions, mails, relances) ?",
        "pressure": "Quelle pression ressens-tu dessus ?",
        "unknown": "🤷 Je ne sais pas",
        "low": "Faible",
        "medium": "Moyen",
        "high": "Élevé",
        "none": "Nulle",
        "me": "Moi",
        "colleague": "Collègue",
        "manager": "Manager",
        "client": "Client",
        "quadrant_helper_title": "Questions pour situer le quadrant :",
    },
    "en": {
        "subjective": "Instinctively, how would you classify it?",
        "estimate": "How much time does it realistically need?",
        "effort": "How much cognitive effort does it require?",
        "requester": "Who is asking for this task?",
        "visibility": "How visible is it (meetings, emails, reminders)?",
        "pressure": "How much pressure do you feel about it?",
        "unknown": "🤷 I don't know",
        "low": "Low",
        "medium": "Medium",
        "high": "High",
        "none": "None",
        "me": "Me",
        "colleague": "Colleague",
        "manager": "Manager",
        "client": "Client",
        "quadrant_helper_title": "Questions to locate the quadrant:",
    },
}


def t(key: str, language: str | None = None) -> str:
    """Translate a short UI key."""
    lang = normalize_language(language)
    return UI_TEXT[lang].get(key, UI_TEXT["fr"][key])


def question_text(q: Q, language: str | None = None) -> str:
    """Return the translated interview question text."""
    lang = normalize_language(language)
    if q == Q.SUBJECTIVE:
        return t("subjective", lang)
    if q == Q.ESTIMATION:
        return t("estimate", lang)
    if q == Q.EFFORT:
        return t("effort", lang)
    if q == Q.DEMANDEUR:
        return t("requester", lang)
    if q == Q.VISIBILITE:
        return t("visibility", lang)
    if q == Q.PRESSION:
        return t("pressure", lang)
    if q in itv.Q_TO_AXIS:
        return AXIS_QUESTIONS_I18N[lang][itv.Q_TO_AXIS[q]]
    return q.value


def axis_labels(axis: Axis, language: str | None = None) -> list[str]:
    """Return translated labels for an axis scale."""
    return AXIS_LABELS_I18N[normalize_language(language)][axis]


def priority_labels(language: str | None = None) -> dict[Priorite, str]:
    """Return translated P1-P4 labels."""
    info = QUADRANT_INFO_I18N[normalize_language(language)]
    return {
        Priorite(row["p"]): f"{row['p']} {row['emoji']} {row['nom']}"
        for row in info.values()
    }


def options(q: Q, language: str | None = None) -> list[tuple[str, str]]:
    """Return encoded translated options for an interview question."""
    lang = normalize_language(language)
    if q == Q.SUBJECTIVE:
        labels = priority_labels(lang)
        return [(labels[p], p.value) for p in Priorite]
    if q == Q.ESTIMATION:
        return [(e.value, e.name) for e in Estimation]
    if q == Q.EFFORT:
        return [(t("low", lang), str(Effort.FAIBLE.value)),
                (t("medium", lang), str(Effort.MOYEN.value)),
                (t("high", lang), str(Effort.ELEVE.value))]
    if q == Q.DEMANDEUR:
        return [(t("me", lang), Demandeur.MOI.value),
                (t("colleague", lang), Demandeur.COLLEGUE.value),
                (t("manager", lang), Demandeur.MANAGER.value),
                (t("client", lang), Demandeur.CLIENT.value)]
    if q in (Q.VISIBILITE, Q.PRESSION):
        return [(t("none", lang), "0"), (t("low", lang), "1"),
                (t("medium", lang), "2"), (t("high", lang), "3")]
    axis = itv.Q_TO_AXIS[q]
    opts = [(label, str(i)) for i, label in enumerate(axis_labels(axis, lang))]
    opts.append((t("unknown", lang), "?"))
    return opts
