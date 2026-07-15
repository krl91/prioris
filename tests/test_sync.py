"""Tests de la synchro vault → SQLite (v0.3.3)."""
from prioris.core.axes import Estimation
from prioris.core.scoring import score
from prioris.store import db
from prioris.vault import scan
from tests.test_scoring import axes


def make_synced_vault(tmp_path, conn):
    """3 tâches évaluées + annotées ; puis modifications manuelles simulées."""
    note = tmp_path / "Quotidien.md"
    note.write_text("- [ ] Tâche A\n- [ ] Tâche B\n- [ ] Tâche C\n", "utf-8")
    ids = []
    for vt in scan.find_unprioritized(tmp_path):
        tid = db.create_task(conn, vt.titre, "travail", source="obsidian",
                             obsidian_path=vt.rel_path)
        r = score(axes(imp=2, ina=2), estimation=Estimation.M15_30)
        db.save_evaluation(conn, tid, None, r, None)
        scan.apply_result(tmp_path, "PRIORIS", vt, tid, r.justification,
                          [], "2026-07-12")
        ids.append(tid)
    return note, ids


def test_find_marked_extrait_id_et_etat(tmp_path):
    conn = db.connect(":memory:")
    note, ids = make_synced_vault(tmp_path, conn)
    # cocher A à la main (même avec titre modifié : l'id du lien fait foi)
    text = note.read_text("utf-8")
    text = text.replace("- [ ] Tâche A", "- [x] Tâche A (terminée hier)", 1)
    note.write_text(text, "utf-8")

    marked = scan.find_marked(tmp_path)
    assert {m.task_id for m in marked} == set(ids)
    etats = {m.task_id: m.checked for m in marked}
    assert etats[ids[0]] is True
    assert etats[ids[1]] is False


def test_sync_cochee_devient_faite(tmp_path):
    conn = db.connect(":memory:")
    note, ids = make_synced_vault(tmp_path, conn)
    note.write_text(note.read_text("utf-8").replace("- [ ] Tâche B", "- [x] Tâche B"),
                    "utf-8")
    report = db.sync_from_vault_marks(conn, scan.find_marked(tmp_path), "2026-07-12")
    assert [i for i, _ in report["done"]] == [ids[1]]
    statut = conn.execute("SELECT statut, done_at FROM tasks WHERE id=?",
                          (ids[1],)).fetchone()
    assert statut["statut"] == "faite" and statut["done_at"]
    # temps loggé
    assert conn.execute("SELECT COUNT(*) c FROM time_log WHERE task_id=?",
                        (ids[1],)).fetchone()["c"] == 1
    # les autres inchangées
    assert conn.execute("SELECT statut FROM tasks WHERE id=?",
                        (ids[0],)).fetchone()["statut"] == "evaluee"


def test_sync_disparue_signalee_sans_action(tmp_path):
    conn = db.connect(":memory:")
    note, ids = make_synced_vault(tmp_path, conn)
    lignes = [l for l in note.read_text("utf-8").splitlines()
              if "Tâche C" not in l]
    note.write_text("\n".join(lignes) + "\n", "utf-8")
    report = db.sync_from_vault_marks(conn, scan.find_marked(tmp_path), "2026-07-12")
    assert [i for i, _ in report["missing"]] == [ids[2]]
    # statut CONSERVÉ : la décision appartient à l'utilisateur
    assert conn.execute("SELECT statut FROM tasks WHERE id=?",
                        (ids[2],)).fetchone()["statut"] == "evaluee"


def test_check_task_line_coche_la_bonne_ligne(tmp_path):
    """Symétrie /done → vault (v0.3.4)."""
    conn = db.connect(":memory:")
    note, ids = make_synced_vault(tmp_path, conn)
    ok, rel = scan.check_task_line(tmp_path, ids[1])
    assert ok and rel == "Quotidien.md"
    text = note.read_text("utf-8")
    assert text.count("- [x]") == 1
    assert "- [x] Tâche B" in text
    assert "- [ ] Tâche A" in text and "- [ ] Tâche C" in text
    # idempotent : déjà cochée ⇒ succès, contenu inchangé
    avant = note.read_text("utf-8")
    ok2, _ = scan.check_task_line(tmp_path, ids[1])
    assert ok2 and note.read_text("utf-8") == avant
    # id inconnu ⇒ échec propre, aucune écriture
    ok3, rel3 = scan.check_task_line(tmp_path, 99999)
    assert not ok3 and rel3 == ""


def test_sync_idempotente(tmp_path):
    conn = db.connect(":memory:")
    note, ids = make_synced_vault(tmp_path, conn)
    note.write_text(note.read_text("utf-8").replace("- [ ] Tâche A", "- [x] Tâche A"),
                    "utf-8")
    marked = scan.find_marked(tmp_path)
    db.sync_from_vault_marks(conn, marked, "2026-07-12")
    report2 = db.sync_from_vault_marks(conn, marked, "2026-07-12")
    assert report2["done"] == []       # déjà faite : pas re-signalée
    assert conn.execute("SELECT COUNT(*) c FROM time_log WHERE task_id=?",
                        (ids[0],)).fetchone()["c"] == 1   # pas de double log
