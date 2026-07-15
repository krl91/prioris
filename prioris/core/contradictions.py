"""In-interview contradiction detection, rules C1-C6.

Pure functions. Clarification questions are static templates, no LLM involved.
"""
from __future__ import annotations

from dataclasses import dataclass

from .axes import Axis, Priorite


@dataclass(frozen=True)
class Contradiction:
    regle: str
    axes: tuple[str, ...]
    message: str
    # Prewritten clarification question: (text, [(label, corrected_axis, value)]).
    question: str
    options: tuple[tuple[str, str, int], ...]


def detect(axes: dict[Axis, int],
           subjective: Priorite | None = None,
           deadline_days: int | None = None) -> list[Contradiction]:
    """Return triggered rules. Accepts partial axes during an interview."""
    v = {a: axes.get(a) for a in Axis}
    found: list[Contradiction] = []

    def has(*needed: Axis) -> bool:
        return all(v[a] is not None for a in needed)

    if has(Axis.INA, Axis.CDR) and v[Axis.INA] <= 1 and v[Axis.CDR] >= 3:
        found.append(Contradiction(
            "C1", ("INA", "CDR"),
            "« Rien ne se passe si on ne fait rien » mais « le coût explose ».",
            "Tu dis que l'inaction est sans conséquence, mais que le coût du retard "
            "s'aggrave fortement. Laquelle des deux réalités est la bonne ?",
            (("L'inaction pose en fait un vrai problème", "INA", 2),
             ("Le coût du retard est en fait modéré", "CDR", 1),
             ("Je ne sais pas", "INA", 2))))
    if has(Axis.BLK, Axis.INA) and v[Axis.BLK] >= 4 and v[Axis.INA] <= 1:
        found.append(Contradiction(
            "C2", ("BLK", "INA"),
            "Le client/équipes seraient bloqués… sans conséquence.",
            "Le client serait bloqué, mais l'inaction resterait sans vraie conséquence. "
            "Est-il vraiment bloqué… ou en attente ?",
            (("Vraiment bloqué (et ça aura des conséquences)", "INA", 2),
             ("En attente, ça peut glisser", "BLK", 0),
             ("Je ne sais pas", "BLK", 2))))
    if has(Axis.HOR, Axis.INA) and v[Axis.HOR] >= 3 and v[Axis.INA] == 0:
        found.append(Contradiction(
            "C3", ("HOR", "INA"),
            "Visible cette semaine mais aucune conséquence.",
            "Le problème serait visible dès cette semaine, mais sans aucune conséquence. "
            "Visible pour qui, et avec quel effet réel ?",
            (("Il y aura bien une gêne réelle", "INA", 1),
             ("En fait personne ne le verra vraiment", "HOR", 1),
             ("Je ne sais pas", "INA", 1))))
    if has(Axis.IMP, Axis.INA) and v[Axis.IMP] >= 3 and v[Axis.INA] == 0:
        found.append(Contradiction(
            "C4", ("IMP", "INA"),
            "Impact majeur mais l'inaction ne coûte rien.",
            "Impact majeur… mais ne rien faire ne coûterait rien. Qu'est-ce qui rend "
            "cette tâche importante, concrètement ?",
            (("Ne rien faire aurait bien un coût", "INA", 2),
             ("L'impact est en fait plus modeste", "IMP", 1),
             ("Je ne sais pas", "IMP", 2))))
    if has(Axis.CDR) and v[Axis.CDR] == 4 and deadline_days is None:
        found.append(Contradiction(
            "C5", ("CDR",),
            "Falaise sans date : quelle est la vraie échéance ?",
            "Tu décris une deadline dure, mais aucune date n'est posée. "
            "Quelle est la vraie échéance ?",
            # "DATE" is a pseudo-axis: the bot asks for a free-form date.
            (("Je donne la date exacte", "DATE", 0),
             ("Pas de vraie date en fait", "CDR", 2),
             ("Je ne sais pas", "CDR", 3))))
    if (subjective == Priorite.P1 and has(Axis.BLK, Axis.CDR, Axis.INA)
            and v[Axis.BLK] == 0 and v[Axis.CDR] <= 1 and v[Axis.INA] <= 1):
        found.append(Contradiction(
            "C6", ("BLK", "CDR", "INA"),
            "Ressenti P1 sans aucun fondement objectif.",
            "Ton instinct dit P1, mais personne n'est bloqué, le retard ne coûte rien "
            "et l'inaction est sans conséquence. Qu'est-ce qui crée cette urgence ressentie ?",
            (("De la pression, pas des faits — je maintiens mes réponses", "BLK", 0),
             ("J'ai sous-estimé une conséquence", "INA", 2),
             ("Quelqu'un est en fait bloqué", "BLK", 2))))
    return found
