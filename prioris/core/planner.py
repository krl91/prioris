"""Daily-plan planner: one balanced deterministic scenario.

Weighted greedy selection under constraints. Realism rules: usable capacity is
80%, at most three major tasks, energy constraints are respected, unknown
estimates are never planned, P4 is never planned, and P1 tasks are considered
first.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .axes import Effort, Priorite

MARGE_CAPACITE = 0.8
MAX_MAJEURES = 3
SEUIL_MAJEURE_MIN = 60
BONUS_PEPITE = 10
TRANCHE_ENTAMER_MIN = 60
SEUIL_ENTAMER_G = 60
DEADLINE_BONUS = (
    (0, 40),    # overdue or today
    (1, 35),
    (3, 28),
    (7, 20),
    (14, 12),
    (30, 6),
)


@dataclass(frozen=True)
class PlanTask:
    task_id: int
    titre: str
    priorite: Priorite
    score_global: float
    est_min: int | None          # None means unknown estimate
    effort: Effort
    categorie: str
    pepite: bool = False
    deadline_days: int | None = None
    deadline: str | None = None


@dataclass(frozen=True)
class PlanItem:
    task: PlanTask
    duree_min: int
    entamer: bool = False        # partial "start with ..." slice
    note: str = ""


@dataclass(frozen=True)
class Plan:
    items: tuple[PlanItem, ...]
    sacrifiees: tuple[PlanTask, ...]     # evaluated but not selected
    exclues: tuple[tuple[PlanTask, str], ...]  # ineligible plus reason
    capacite_utile_min: int
    minutes_par_categorie: dict = field(default_factory=dict)
    avertissements: tuple[str, ...] = ()


def _energy_adjustment(energie: int, effort: Effort) -> int | None:
    """Energy matrix. None means excluded; otherwise bonus/malus on value."""
    if energie <= 1:
        return {Effort.FAIBLE: 0, Effort.MOYEN: -25, Effort.ELEVE: None}[effort]
    if energie == 2:
        return {Effort.FAIBLE: 0, Effort.MOYEN: 0, Effort.ELEVE: -25}[effort]
    if energie == 3:
        return 0
    return {Effort.FAIBLE: -10, Effort.MOYEN: 0, Effort.ELEVE: +10}[effort]


def _majeure(t: PlanTask) -> bool:
    return (t.est_min or 0) >= SEUIL_MAJEURE_MIN or t.effort == Effort.ELEVE


def _deadline_bonus(t: PlanTask) -> int:
    if t.deadline_days is None:
        return 0
    for max_days, bonus in DEADLINE_BONUS:
        if t.deadline_days <= max_days:
            return bonus
    return 0


def _deadline_note(t: PlanTask) -> str:
    if t.deadline_days is None:
        return ""
    if t.deadline_days < 0:
        return f"échéance dépassée ({t.deadline})" if t.deadline else "échéance dépassée"
    if t.deadline_days == 0:
        return f"échéance aujourd'hui ({t.deadline})" if t.deadline else "échéance aujourd'hui"
    return f"échéance J-{t.deadline_days}" + (f" ({t.deadline})" if t.deadline else "")


def build_day_plan(tasks: list[PlanTask], capacite_min: int, energie: int) -> Plan:
    """Build the daily plan. Energy ranges from 1 very low to 5 excellent."""
    capacite_utile = int(capacite_min * MARGE_CAPACITE)
    restant = capacite_utile
    items: list[PlanItem] = []
    exclues: list[tuple[PlanTask, str]] = []
    avert: list[str] = []
    majeures = 0

    def eligible(t: PlanTask) -> str | None:
        if t.priorite == Priorite.P4:
            return "P4 : jamais planifié (candidate à /abandon)"
        if t.est_min is None:
            return "estimation inconnue : à estimer avant de planifier"
        return None

    def try_add(t: PlanTask, forced_p1: bool) -> None:
        nonlocal restant, majeures
        adj = _energy_adjustment(energie, t.effort)
        if adj is None and not forced_p1:
            exclues.append((t, "effort incompatible avec l'énergie du jour"))
            return
        if _majeure(t) and majeures >= MAX_MAJEURES:
            exclues.append((t, f"max {MAX_MAJEURES} tâches majeures atteint"))
            return
        note = ""
        if adj is None and forced_p1:
            note = "P1 exigeant + énergie très faible : commence par 25 min, ou re-négocie la deadline"
            avert.append(f"« {t.titre} » : {note}")
        deadline_note = _deadline_note(t)
        if deadline_note and _deadline_bonus(t):
            note = f"{note} · {deadline_note}".strip(" ·")
        if t.est_min <= restant:
            items.append(PlanItem(t, t.est_min, note=note))
            restant -= t.est_min
            majeures += _majeure(t)
        elif t.score_global >= SEUIL_ENTAMER_G and restant >= TRANCHE_ENTAMER_MIN:
            items.append(PlanItem(t, TRANCHE_ENTAMER_MIN, entamer=True, note=note))
            restant -= TRANCHE_ENTAMER_MIN
            majeures += _majeure(t)
        else:
            exclues.append((t, "capacité restante insuffisante"))

    def value(t: PlanTask) -> float:
        v = (t.score_global
             + (BONUS_PEPITE if t.pepite else 0)
             + _deadline_bonus(t))
        adj = _energy_adjustment(energie, t.effort)
        return v + (adj or 0)

    # 1. P1 always first; no profile can evict them. Sort by decreasing value.
    pool: list[PlanTask] = []
    for t in tasks:
        raison = eligible(t)
        if raison:
            exclues.append((t, raison))
        elif t.priorite == Priorite.P1:
            pool.append(t)
    for t in sorted(pool, key=lambda t: (-value(t), t.task_id)):
        try_add(t, forced_p1=True)

    # 2. Greedy fill by decreasing value.
    rest = [t for t in tasks if t.priorite in (Priorite.P2, Priorite.P3)
            and eligible(t) is None]
    for t in sorted(rest, key=lambda t: (-value(t), t.task_id)):
        if restant <= 0:
            break
        try_add(t, forced_p1=False)

    planned_ids = {i.task.task_id for i in items}
    excl_ids = {t.task_id for t, _ in exclues}
    sacrifiees = tuple(t for t in tasks
                       if t.task_id not in planned_ids and t.task_id not in excl_ids)
    minutes: dict[str, int] = {}
    for i in items:
        minutes[i.task.categorie] = minutes.get(i.task.categorie, 0) + i.duree_min

    total = sum(i.duree_min for i in items)
    assert total <= capacite_utile, "invariant : capacité utile jamais dépassée"
    return Plan(tuple(items), sacrifiees, tuple(exclues),
                capacite_utile, minutes, tuple(avert))
