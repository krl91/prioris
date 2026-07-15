from prioris import task_revision
from prioris.core.axes import Axis, Estimation
from prioris.core.scoring import score
from prioris.llm.client import ChatClient, LLMConfig
from prioris.llm.facade import LLMFacade
from prioris.store import db
from tests.test_llm import fake_transport


def _axes(**kw):
    base = {
        Axis.BLK: 2, Axis.CDR: 1, Axis.HOR: 1,
        Axis.IMP: 2, Axis.INA: 1, Axis.IRR: 0, Axis.ALN: 0,
    }
    base.update(kw)
    return base


def test_revision_applique_une_nouvelle_evaluation(tmp_path):
    conn = db.connect(tmp_path / "prioris.db")
    task_id = db.create_task(conn, "Préparer retour client", "travail")
    result = score(_axes(), estimation=Estimation.M30_60)
    db.save_evaluation(conn, task_id, None, result, None)

    llm = LLMFacade(ChatClient(LLMConfig(enabled=True, provider="prioris")))
    proposal = task_revision.make_proposal(
        conn, task_id, "Le client est bloqué depuis ce matin.", llm)

    assert proposal is not None
    assert proposal.has_changes
    assert any(ch.axis == Axis.BLK and ch.new == 4 for ch in proposal.changes)

    old_eval_id = db.last_evaluation(conn, task_id)["id"]
    new_eval_id = task_revision.apply_proposal(conn, proposal)

    assert new_eval_id != old_eval_id
    latest = db.last_evaluation(conn, task_id)
    assert latest["id"] == new_eval_id
    assert latest["score_global"] >= result.global_
    note = conn.execute(
        "SELECT note FROM task_notes WHERE task_id=?", (task_id,)
    ).fetchone()
    assert "client" in note["note"].lower()


def test_revision_manuelle_sans_llm(tmp_path):
    conn = db.connect(tmp_path / "prioris.db")
    task_id = db.create_task(conn, "Préparer retour client", "travail")
    result = score(_axes(), estimation=Estimation.M30_60)
    db.save_evaluation(conn, task_id, None, result, None)

    proposal = task_revision.make_manual_proposal(
        conn, task_id, "BLK=4 Le client est bloqué", "BLK", 4)

    assert proposal is not None
    assert proposal.has_changes
    assert proposal.changes[0].axis == Axis.BLK
    assert proposal.changes[0].new == 4


def test_revision_llm_echec_pas_transforme_en_aucune_modification(tmp_path):
    conn = db.connect(tmp_path / "prioris.db")
    task_id = db.create_task(conn, "Préparer retour client", "travail")
    result = score(_axes(), estimation=Estimation.M30_60)
    db.save_evaluation(conn, task_id, None, result, None)
    llm = LLMFacade(ChatClient(
        LLMConfig(enabled=True, provider="ollama", model="m"),
        fake_transport("pas du json"),
    ))

    proposal = task_revision.make_proposal(
        conn, task_id, "Le client est bloqué", llm)

    assert proposal is None
    assert llm.last_error
