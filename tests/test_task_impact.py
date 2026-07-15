import datetime as dt

from prioris import task_impact
from prioris.core.axes import Axis, Estimation
from prioris.core.scoring import score
from prioris.llm.client import ChatClient, LLMConfig
from prioris.llm.facade import LLMFacade
from prioris.store import db


def _axes():
    return {
        Axis.BLK: 2, Axis.CDR: 1, Axis.HOR: 1,
        Axis.IMP: 2, Axis.INA: 1, Axis.IRR: 0, Axis.ALN: 0,
    }


def test_impact_propose_une_tache_existante(tmp_path):
    conn = db.connect(tmp_path / "prioris.db")
    tid = db.create_task(conn, "Retour client", "travail")
    db.save_evaluation(conn, tid, None, score(_axes(), Estimation.M30_60), None)
    llm = LLMFacade(ChatClient(LLMConfig(enabled=True, provider="prioris")))

    proposal = task_impact.make_proposal(conn, "Le client est bloqué", llm)

    assert proposal is not None
    assert proposal.has_impacted
    assert proposal.impacted[0].id == tid
    assert "client" in task_impact.render_proposal(proposal).lower()


def test_impact_propose_une_nouvelle_tache_si_aucun_match(tmp_path):
    conn = db.connect(tmp_path / "prioris.db")
    tid = db.create_task(conn, "Retour client", "travail")
    db.save_evaluation(conn, tid, None, score(_axes(), Estimation.M30_60), None)
    llm = LLMFacade(ChatClient(LLMConfig(enabled=True, provider="prioris")))

    proposal = task_impact.make_proposal(conn, "Réserver le train pour Lyon", llm)

    assert proposal is not None
    assert not proposal.has_impacted
    assert "train" in proposal.new_task_title.lower()


def test_impact_propose_date_limite_relative(tmp_path):
    conn = db.connect(tmp_path / "prioris.db")
    tid = db.create_task(conn, "Retour client", "travail")
    db.save_evaluation(conn, tid, None, score(_axes(), Estimation.M30_60), None)
    llm = LLMFacade(ChatClient(LLMConfig(enabled=True, provider="prioris")))

    proposal = task_impact.make_proposal(
        conn, "toto doit manger une pomme d'ici une heure", llm)

    assert proposal is not None
    assert not proposal.has_impacted
    assert proposal.suggested_deadline == dt.date.today().isoformat()
    assert "Date limite détectée" in task_impact.render_proposal(proposal)


def test_impact_repond_directement_a_une_question(tmp_path):
    conn = db.connect(tmp_path / "prioris.db")
    tid = db.create_task(conn, "Retour client", "travail")
    db.save_evaluation(conn, tid, None, score(_axes(), Estimation.M30_60), None)
    llm = LLMFacade(ChatClient(LLMConfig(enabled=True, provider="prioris")))

    proposal = task_impact.make_proposal(conn, "Est-ce que le client est bloqué ?", llm)

    assert proposal is not None
    assert proposal.direct_answer
    assert "Réponse directe" in task_impact.render_proposal(proposal)
