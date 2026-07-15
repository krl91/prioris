"""Controlled revision of an existing evaluation.

The LLM may propose axis changes, but recalculation stays fully inside
scoring.py and database writes remain subject to UI confirmation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from .core.axes import AXIS_LABELS, AXIS_MAX, Axis, Estimation, Metadata
from .core import biases, scoring
from .store import db


@dataclass(frozen=True)
class AxisChange:
    axis: Axis
    old: int
    new: int
    reason: str


@dataclass(frozen=True)
class RevisionProposal:
    task_id: int
    task_title: str
    note: str
    changes: list[AxisChange]
    old_priority: str
    old_score: float
    new_priority: str
    new_score: float
    explanation: str
    result: scoring.ScoreResult | None

    @property
    def has_changes(self) -> bool:
        return bool(self.changes) and self.result is not None


def axes_from_evaluation(row) -> dict[Axis, int]:
    j = json.loads(row["justification_json"])
    return {Axis(code): int(data["valeur"]) for code, data in j["axes"].items()}


def build_context(conn, task_id: int) -> dict | None:
    task = conn.execute(
        "SELECT t.*, c.code AS cat_code FROM tasks t "
        "LEFT JOIN categories c ON c.id=t.category_id WHERE t.id=?",
        (task_id,),
    ).fetchone()
    row = db.last_evaluation(conn, task_id)
    if not task or not row:
        return None
    axes = axes_from_evaluation(row)
    return {
        "task": {
            "id": task_id,
            "titre": task["titre"],
            "categorie": task["cat_code"],
            "description": task["description"],
            "deadline": task["deadline_reelle"],
            "estimation": task["estimation"],
        },
        "evaluation": {
            "priorite": row["priorite"],
            "score_global": row["score_global"],
            "axes": {
                axis.value: {
                    "valeur": value,
                    "label": AXIS_LABELS[axis][value],
                    "max": AXIS_MAX[axis],
                }
                for axis, value in axes.items()
            },
        },
    }


def make_proposal(conn, task_id: int, note: str, llm) -> RevisionProposal | None:
    ctx = build_context(conn, task_id)
    if ctx is None:
        return None
    task = ctx["task"]
    row = db.last_evaluation(conn, task_id)
    old_axes = axes_from_evaluation(row)
    suggested = llm.revise_task(ctx, note) if llm and llm.available else None
    if suggested is None:
        return None

    changes: list[AxisChange] = []
    new_axes = dict(old_axes)
    for item in suggested.get("changes", []):
        axis = Axis(item["axis"])
        new_value = int(item["value"])
        old_value = old_axes[axis]
        if new_value == old_value:
            continue
        new_axes[axis] = new_value
        changes.append(AxisChange(
            axis=axis,
            old=old_value,
            new=new_value,
            reason=str(item.get("reason", "")).strip() or "information nouvelle",
        ))

    if not changes:
        return RevisionProposal(
            task_id, task["titre"], note, [],
            row["priorite"], float(row["score_global"]),
            row["priorite"], float(row["score_global"]),
            str(suggested.get("explanation", "")).strip()
            or "Aucune modification utile détectée.",
            None,
        )

    task_row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    estimation = Estimation(task_row["estimation"] or Estimation.INCONNUE.value)
    deadline_days = None
    if task_row["deadline_reelle"]:
        try:
            import datetime as dt
            deadline_days = (
                dt.date.fromisoformat(task_row["deadline_reelle"]) - dt.date.today()
            ).days
        except ValueError:
            deadline_days = None
    result = scoring.score(
        new_axes,
        estimation=estimation,
        deadline_days=deadline_days,
        incertitudes={},
        mode="revision_llm",
        subjective=None,
    )
    return RevisionProposal(
        task_id, task["titre"], note, changes,
        row["priorite"], float(row["score_global"]),
        result.priorite.value, result.global_,
        str(suggested.get("explanation", "")).strip()
        or "Le LLM propose d'intégrer cette information dans les axes.",
        result,
    )


def make_manual_proposal(conn, task_id: int, note: str,
                         axis_code: str, value: int) -> RevisionProposal | None:
    ctx = build_context(conn, task_id)
    if ctx is None:
        return None
    task = ctx["task"]
    row = db.last_evaluation(conn, task_id)
    old_axes = axes_from_evaluation(row)
    axis = Axis(axis_code.upper())
    if not 0 <= value <= AXIS_MAX[axis]:
        raise ValueError(f"{axis.value} doit être entre 0 et {AXIS_MAX[axis]}")
    old_value = old_axes[axis]
    if value == old_value:
        return RevisionProposal(
            task_id, task["titre"], note, [],
            row["priorite"], float(row["score_global"]),
            row["priorite"], float(row["score_global"]),
            "La valeur saisie est identique à l'évaluation actuelle.",
            None,
        )
    new_axes = dict(old_axes)
    new_axes[axis] = value
    task_row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    estimation = Estimation(task_row["estimation"] or Estimation.INCONNUE.value)
    deadline_days = None
    if task_row["deadline_reelle"]:
        try:
            import datetime as dt
            deadline_days = (
                dt.date.fromisoformat(task_row["deadline_reelle"]) - dt.date.today()
            ).days
        except ValueError:
            deadline_days = None
    result = scoring.score(
        new_axes,
        estimation=estimation,
        deadline_days=deadline_days,
        incertitudes={},
        mode="revision_manuelle",
        subjective=None,
    )
    return RevisionProposal(
        task_id, task["titre"], note,
        [AxisChange(axis, old_value, value, "Correction saisie manuellement.")],
        row["priorite"], float(row["score_global"]),
        result.priorite.value, result.global_,
        "Révision manuelle : tu as indiqué explicitement l'axe à modifier.",
        result,
    )


def render_proposal(p: RevisionProposal) -> str:
    if not p.has_changes:
        return (
            f"#{p.task_id} {p.task_title}\n"
            f"Aucune modification proposée.\n\n{p.explanation}"
        )
    lines = [
        f"#{p.task_id} {p.task_title}",
        "Le LLM propose une révision, à confirmer :",
        "",
        p.explanation,
        "",
        f"Priorité : {p.old_priority} ({p.old_score:.0f}) -> "
        f"{p.new_priority} ({p.new_score:.0f})",
        "",
        "Axes modifiés :",
    ]
    for ch in p.changes:
        lines.append(
            f"- {ch.axis.value}: {ch.old} ({AXIS_LABELS[ch.axis][ch.old]}) -> "
            f"{ch.new} ({AXIS_LABELS[ch.axis][ch.new]}) : {ch.reason}"
        )
    lines.append("")
    lines.append("Rien n'est modifié tant que tu ne confirmes pas.")
    return "\n".join(lines)


def apply_proposal(conn, p: RevisionProposal) -> int:
    if not p.has_changes or p.result is None:
        raise ValueError("proposition vide")
    eval_id = db.save_evaluation(conn, p.task_id, None, p.result, None)
    flags = biases.detect(
        {Axis(code): data["valeur"]
         for code, data in p.result.justification["axes"].items()},
        p.result.importance,
        p.result.priorite,
        Metadata(),
    )
    db.save_bias_flags(conn, eval_id, flags)
    db.add_task_note(conn, p.task_id, "revision_llm", p.note)
    return eval_id
