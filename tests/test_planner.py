"""Tests du planificateur (§8, §12.1) — invariants et cas dégénérés."""
from prioris.core.axes import Effort, Priorite
from prioris.core.planner import MARGE_CAPACITE, PlanTask, build_day_plan


def task(i, prio, g, est=45, eff=Effort.MOYEN, cat="travail", pepite=False):
    return PlanTask(i, f"T{i}", prio, g, est, eff, cat, pepite)


def task_due(i, prio, g, days, est=45):
    return PlanTask(i, f"T{i}", prio, g, est, Effort.MOYEN, "travail",
                    False, days, f"2026-07-{15 + days:02d}")


def test_capacite_jamais_depassee():
    tasks = [task(i, Priorite.P2, 60 - i, est=90) for i in range(10)]
    plan = build_day_plan(tasks, capacite_min=240, energie=3)
    assert sum(it.duree_min for it in plan.items) <= int(240 * MARGE_CAPACITE)


def test_p1_toujours_inclus_p4_jamais():
    tasks = [task(1, Priorite.P4, 90), task(2, Priorite.P1, 40),
             task(3, Priorite.P2, 80)]
    plan = build_day_plan(tasks, capacite_min=480, energie=3)
    ids = [it.task.task_id for it in plan.items]
    assert 2 in ids and 1 not in ids
    assert ids[0] == 2  # P1 d'abord
    assert any(t.task_id == 1 and "P4" in raison for t, raison in plan.exclues)


def test_max_3_majeures():
    tasks = [task(i, Priorite.P2, 70, est=90) for i in range(6)]
    plan = build_day_plan(tasks, capacite_min=1200, energie=3)
    majeures = [it for it in plan.items if it.duree_min >= 60 or
                it.task.effort == Effort.ELEVE]
    assert len(majeures) <= 3


def test_energie_tres_faible_exclut_eff3():
    tasks = [task(1, Priorite.P2, 90, eff=Effort.ELEVE),
             task(2, Priorite.P2, 50, eff=Effort.FAIBLE)]
    plan = build_day_plan(tasks, capacite_min=240, energie=1)
    ids = [it.task.task_id for it in plan.items]
    assert 1 not in ids and 2 in ids


def test_p1_incompatible_signale_mais_inclus():
    """§8.4 : un vrai P1 reste un P1, avec avertissement."""
    tasks = [task(1, Priorite.P1, 80, eff=Effort.ELEVE)]
    plan = build_day_plan(tasks, capacite_min=240, energie=1)
    assert [it.task.task_id for it in plan.items] == [1]
    assert plan.avertissements


def test_estimation_inconnue_jamais_planifiee():
    tasks = [task(1, Priorite.P2, 90, est=None)]
    plan = build_day_plan(tasks, capacite_min=240, energie=3)
    assert not plan.items
    assert "estimation inconnue" in plan.exclues[0][1]


def test_decoupage_entamer():
    """Tâche trop grosse mais G ≥ 60 → tranche de 60 min."""
    tasks = [task(1, Priorite.P2, 75, est=300)]
    plan = build_day_plan(tasks, capacite_min=120, energie=3)  # utile = 96
    assert plan.items[0].entamer and plan.items[0].duree_min == 60


def test_pepite_bonus_ordre():
    """À G proche, la pépite passe devant (§6.6 : bonus +10)."""
    tasks = [task(1, Priorite.P2, 55, est=30),
             task(2, Priorite.P2, 60, est=30, pepite=True)]
    plan = build_day_plan(tasks, capacite_min=60, energie=3)  # utile = 48 → 1 seule
    assert plan.items[0].task.task_id == 2


def test_echeance_proche_concurrence_la_note():
    tasks = [task_due(1, Priorite.P2, 72, 30),
             task_due(2, Priorite.P2, 55, 1)]
    plan = build_day_plan(tasks, capacite_min=60, energie=3)
    assert plan.items[0].task.task_id == 2
    assert "échéance" in plan.items[0].note


def test_echeance_ne_rend_pas_une_p4_planifiable():
    tasks = [task_due(1, Priorite.P4, 90, 0),
             task(2, Priorite.P2, 50)]
    plan = build_day_plan(tasks, capacite_min=240, energie=3)
    assert 1 not in [i.task.task_id for i in plan.items]
    assert any(t.task_id == 1 and "P4" in raison for t, raison in plan.exclues)


def test_cas_degeneres():
    assert build_day_plan([], 240, 3).items == ()
    plan = build_day_plan([task(1, Priorite.P2, 50)], 0, 3)
    assert not plan.items
    plan = build_day_plan([task(1, Priorite.P4, 50)], 240, 3)
    assert not plan.items and plan.sacrifiees == ()


def test_determinisme():
    tasks = [task(i, Priorite.P2, 50 + i % 3, est=30) for i in range(8)]
    p1 = build_day_plan(tasks, 240, 3)
    p2 = build_day_plan(tasks, 240, 3)
    assert [i.task.task_id for i in p1.items] == [i.task.task_id for i in p2.items]
