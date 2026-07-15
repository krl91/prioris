"""Tests des questions miroir (§7.2) et des objectifs /goals (v0.4.0)."""
from prioris.core import interview as itv
from prioris.core.axes import Axis, Incertitude, Priorite
from prioris.core.interview import Q, Session
from prioris.core.mirror import select_mirror
from prioris.store import db
from tests.test_interview import EXPRESS_ANSWERS, FULL_ANSWERS, run_until


# ------------------------------------------------------------------ miroir
def test_selection_deterministe_et_seedee():
    axes = {Axis.INA: 1, Axis.IMP: 3}          # M1 et M2 applicables
    m_seed0 = select_mirror(axes, None, seed=0)
    m_seed1 = select_mirror(axes, None, seed=1)
    assert m_seed0.code == "M1_INA" and m_seed1.code == "M2_IMP"
    # même seed ⇒ toujours la même sonde
    assert select_mirror(axes, None, 0).code == m_seed0.code


def test_aucune_sonde_si_rien_d_applicable():
    axes = {Axis.INA: 2, Axis.IMP: 2, Axis.BLK: 1}
    assert select_mirror(axes, Priorite.P3, 0) is None
    answers = {**FULL_ANSWERS, Q.INACTION: 2}
    asked, s = run_until(Session(), answers)
    assert Q.MIROIR not in asked and not s.mirror_done


def test_une_seule_sonde_par_entretien():
    asked, s = run_until(Session(), EXPRESS_ANSWERS)   # INA=1 ⇒ M1
    assert asked.count(Q.MIROIR) == 1
    q, _ = itv.next_question(s)
    assert q is None                                    # pas de 2e sonde


def test_reponse_coherente_ne_change_rien():
    _, s = run_until(Session(), EXPRESS_ANSWERS, mirror_choice=0)
    assert s.axes[Axis.INA] == 1                        # inchangé


def test_reponse_contradictoire_corrige_l_axe():
    """« Pas surpris qu'on me demande des comptes » ⇒ INA relevée à 2."""
    _, s = run_until(Session(), EXPRESS_ANSWERS, mirror_choice=1)
    assert s.axes[Axis.INA] == 2


def test_je_ne_sais_pas_marque_incertitude():
    _, s = run_until(Session(), EXPRESS_ANSWERS, mirror_choice=2)
    assert s.axes[Axis.INA] == 2
    assert s.incertitudes[Axis.INA] == Incertitude.NE_SAIT_PAS


def test_sonde_m4_sur_p1_subjectif():
    """P1 instinctif + axes solides : M4 questionne le report d'une semaine."""
    axes = {Axis.INA: 3, Axis.IMP: 2, Axis.BLK: 2}
    m = select_mirror(axes, Priorite.P1, seed=0)
    assert m is not None and m.code == "M4_P1"
    assert m.options[1].axe == "CDR"                    # « rien de grave » ⇒ CDR


# ------------------------------------------------------------------ goals
def test_goal_changement_categorie_et_detachement():
    conn = db.connect(":memory:")
    gid = db.create_goal(conn, "Condition physique", "perso")
    db.set_goal_category(conn, gid, "sante")
    g = db.active_goals(conn)[0]
    assert g["categorie"] == "Santé"
    db.set_goal_category(conn, gid, "categorie_inexistante")  # ignoré, pas d'erreur
    assert db.active_goals(conn)[0]["categorie"] == "Santé"

    tid = db.create_task(conn, "Sport 45 min", "sante")
    db.set_task_goal(conn, tid, gid)
    assert len(db.goal_tasks(conn, gid)) == 1
    db.set_task_goal(conn, tid, None)                          # détacher
    assert db.goal_tasks(conn, gid) == []


def test_llm_suggest_goal_valide_et_conservateur():
    import json as _json
    from prioris.llm.client import ChatClient, LLMConfig
    from prioris.llm.facade import LLMFacade
    from tests.test_llm import facade_with, fake_transport
    goals = [(3, "Activité drone"), (7, "Condition physique")]

    f = facade_with(_json.dumps({"goal_id": 7}))
    assert f.suggest_goal("Faire 45 min de course", goals) == 7
    # null = pas de correspondance claire : réponse VALIDE, pas un échec
    assert facade_with('{"goal_id": null}').suggest_goal("x", goals) is None
    # id hors liste = rejeté (repli sans suggestion)
    assert facade_with('{"goal_id": 42}').suggest_goal("x", goals) is None
    # LLM désactivé ⇒ pas de suggestion, pas d'erreur
    assert LLMFacade(None).suggest_goal("x", goals) is None


def test_llm_audit_goal_valide():
    import json as _json
    from tests.test_llm import facade_with
    tasks = [(1, "Passer le certificat télépilote"), (2, "Ranger le garage")]

    f = facade_with(_json.dumps({"douteuses": [{"id": 2, "raison": "sans lien"}]}))
    result = f.audit_goal("Activité drone", tasks)
    assert result == [{"id": 2, "raison": "sans lien"}]
    assert facade_with('{"douteuses": []}').audit_goal("Drone", tasks) == []
    # id inventé par le LLM ⇒ rejeté ⇒ None (échec propre)
    assert facade_with('{"douteuses": [{"id": 99}]}').audit_goal("D", tasks) is None


def test_goal_crud_et_liaison_tache():
    conn = db.connect(":memory:")
    gid = db.create_goal(conn, "Développer une activité drone", "perso")
    assert [g["titre"] for g in db.active_goals(conn)] == \
        ["Développer une activité drone"]

    tid = db.create_task(conn, "Passer le certificat télépilote", "perso")
    db.set_task_goal(conn, tid, gid)
    g = db.active_goals(conn)[0]
    assert g["nb_taches"] == 1 and g["nb_faites"] == 0

    db.set_task_status(conn, tid, "faite")
    assert db.active_goals(conn)[0]["nb_faites"] == 1

    db.set_goal_status(conn, gid, "atteint")
    assert db.active_goals(conn) == []                  # plus proposé
