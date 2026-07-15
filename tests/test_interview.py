"""Tests de la machine à états (§3.2, §3.5) — transitions sans Telegram."""
from prioris.core import interview as itv
from prioris.core.axes import Axis, Estimation, Priorite
from prioris.core.interview import Q, Session


def run_until(session, answers, mirror_choice=0):
    """Déroule l'entretien avec un dict Q -> valeur ; retourne (questions posées, session).

    Clarifications : première option. Miroir : option `mirror_choice`
    (0 = réponse cohérente, sans correction d'axe)."""
    asked = []
    while True:
        q, session = itv.next_question(session)
        if q is None:
            return asked, session
        if q == Q.CLARIFICATION:
            c = session.pending
            _, axe, val = c.options[0]
            asked.append(Q.CLARIFICATION)
            session = itv.clarify(session, axe, val)
            continue
        if q == Q.MIROIR:
            asked.append(Q.MIROIR)
            session = itv.mirror_answer(session, mirror_choice)
            continue
        asked.append(q)
        session = itv.answer(session, q, answers[q])
    return asked, session


EXPRESS_ANSWERS = {
    Q.SUBJECTIVE: "P3", Q.INACTION: 1, Q.BLOCAGE: 0, Q.CDR: 1,
    Q.OBJECTIF: 0, Q.ESTIMATION: Estimation.M30_60,
}
FULL_ANSWERS = {**EXPRESS_ANSWERS, Q.IMPACT: 1, Q.HORIZON: 1,
                Q.IRREVERSIBILITE: 0, Q.EFFORT: 2, Q.DEMANDEUR: "moi",
                Q.VISIBILITE: 0, Q.PRESSION: 0}


def test_express_par_defaut_6_questions():
    asked, s = run_until(Session(), EXPRESS_ANSWERS)
    # INA=1 rend la sonde miroir M1 applicable : elle clôt l'entretien (§7.2)
    assert asked == itv.EXPRESS_FLOW + [Q.MIROIR]
    assert s.mode == "express" and s.mirror_done


def test_bascule_complet_sur_p1_subjectif():
    answers = {**FULL_ANSWERS, Q.SUBJECTIVE: "P1", Q.BLOCAGE: 2}
    asked, s = run_until(Session(), answers)
    assert s.mode == "complet"
    assert Q.IMPACT in asked and Q.PRESSION in asked


def test_bascule_complet_sur_ina_haute():
    answers = {**FULL_ANSWERS, Q.INACTION: 3}
    _, s = run_until(Session(), answers)
    assert s.mode == "complet"


def test_bascule_complet_sur_deadline_proche():
    _, s = run_until(Session(deadline_days=3), FULL_ANSWERS)
    assert s.mode == "complet"


def test_contradiction_c2_inseree_et_resolue():
    """BLK=4 + INA=1 ⇒ clarification ; l'option 'en attente' corrige BLK→0."""
    answers = {**FULL_ANSWERS, Q.BLOCAGE: 4}
    asked, s = run_until(Session(), answers)
    assert Q.CLARIFICATION in asked
    assert "C2" in s.resolved_rules
    assert s.mode == "complet"          # contradiction ⇒ enjeu ⇒ complet


def test_plafond_2_clarifications():
    s = Session(axes={Axis.INA: 0, Axis.CDR: 4, Axis.BLK: 5, Axis.HOR: 4,
                      Axis.IMP: 4}, clarifications=2)
    s2 = itv._check_contradictions(s)
    assert s2.pending is None            # plafond atteint : plus d'insertion
    assert itv.is_provisoire(s2)         # ⇒ évaluation provisoire (§7.1)


def test_final_axes_defauts_express():
    """§3.5 : HOR dérivé de la deadline, IRR=1, IMP=min(INA,3)."""
    _, s = run_until(Session(deadline_days=20), {
        **EXPRESS_ANSWERS, Q.INACTION: 2})
    axes, par_defaut = itv.final_axes(s)
    assert axes[Axis.HOR] == 2 and Axis.HOR in par_defaut
    assert axes[Axis.IRR] == 1 and axes[Axis.IMP] == 2
    assert Axis.INA not in par_defaut    # répondu, pas défaut


def test_clarification_je_ne_sais_pas_marque_incertitude():
    """Audit v0.3.5 : « je ne sais pas » en clarification = incertitude
    enregistrée ⇒ évaluation provisoire, comme le 🤷 des questions normales."""
    from prioris.core.axes import Incertitude
    s = Session()
    s = itv.answer(s, Q.SUBJECTIVE, "P3")
    s = itv.answer(s, Q.INACTION, 1)
    s = itv.answer(s, Q.BLOCAGE, 4)          # C2 levée
    assert s.pending is not None
    s = itv.clarify(s, "BLK", 2, incertain=True)
    assert s.incertitudes[Axis.BLK] == Incertitude.NE_SAIT_PAS


def test_c5_promesse_de_date_puis_saisie():
    """Audit v0.3.5 : « je donne la date » → règle éteinte → date posée."""
    s = Session()
    s = itv.answer(s, Q.SUBJECTIVE, "P2")
    s = itv.answer(s, Q.INACTION, 2)
    s = itv.answer(s, Q.BLOCAGE, 1)
    s = itv.answer(s, Q.CDR, 4)              # falaise sans date ⇒ C5
    assert s.pending is not None and s.pending.regle == "C5"
    s = itv.promise_deadline(s)
    assert s.pending is None and "C5" in s.resolved_rules
    s = itv.set_deadline(s, 4)
    assert s.deadline_days == 4
    # C5 résolue : ne se re-lève pas ; la deadline alimentera le plancher §6.2
    q, s = itv.next_question(s)
    assert q != Q.CLARIFICATION


def test_une_seule_question_a_la_fois():
    s = Session()
    q1, s = itv.next_question(s)
    q1b, _ = itv.next_question(s)
    assert q1 == q1b == Q.SUBJECTIVE     # tant que pas de réponse, même question


def test_sessions_immuables():
    s = Session()
    s2 = itv.answer(s, Q.SUBJECTIVE, "P2")
    assert s.asked == () and s2.asked == (Q.SUBJECTIVE,)
    assert s2.subjective == Priorite.P2
