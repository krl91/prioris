"""Impact analysis for free-form information against existing tasks."""
from __future__ import annotations

from dataclasses import dataclass

from .store import db


@dataclass(frozen=True)
class ImpactedTask:
    id: int
    title: str
    impact: str


@dataclass(frozen=True)
class ImpactProposal:
    note: str
    impacted: list[ImpactedTask]
    new_task_title: str
    suggested_deadline: str
    direct_answer: str
    explanation: str

    @property
    def has_impacted(self) -> bool:
        return bool(self.impacted)


def make_proposal(conn, note: str, llm) -> ImpactProposal | None:
    rows = db.current_tasks(conn)
    tasks = [(r["id"], r["titre"]) for r in rows]
    if not llm or not llm.available:
        return None
    suggested = llm.impacted_tasks(tasks, note)
    if suggested is None:
        return None
    titles = {task_id: title for task_id, title in tasks}
    impacted = [
        ImpactedTask(i["id"], titles.get(i["id"], f"#{i['id']}"), i["impact"])
        for i in suggested.get("impacted", [])
        if i["id"] in titles
    ]
    return ImpactProposal(
        note=note,
        impacted=impacted,
        new_task_title=str(suggested.get("new_task_title", "")).strip()
                       or note.strip(),
        suggested_deadline=str(suggested.get("suggested_deadline", "")).strip(),
        direct_answer=str(suggested.get("direct_answer", "")).strip(),
        explanation=str(suggested.get("explanation", "")).strip()
                    or "Analyse d'impact terminée.",
    )


def render_proposal(p: ImpactProposal) -> str:
    lines = ["Analyse d'impact de l'information :", p.note, "", p.explanation, ""]
    if p.direct_answer:
        lines.extend(["Réponse directe :", p.direct_answer, ""])
    if p.impacted:
        lines.append("Tâches potentiellement impactées :")
        for item in p.impacted:
            lines.append(f"- #{item.id} {item.title} : {item.impact}")
        lines.append("")
        lines.append("Choisis les tâches à analyser ; rien n'est modifié sans confirmation.")
    else:
        lines.append("Aucune tâche existante ne semble clairement impactée.")
        lines.append(f"Nouvelle tâche proposée : {p.new_task_title}")
    if p.suggested_deadline:
        lines.append(f"Date limite détectée : {p.suggested_deadline}")
    return "\n".join(lines)
