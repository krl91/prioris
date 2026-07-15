"""Mirror questions: systematic probes that test answer robustness.

One per interview, selected deterministically from applicable probes using the
task id as seed. As everywhere else, an answer can adjust an axis, never the
score. Pure module.
"""
from __future__ import annotations

from dataclasses import dataclass

from .axes import Axis, Priorite


@dataclass(frozen=True)
class MirrorOption:
    label: str
    axe: str = ""            # empty means coherent answer, no axis corrected
    valeur: int = 0
    incertain: bool = False


@dataclass(frozen=True)
class MirrorQuestion:
    code: str
    question: str
    options: tuple[MirrorOption, ...]


_PROBES: list[tuple] = [
    # (code, condition(axes, subjective), question, options)
    ("M1_INA",
     lambda a, s: a.get(Axis.INA, 99) <= 1,
     "Serais-tu surpris qu'on te demande des comptes sur ce sujet dans 15 jours ?",
     (MirrorOption("Oui, très surpris — vraiment sans enjeu"),
      MirrorOption("Non, pas surpris… il y a un enjeu en fait", "INA", 2),
      MirrorOption("Je ne sais pas", "INA", 2, incertain=True))),
    ("M2_IMP",
     lambda a, s: a.get(Axis.IMP, -1) >= 3,
     "Si tu quittais l'entreprise demain, quelqu'un reprendrait-il "
     "cette tâche en priorité ?",
     (MirrorOption("Oui, clairement"),
      MirrorOption("Non, personne ne la reprendrait", "IMP", 1),
      MirrorOption("Je ne sais pas", "IMP", 2, incertain=True))),
    ("M3_BLK",
     lambda a, s: a.get(Axis.BLK, -1) >= 3,
     "La personne ou l'équipe bloquée t'a-t-elle relancé cette semaine ?",
     (MirrorOption("Oui, relancé"),
      MirrorOption("Non, aucune relance", "BLK", 2),
      MirrorOption("Je ne sais pas", "BLK", 2, incertain=True))),
    ("M4_P1",
     lambda a, s: s == Priorite.P1,
     "Si tu la faisais la semaine prochaine plutôt que demain, "
     "que se passerait-il concrètement ?",
     (MirrorOption("Un vrai problème"),
      MirrorOption("Rien de grave, en fait", "CDR", 1),
      MirrorOption("Je ne sais pas", "CDR", 2, incertain=True))),
]


def select_mirror(axes: dict, subjective: Priorite | None,
                  seed: int) -> MirrorQuestion | None:
    """Return the deterministic probe for these answers and seed."""
    applicable = [(code, q, opts) for code, cond, q, opts in _PROBES
                  if cond(axes, subjective)]
    if not applicable:
        return None
    code, question, options = applicable[seed % len(applicable)]
    return MirrorQuestion(code, question, options)
