"""Simple Obsidian export: the daily plan in one fixed note.

Atomic write through temp file + rename. Touches nothing else in the vault.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

MARK_START = "<!-- prioris:start -->"
MARK_END = "<!-- prioris:end -->"


def render_plan_md(plan, date_str: str, energie: int) -> str:
    energies = {1: "très faible", 2: "faible", 3: "normale", 4: "bonne", 5: "excellente"}
    lines = [MARK_START,
             f"# Plan du jour — {date_str}",
             f"*Énergie : {energies.get(energie, '?')} · "
             f"capacité utile : {plan.capacite_utile_min} min*", ""]
    if not plan.items:
        lines.append("Aucune tâche planifiable aujourd'hui — plan court, plan honnête.")
    for item in plan.items:
        prefix = "entamer : " if item.entamer else ""
        gem = " 💎" if item.task.pepite else ""
        lines.append(f"- [ ] {prefix}{item.task.titre}{gem} "
                     f"({item.duree_min} min · {item.task.priorite.value})")
        if item.note:
            lines.append(f"  - ⚠️ {item.note}")
    if plan.sacrifiees:
        lines += ["", "## Non retenu aujourd'hui (assumé)"]
        lines += [f"- {t.titre} ({t.priorite.value})" for t in plan.sacrifiees]
    if plan.exclues:
        lines += ["", "## Exclues"]
        lines += [f"- {t.titre} — {raison}" for t, raison in plan.exclues]
    if plan.minutes_par_categorie:
        lines += ["", "## Minutes par catégorie"]
        lines += [f"- {cat} : {mn} min"
                  for cat, mn in sorted(plan.minutes_par_categorie.items())]
    lines.append(MARK_END)
    return "\n".join(lines) + "\n"


def write_note(vault_path: str | Path, relative_note: str, content: str) -> Path:
    """Write a note atomically and create missing folders."""
    target = Path(vault_path) / relative_note
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return target
