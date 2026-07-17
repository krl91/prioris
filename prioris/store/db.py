"""SQLite access: one file, WAL, no administration.

Threads: the connection is shared between the main bot-handler thread and LLM
worker threads via asyncio.to_thread. Python serializes access
(sqlite3.threadsafety == 3 since 3.11); an explicit lock also protects writes
from worker threads.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import unicodedata
from importlib import resources
from pathlib import Path

_WRITE_LOCK = threading.Lock()


def _category_code(label: str) -> str:
    normalized = unicodedata.normalize("NFKD", label.strip().lower())
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    code = "".join(ch if ch.isalnum() else "_" for ch in ascii_text)
    while "__" in code:
        code = code.replace("__", "_")
    return code.strip("_")


def connect(db_path: str | Path) -> sqlite3.Connection:
    # check_same_thread=False is required to log LLM calls from worker threads.
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    schema = resources.files("prioris.store").joinpath("schema.sql").read_text("utf-8")
    conn.executescript(schema)
    return conn


# ------------------------------------------------------------ tasks
def create_task(conn, titre: str, category_code: str = "travail",
                deadline: str | None = None, source: str = "telegram",
                obsidian_path: str | None = None, sujet_tag: str = "") -> int:
    cat = conn.execute("SELECT id FROM categories WHERE code=?", (category_code,)).fetchone()
    cur = conn.execute(
        "INSERT INTO tasks (titre, category_id, deadline_reelle, source,"
        " obsidian_path, sujet_tag) VALUES (?,?,?,?,?,?)",
        (titre, cat["id"] if cat else None, deadline, source,
         obsidian_path, sujet_tag))
    conn.commit()
    return cur.lastrowid


def obsidian_task_known(conn, obsidian_path: str, titre: str) -> bool:
    """Scan deduplication: same source note and title already imported."""
    row = conn.execute(
        "SELECT 1 FROM tasks WHERE obsidian_path=? AND titre=? "
        "AND statut != 'abandonnee' LIMIT 1", (obsidian_path, titre)).fetchone()
    return row is not None


def set_task_category(conn, task_id: int, category_code: str) -> None:
    cat = conn.execute("SELECT id FROM categories WHERE code=?",
                       (category_code,)).fetchone()
    if cat:
        conn.execute("UPDATE tasks SET category_id=?, updated_at=datetime('now')"
                     " WHERE id=?", (cat["id"], task_id))
        conn.commit()


def set_task_status(conn, task_id: int, statut: str) -> None:
    done = ", done_at=datetime('now')" if statut == "faite" else ""
    conn.execute(f"UPDATE tasks SET statut=?, updated_at=datetime('now'){done} WHERE id=?",
                 (statut, task_id))
    conn.commit()


def update_task_planning_attrs(conn, task_id: int, estimation: str,
                               estimation_min: int, effort: int) -> None:
    conn.execute("UPDATE tasks SET estimation=?, estimation_min=?, effort=?, "
                 "updated_at=datetime('now') WHERE id=?",
                 (estimation, estimation_min, effort, task_id))
    conn.commit()


def current_tasks(conn) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM v_task_current WHERE statut IN ('evaluee','planifiee') "
        "ORDER BY priorite, score_global DESC").fetchall()


# ------------------------------------------------------------ categories
def list_categories(conn) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT code, label FROM categories ORDER BY id"
    ).fetchall()


def create_category(conn, label: str) -> str:
    clean_label = " ".join(label.strip().split())
    if not clean_label:
        raise ValueError("empty category label")
    code = _category_code(clean_label)
    if not code:
        raise ValueError("invalid category label")
    with _WRITE_LOCK:
        suffix = 2
        candidate = code
        while conn.execute("SELECT 1 FROM categories WHERE code=?",
                           (candidate,)).fetchone():
            existing = conn.execute(
                "SELECT label FROM categories WHERE code=?",
                (candidate,),
            ).fetchone()
            if existing and existing["label"].lower() == clean_label.lower():
                return candidate
            candidate = f"{code}_{suffix}"
            suffix += 1
        conn.execute("INSERT INTO categories (code, label) VALUES (?,?)",
                     (candidate, clean_label))
        conn.commit()
        return candidate


# ------------------------------------------------------------ goals
def create_goal(conn, titre: str, category_code: str = "perso") -> int:
    cat = conn.execute("SELECT id FROM categories WHERE code=?",
                       (category_code,)).fetchone()
    cur = conn.execute("INSERT INTO goals (titre, category_id) VALUES (?,?)",
                       (titre, cat["id"] if cat else None))
    conn.commit()
    return cur.lastrowid


def active_goals(conn) -> list:
    return conn.execute(
        "SELECT g.*, c.label AS categorie,"
        " (SELECT COUNT(*) FROM tasks WHERE goal_id = g.id) AS nb_taches,"
        " (SELECT COUNT(*) FROM tasks WHERE goal_id = g.id"
        "   AND statut = 'faite') AS nb_faites"
        " FROM goals g LEFT JOIN categories c ON c.id = g.category_id"
        " WHERE g.statut = 'actif' ORDER BY g.id").fetchall()


def set_goal_status(conn, goal_id: int, statut: str) -> None:
    conn.execute("UPDATE goals SET statut=? WHERE id=?", (statut, goal_id))
    conn.commit()


def set_goal_category(conn, goal_id: int, category_code: str) -> None:
    cat = conn.execute("SELECT id FROM categories WHERE code=?",
                       (category_code,)).fetchone()
    if cat:
        conn.execute("UPDATE goals SET category_id=? WHERE id=?",
                     (cat["id"], goal_id))
        conn.commit()


def goal_tasks(conn, goal_id: int, actives_seulement: bool = True) -> list:
    filtre = "AND statut NOT IN ('faite','abandonnee')" if actives_seulement else ""
    return conn.execute(
        f"SELECT id, titre, statut FROM tasks WHERE goal_id=? {filtre}"
        " ORDER BY id", (goal_id,)).fetchall()


def set_task_goal(conn, task_id: int, goal_id: int | None) -> None:
    conn.execute("UPDATE tasks SET goal_id=?, updated_at=datetime('now')"
                 " WHERE id=?", (goal_id, task_id))
    conn.commit()


# ------------------------------------------------------------ interviews
def create_interview(conn, task_id: int, mode: str) -> int:
    cur = conn.execute("INSERT INTO interviews (task_id, mode) VALUES (?,?)",
                       (task_id, mode))
    conn.commit()
    return cur.lastrowid


def record_answer(conn, interview_id: int, axe: str, valeur: int | None,
                  brut: str = "", incertitude: int = 0) -> None:
    conn.execute("INSERT INTO answers (interview_id, axe, valeur, valeur_brute_texte,"
                 " incertitude) VALUES (?,?,?,?,?)",
                 (interview_id, axe, valeur, brut, incertitude))
    conn.commit()


def finish_interview(conn, interview_id: int, mode: str) -> None:
    conn.execute("UPDATE interviews SET finished_at=datetime('now'), statut='termine',"
                 " mode=? WHERE id=?", (mode, interview_id))
    conn.commit()


# ------------------------------------------------------------ evaluations
def save_evaluation(conn, task_id: int, interview_id: int | None, result,
                    subjective: str | None) -> int:
    j = result.justification
    cur = conn.execute(
        "INSERT INTO evaluations (task_id, interview_id, version_algo, score_urgence,"
        " score_importance, score_global, quadrant, priorite, priorite_subjective,"
        " provisoire, pepite, justification_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (task_id, interview_id, j["version_algo"], result.urgence, result.importance,
         result.global_, result.quadrant, result.priorite.value, subjective,
         int(result.provisoire), int(result.pepite), json.dumps(j, ensure_ascii=False)))
    conn.execute("UPDATE tasks SET statut='evaluee', updated_at=datetime('now')"
                 " WHERE id=? AND statut='inbox'", (task_id,))
    conn.commit()
    return cur.lastrowid


def save_bias_flags(conn, evaluation_id: int, flags) -> None:
    for f in flags:
        conn.execute("INSERT INTO bias_flags (evaluation_id, type_biais, gravite,"
                     " preuve_json, message) VALUES (?,?,?,?,?)",
                     (evaluation_id, f.type_biais, f.gravite,
                      json.dumps(f.preuve, ensure_ascii=False), f.message))
    conn.commit()


def last_evaluation(conn, task_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM evaluations WHERE task_id=? "
                        "ORDER BY created_at DESC, id DESC LIMIT 1", (task_id,)).fetchone()


# ------------------------------------------------------------ plans
def save_plan(conn, date_plan: str, capacite_min: int, energie: int, plan) -> int:
    cur = conn.execute("INSERT INTO plans (date_plan, capacite_min, energie)"
                       " VALUES (?,?,?)", (date_plan, capacite_min, energie))
    plan_id = cur.lastrowid
    for ordre, item in enumerate(plan.items, 1):
        conn.execute("INSERT INTO plan_items (plan_id, task_id, ordre, duree_min,"
                     " entamer) VALUES (?,?,?,?,?)",
                     (plan_id, item.task.task_id, ordre, item.duree_min,
                      int(item.entamer)))
        conn.execute("UPDATE tasks SET statut='planifiee' WHERE id=? AND statut='evaluee'",
                     (item.task.task_id,))
    conn.commit()
    return plan_id


def log_time(conn, task_id: int, minutes: int, date: str, energie: int | None = None) -> None:
    row = conn.execute("SELECT category_id FROM tasks WHERE id=?", (task_id,)).fetchone()
    conn.execute("INSERT INTO time_log (task_id, category_id, date, minutes, energie)"
                 " VALUES (?,?,?,?,?)",
                 (task_id, row["category_id"] if row else None, date, minutes, energie))
    conn.commit()


def save_outcome(conn, task_id: int, consequence: int, delai_jours: int | None) -> None:
    conn.execute("INSERT INTO outcomes (task_id, consequence_reelle, delai_jours)"
                 " VALUES (?,?,?)", (task_id, consequence, delai_jours))
    conn.commit()


def add_task_note(conn, task_id: int, source: str, note: str) -> int:
    cur = conn.execute("INSERT INTO task_notes (task_id, source, note) VALUES (?,?,?)",
                       (task_id, source, note))
    conn.commit()
    return cur.lastrowid


def sync_from_vault_marks(conn, marked, date: str) -> dict:
    """Sync vault markers into SQLite, called by /scan.

    `marked` is a list of MarkedTask items found in the vault.
    - checked `- [x]` line: task becomes done and estimated time is logged;
    - tracked task missing from the vault: reported, with no automatic action.
    Returns {"done": [(id, title)], "missing": [(id, title)]}.
    """
    seen_ids = {m.task_id for m in marked}
    checked_ids = {m.task_id for m in marked if m.checked}
    report = {"done": [], "missing": []}

    tracked = conn.execute(
        "SELECT id, titre, estimation_min FROM tasks WHERE source='obsidian' "
        "AND statut IN ('evaluee', 'planifiee')").fetchall()
    for row in tracked:
        if row["id"] in checked_ids:
            set_task_status(conn, row["id"], "faite")
            log_time(conn, row["id"], row["estimation_min"] or 30, date)
            report["done"].append((row["id"], row["titre"]))
        elif row["id"] not in seen_ids:
            report["missing"].append((row["id"], row["titre"]))
    return report


def log_llm_call(conn, type_: str, modele: str, latence_ms: int, valide: bool) -> None:
    """Only function called from worker threads; protected by a lock."""
    with _WRITE_LOCK:
        conn.execute("INSERT INTO llm_calls (type, modele, latence_ms, valide)"
                     " VALUES (?,?,?,?)", (type_, modele, latence_ms, int(valide)))
        conn.commit()
