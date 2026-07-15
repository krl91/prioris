"""Obsidian sync proposed after an /info revision.

Nothing is written without UI confirmation. The module prepares a before/after
preview for the files that would be touched, then applies exactly that state.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from . import scan
from .export import write_note


@dataclass(frozen=True)
class FileChange:
    rel_path: str
    before: str
    after: str

    @property
    def changed(self) -> bool:
        return self.before != self.after


@dataclass(frozen=True)
class SyncProposal:
    task_id: int
    title: str
    changes: list[FileChange]

    @property
    def has_changes(self) -> bool:
        return any(c.changed for c in self.changes)


def _bias_flags(conn, evaluation_id: int) -> list:
    rows = conn.execute(
        "SELECT type_biais, gravite, preuve_json, message "
        "FROM bias_flags WHERE evaluation_id=? ORDER BY id",
        (evaluation_id,),
    ).fetchall()
    return [
        SimpleNamespace(
            type_biais=r["type_biais"],
            gravite=r["gravite"],
            preuve=json.loads(r["preuve_json"]),
            message=r["message"],
        )
        for r in rows
    ]


def _task_notes(conn, task_id: int) -> list[tuple[str, str]]:
    rows = conn.execute(
        "SELECT created_at, note FROM task_notes "
        "WHERE task_id=? ORDER BY created_at, id",
        (task_id,),
    ).fetchall()
    return [(r["created_at"], r["note"]) for r in rows]


def _replace_priority_marker(text: str, task_id: int, priority: str) -> str:
    pattern = re.compile(
        rf"🎯P[1-4]\s+\[\[(?:[^\]|]*/)?{task_id}(?:\s+-[^\]|]*)?(?:\|[^\]]*)?\]\]"
    )
    return pattern.sub(f"🎯{priority} [[PRIORIS/{task_id}]]", text)


def build_sync_proposal(conn, vault_path: str | Path,
                        prioris_dir: str, task_id: int) -> SyncProposal | None:
    task = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    evaluation = conn.execute(
        "SELECT * FROM evaluations WHERE task_id=? "
        "ORDER BY created_at DESC, id DESC LIMIT 1",
        (task_id,),
    ).fetchone()
    if not task or not evaluation or not task["obsidian_path"]:
        return None

    source_rel = task["obsidian_path"]
    title = task["titre"]
    justification = json.loads(evaluation["justification_json"])
    detail_rel = scan.detail_note_rel(prioris_dir, task_id, title)
    vault = Path(vault_path)

    old_detail = ""
    detail_path = vault / detail_rel
    if detail_path.exists():
        try:
            old_detail = detail_path.read_text("utf-8")
        except (OSError, UnicodeDecodeError):
            old_detail = ""
    new_detail = scan.render_detail_note(
        title, source_rel, justification, _bias_flags(conn, evaluation["id"]),
        dt.date.today().isoformat(), task_id=task_id,
        notes=_task_notes(conn, task_id),
    )

    changes = [FileChange(detail_rel, old_detail, new_detail)]

    source_path = vault / source_rel
    try:
        old_source = source_path.read_text("utf-8")
    except (OSError, UnicodeDecodeError):
        old_source = ""
    if old_source:
        new_source = _replace_priority_marker(
            old_source, task_id, evaluation["priorite"])
        if new_source != old_source:
            changes.append(FileChange(source_rel, old_source, new_source))

    proposal = SyncProposal(task_id, title, changes)
    return proposal if proposal.has_changes else None


def build_full_sync_proposal(conn, vault_path: str | Path,
                             prioris_dir: str) -> SyncProposal | None:
    """Build one cumulative proposal for every task linked to the vault."""
    rows = conn.execute(
        "SELECT t.id, t.titre, t.obsidian_path, "
        "e.id AS eval_id, e.priorite, e.justification_json "
        "FROM tasks t "
        "JOIN evaluations e ON e.id = ("
        "  SELECT id FROM evaluations WHERE task_id=t.id "
        "  ORDER BY created_at DESC, id DESC LIMIT 1"
        ") "
        "WHERE t.obsidian_path IS NOT NULL AND t.obsidian_path != '' "
        "AND t.statut != 'abandonnee' "
        "ORDER BY t.id"
    ).fetchall()
    if not rows:
        return None

    vault = Path(vault_path)
    originals: dict[str, str] = {}
    finals: dict[str, str] = {}

    def ensure_text(rel_path: str) -> str:
        if rel_path not in originals:
            path = vault / rel_path
            try:
                originals[rel_path] = path.read_text("utf-8")
            except (OSError, UnicodeDecodeError):
                originals[rel_path] = ""
            finals[rel_path] = originals[rel_path]
        return finals[rel_path]

    for row in rows:
        task_id = int(row["id"])
        title = row["titre"]
        source_rel = row["obsidian_path"]
        justification = json.loads(row["justification_json"])
        detail_rel = scan.detail_note_rel(prioris_dir, task_id, title)
        ensure_text(detail_rel)
        finals[detail_rel] = scan.render_detail_note(
            title, source_rel, justification, _bias_flags(conn, row["eval_id"]),
            dt.date.today().isoformat(), task_id=task_id,
            notes=_task_notes(conn, task_id),
        )

        source_text = ensure_text(source_rel)
        if source_text:
            finals[source_rel] = _replace_priority_marker(
                source_text, task_id, row["priorite"])

    changes = [
        FileChange(rel_path, originals[rel_path], finals[rel_path])
        for rel_path in sorted(originals)
        if originals[rel_path] != finals[rel_path]
    ]
    proposal = SyncProposal(0, "Synchronisation Obsidian complète", changes)
    return proposal if proposal.has_changes else None


def apply_sync_proposal(vault_path: str | Path, proposal: SyncProposal) -> None:
    for change in proposal.changes:
        if change.changed:
            write_note(vault_path, change.rel_path, change.after)


def render_sync_preview(proposal: SyncProposal, max_chars: int = 3200) -> str:
    lines = [
        f"Synchronisation Obsidian proposée pour #{proposal.task_id} {proposal.title}",
        "Rien ne sera écrit sans confirmation.",
        "",
    ]
    for change in proposal.changes:
        if not change.changed:
            continue
        before = change.before.strip() or "(fichier absent)"
        after = change.after.strip() or "(fichier vide)"
        lines += [
            f"Fichier : {change.rel_path}",
            "Avant :",
            before,
            "",
            "Après :",
            after,
            "",
            "────────────────",
            "",
        ]
    text = "\n".join(lines).strip()
    if len(text) > max_chars:
        return text[:max_chars].rstrip() + "\n\n... aperçu tronqué ..."
    return text
