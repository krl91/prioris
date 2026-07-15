"""Tests d'intégration légers : store/ (SQLite en mémoire) et vault/ (tmp)."""
import json

from prioris.core.axes import Axis, Effort, Estimation, Priorite
from prioris.core.planner import PlanTask, build_day_plan
from prioris.core.scoring import score
from prioris.store import db
from prioris.vault import export, info_sync, scan


def axes(**kw):
    base = dict(blk=0, cdr=1, hor=3, imp=1, ina=1, irr=0, aln=0)
    base.update(kw)
    return {Axis.BLK: base["blk"], Axis.CDR: base["cdr"], Axis.HOR: base["hor"],
            Axis.IMP: base["imp"], Axis.INA: base["ina"], Axis.IRR: base["irr"],
            Axis.ALN: base["aln"]}


def test_roundtrip_evaluation():
    conn = db.connect(":memory:")
    task_id = db.create_task(conn, "Préparer l'atelier Kallipr", "travail")
    itw = db.create_interview(conn, task_id, "express")
    result = score(axes(), estimation=Estimation.H1_2, subjective=Priorite.P1)
    eval_id = db.save_evaluation(conn, task_id, itw, result, "P1")

    row = db.last_evaluation(conn, task_id)
    assert row["id"] == eval_id
    assert row["priorite"] == "P4" and row["priorite_subjective"] == "P1"
    j = json.loads(row["justification_json"])
    assert j["calculs"]["G"]["total"] == 22.0   # reconstructible (§6.5)

    # append-only : une réévaluation s'ajoute, n'écrase pas
    result2 = score(axes(blk=2), estimation=Estimation.H1_2)
    db.save_evaluation(conn, task_id, itw, result2, None)
    count = conn.execute("SELECT COUNT(*) c FROM evaluations WHERE task_id=?",
                         (task_id,)).fetchone()["c"]
    assert count == 2


def test_v_task_current_prend_la_derniere():
    conn = db.connect(":memory:")
    task_id = db.create_task(conn, "T", "sante")
    r1 = score(axes(), estimation=Estimation.LT15)
    r2 = score(axes(aln=3, imp=3), estimation=Estimation.LT15)
    db.save_evaluation(conn, task_id, None, r1, None)
    db.save_evaluation(conn, task_id, None, r2, None)
    rows = db.current_tasks(conn)
    assert len(rows) == 1 and rows[0]["priorite"] == r2.priorite.value


def test_export_plan_note(tmp_path):
    tasks = [PlanTask(1, "Sport 45 min", Priorite.P2, 56.6, 45,
                      Effort.FAIBLE, "sante", False)]
    plan = build_day_plan(tasks, 240, 3)
    content = export.render_plan_md(plan, "2026-07-12", 3)
    target = export.write_note(tmp_path, "PRIORIS/Plan du jour.md", content)
    text = target.read_text("utf-8")
    assert export.MARK_START in text and export.MARK_END in text
    assert "- [ ] Sport 45 min" in text
    # réécriture atomique : pas de fichier temporaire résiduel
    assert list(target.parent.glob("*.tmp")) == []


def test_info_sync_propose_et_applique_avant_apres_obsidian(tmp_path):
    vault = tmp_path / "vault"
    source = vault / "Daily.md"
    source.parent.mkdir()
    source.write_text(
        "- [ ] Préparer le dossier 🎯P4 [[PRIORIS/details/1 - Préparer le dossier|détail]]\n",
        "utf-8",
    )

    conn = db.connect(":memory:")
    task_id = db.create_task(
        conn, "Préparer le dossier", "travail",
        source="obsidian", obsidian_path="Daily.md")
    result = score(
        axes(blk=3, cdr=4, hor=1, imp=3, ina=3, irr=1, aln=2),
        estimation=Estimation.M30_60,
    )
    db.save_evaluation(conn, task_id, None, result, None)
    db.add_task_note(conn, task_id, "revision_llm", "Le client est bloqué.")

    proposal = info_sync.build_sync_proposal(conn, vault, "PRIORIS", task_id)

    assert proposal is not None
    preview = info_sync.render_sync_preview(proposal)
    assert "Avant :" in preview
    assert "Après :" in preview
    assert "🎯P4" in preview
    assert f"🎯{result.priorite.value}" in preview

    info_sync.apply_sync_proposal(vault, proposal)

    source_text = source.read_text("utf-8")
    assert f"🎯{result.priorite.value} [[PRIORIS/{task_id}]]" in source_text
    assert "details/" not in source_text
    detail = vault / scan.detail_note_rel("PRIORIS", task_id, "Préparer le dossier")
    assert detail.exists()
    detail_text = detail.read_text("utf-8")
    assert f"# PRIORIS #{task_id} — Préparer le dossier" in detail_text
    assert f"**{result.priorite.value}**" in detail_text
    assert "## Informations ajoutées" in detail_text
    assert "Le client est bloqué." in detail_text


def test_info_sync_ignore_tache_non_liee_obsidian(tmp_path):
    conn = db.connect(":memory:")
    task_id = db.create_task(conn, "Tâche locale", "perso")
    result = score(axes(), estimation=Estimation.LT15)
    db.save_evaluation(conn, task_id, None, result, None)

    assert info_sync.build_sync_proposal(conn, tmp_path, "PRIORIS", task_id) is None


def test_info_sync_complete_agrege_plusieurs_taches_meme_note(tmp_path):
    vault = tmp_path / "vault"
    source = vault / "Daily.md"
    source.parent.mkdir()
    source.write_text(
        "- [ ] Préparer le dossier 🎯P4 [[PRIORIS/details/1 - Préparer le dossier|détail]]\n"
        "- [ ] Appeler le client 🎯P4 [[PRIORIS/details/2 - Appeler le client|détail]]\n",
        "utf-8",
    )
    conn = db.connect(":memory:")
    first = db.create_task(
        conn, "Préparer le dossier", "travail",
        source="obsidian", obsidian_path="Daily.md")
    second = db.create_task(
        conn, "Appeler le client", "travail",
        source="obsidian", obsidian_path="Daily.md")
    result_first = score(
        axes(blk=3, cdr=4, hor=1, imp=3, ina=3, irr=1, aln=2),
        estimation=Estimation.M30_60,
    )
    result_second = score(
        axes(blk=2, cdr=3, hor=1, imp=2, ina=2, irr=1, aln=1),
        estimation=Estimation.M30_60,
    )
    db.save_evaluation(conn, first, None, result_first, None)
    db.save_evaluation(conn, second, None, result_second, None)

    proposal = info_sync.build_full_sync_proposal(conn, vault, "PRIORIS")

    assert proposal is not None
    assert any(c.rel_path == "Daily.md" for c in proposal.changes)
    info_sync.apply_sync_proposal(vault, proposal)
    source_text = source.read_text("utf-8")
    assert f"🎯{result_first.priorite.value} [[PRIORIS/{first}]]" in source_text
    assert f"🎯{result_second.priorite.value} [[PRIORIS/{second}]]" in source_text
    assert "details/" not in source_text
    assert (vault / scan.detail_note_rel("PRIORIS", first, "Préparer le dossier")).exists()
    assert (vault / scan.detail_note_rel("PRIORIS", second, "Appeler le client")).exists()
