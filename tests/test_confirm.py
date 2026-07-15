"""Tests de la fiche de confirmation (v0.3.2)."""
from prioris.bot.handlers import _task_card
from prioris.core.axes import Estimation
from prioris.core.scoring import score
from prioris.store import db
from tests.test_scoring import axes


def test_task_card_complete():
    conn = db.connect(":memory:")
    tid = db.create_task(conn, "Finaliser le modèle de données", "travail",
                         source="obsidian", obsidian_path="Quotidien/2026-07-10.md")
    r = score(axes(blk=1, cdr=3, hor=1, imp=3, ina=2, irr=1, aln=3),
              estimation=Estimation.M30_60)
    db.save_evaluation(conn, tid, None, r, None)
    card = _task_card(conn, tid)
    assert "Finaliser le modèle de données" in card
    assert f"#{tid}" in card
    assert "P2" in card and "Travail" in card
    assert "Quotidien/2026-07-10.md" in card


def test_task_card_non_evaluee_et_introuvable():
    conn = db.connect(":memory:")
    tid = db.create_task(conn, "Brouillon", "perso")
    assert "non évaluée" in _task_card(conn, tid)
    assert _task_card(conn, 9999) is None
