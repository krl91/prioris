"""Deterministic bias detection (§7.3), MVP rules: 1-4, 7, 9.

Delta = calculated priority - subjective priority; positive means the user
overestimates the task. Pressure, visibility, and requester never affect the
score directly: they are used only here.
"""
from __future__ import annotations

from dataclasses import dataclass

from .axes import Axis, Demandeur, Metadata, Priorite


@dataclass(frozen=True)
class BiasFlag:
    type_biais: str
    gravite: str          # info | moyen | fort
    preuve: dict
    message: str


def _gravite(ecart: int) -> str:
    return "fort" if ecart >= 2 else "moyen" if ecart == 1 else "info"


def detect(axes: dict[Axis, int],
           importance: float,
           calculee: Priorite,
           meta: Metadata) -> list[BiasFlag]:
    flags: list[BiasFlag] = []
    ecart = (calculee.niveau - meta.subjective.niveau) if meta.subjective else 0

    if ecart >= 1 and axes[Axis.CDR] <= 1 and axes[Axis.HOR] <= 2:
        flags.append(BiasFlag(
            "urgence", _gravite(ecart),
            {"ecart": ecart, "CDR": axes[Axis.CDR], "HOR": axes[Axis.HOR]},
            "Urgence ressentie sans échéance réelle : le retard ne coûte presque rien "
            "et rien ne sera visible avant des semaines."))
    if ecart >= 1 and meta.visibilite >= 2 and importance < 50:
        flags.append(BiasFlag(
            "visibilite", _gravite(ecart),
            {"ecart": ecart, "visibilite": meta.visibilite, "I": round(importance, 1)},
            "Tâche très visible mais peu importante : la visibilité n'est pas la priorité."))
    if ecart >= 1 and meta.demandeur == Demandeur.MANAGER and axes[Axis.BLK] <= 2:
        flags.append(BiasFlag(
            "hierarchique", _gravite(ecart),
            {"ecart": ecart, "demandeur": "manager", "BLK": axes[Axis.BLK]},
            "Demande hiérarchique sans blocage réel : qui attend concrètement quoi ?"))
    if (ecart >= 1 and meta.demandeur == Demandeur.CLIENT
            and axes[Axis.BLK] <= 3 and axes[Axis.CDR] <= 2):
        flags.append(BiasFlag(
            "client", _gravite(ecart),
            {"ecart": ecart, "demandeur": "client", "BLK": axes[Axis.BLK],
             "CDR": axes[Axis.CDR]},
            "Demande client ≠ criticité : pas de blocage fort ni de coût du retard réel."))
    if meta.pression >= 2 and axes[Axis.BLK] <= 1 and axes[Axis.INA] <= 1:
        flags.append(BiasFlag(
            "culpabilite", "moyen" if ecart < 2 else "fort",
            {"pression": meta.pression, "BLK": axes[Axis.BLK], "INA": axes[Axis.INA]},
            "Forte pression ressentie sur une tâche objectivement mineure : "
            "peur de décevoir plutôt qu'enjeu réel."))
    if meta.visibilite >= 2 and axes[Axis.INA] <= 1 and axes[Axis.IMP] <= 1:
        flags.append(BiasFlag(
            "bruit", "info" if ecart < 1 else _gravite(ecart),
            {"visibilite": meta.visibilite, "INA": axes[Axis.INA], "IMP": axes[Axis.IMP]},
            "Beaucoup de discussions, peu de conséquences : du bruit, pas de l'impact."))
    return flags
