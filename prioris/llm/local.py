"""Local PRIORIS interpreter, without an external model or server.

This module is not a generative LLM. It provides deterministic, conservative
NLU for the interview flow: extracting a likely axis value, suggesting a goal
by lexical overlap, and answering diagnostics. Everything remains confirmed by
the user before scoring.
"""
from __future__ import annotations

import json
import re
import unicodedata
import datetime as dt

from ..core.axes import AXIS_MAX, AXIS_MEDIAN, Axis
from . import prompts


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).strip()


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]{3,}", _norm(text))
    stop = {
        "une", "des", "les", "pour", "avec", "dans", "sur", "pas", "plus",
        "moins", "faire", "fait", "tache", "mettre", "jour", "cette",
        "cela", "elle", "il", "est", "sont", "mon", "mes", "ton", "tes",
    }
    return {w for w in words if w not in stop}


UNCERTAIN = (
    "je ne sais pas", "aucune idee", "pas sur", "pas sûr", "peut etre",
    "peut-être", "je pense", "je crois", "sans doute", "ca depend",
    "ça depend", "probablement", "peut-etre",
)


AXIS_PATTERNS: dict[Axis, list[tuple[int, tuple[str, ...]]]] = {
    Axis.BLK: [
        (5, ("plusieurs equipes", "tout le monde", "beaucoup de monde")),
        (4, ("client", "utilisateur final", "externe")),
        (3, ("equipe", "l'equipe", "notre equipe")),
        (2, ("marie", "paul", "quelqu'un", "collegue", "une personne")),
        (1, ("moi", "moi seul", "personne d'autre")),
        (0, ("personne", "aucun blocage", "personne n'est bloque")),
    ],
    Axis.CDR: [
        (4, ("deadline", "date limite", "tout se joue", "bloquant a partir")),
        (3, ("aggrave", "de pire en pire", "explose")),
        (2, ("nettement", "augmente", "plus cher", "s'accumule")),
        (1, ("doucement", "un peu", "legerement")),
        (0, ("rien", "ne bouge pas", "aucun cout", "pas de cout")),
    ],
    Axis.IMP: [
        (4, ("structurant", "strategique", "decisif", "tres important")),
        (3, ("majeur", "grosse difference", "important")),
        (2, ("notable", "utile", "vraie difference")),
        (1, ("confort", "petit plus", "leger")),
        (0, ("negligeable", "rien", "pas grand chose")),
    ],
    Axis.IRR: [
        (3, ("irreversible", "impossible a rattraper", "perdu")),
        (2, ("jusqu'a une date", "date limite", "apres ce sera trop tard")),
        (1, ("rattrapable", "avec effort", "possible mais")),
        (0, ("reversible", "on peut revenir", "aucun probleme")),
    ],
    Axis.INA: [
        (4, ("degats", "irrecuparable", "catastrophe")),
        (3, ("crise", "grave", "bloquant")),
        (2, ("probleme", "vrai probleme", "embetant")),
        (1, ("gene", "inconfort", "petite gene")),
        (0, ("rien", "rien du tout", "pas grave", "aucun impact")),
    ],
    Axis.HOR: [
        (4, ("deja visible", "maintenant", "aujourd'hui")),
        (3, ("cette semaine", "dans quelques jours")),
        (2, ("2 semaines", "deux semaines", "ce mois", "dans un mois")),
        (1, ("plus d'un mois", "plus tard")),
        (0, ("jamais", "pas visible")),
    ],
    Axis.ALN: [
        (3, ("majeur", "directement essentiel", "objectif principal")),
        (2, ("direct", "directement", "contribue")),
        (1, ("indirect", "un peu", "aide")),
        (0, ("aucun", "pas d'objectif", "rien a voir")),
    ],
}


def _interpret(payload: dict) -> dict:
    axis = Axis(payload["axe"])
    text = _norm(payload.get("reponse_utilisateur", ""))
    incertitude = 0
    if any(p in text for p in (_norm(x) for x in UNCERTAIN)):
        incertitude = 2 if "sais pas" in text or "aucune idee" in text else 1
    valeur = AXIS_MEDIAN[axis] if incertitude == 2 else None
    for candidate, patterns in AXIS_PATTERNS[axis]:
        if any(_norm(p) in text for p in patterns):
            valeur = candidate
            break
    if valeur is None:
        valeur = AXIS_MEDIAN[axis]
        incertitude = max(incertitude, 1)
    return {
        "valeur": int(valeur),
        "incertitude": incertitude,
        "reformulation": "Tu indiques : " + (payload.get("reponse_utilisateur", "").strip() or "réponse imprécise") + ".",
    }


def _interpret_question(payload: dict) -> dict:
    text = _norm(payload.get("reponse_utilisateur", ""))
    options = payload.get("options", [])
    incertitude = 0
    if any(p in text for p in (_norm(x) for x in UNCERTAIN)):
        incertitude = 2 if "sais pas" in text or "aucune idee" in text else 1

    def option_by_value(value: str):
        for opt in options:
            if str(opt.get("value")) == value:
                return opt
        return None

    value = None
    if re.search(r"\bp\s*1\b", text) or "urgent et important" in text:
        value = "P1"
    elif re.search(r"\bp\s*2\b", text) or "important pas urgent" in text:
        value = "P2"
    elif re.search(r"\bp\s*3\b", text) or "urgent pas important" in text:
        value = "P3"
    elif re.search(r"\bp\s*4\b", text) or "ni urgent" in text:
        value = "P4"
    elif "client" in text:
        value = "client"
    elif "manager" in text or "chef" in text:
        value = "manager"
    elif "collegue" in text or "collègue" in text:
        value = "collegue"
    elif "moi" in text:
        value = "moi"
    elif "faible" in text or "peu" in text:
        value = "1"
    elif "eleve" in text or "élevé" in text or "fort" in text:
        value = "3"
    elif "moyen" in text or "normal" in text:
        value = "2"
    elif "aucun" in text or "nulle" in text or "rien" in text:
        value = "0"
    elif "15" in text and ("30" not in text):
        value = "LT15"
    elif "30" in text and "60" not in text:
        value = "M15_30"
    elif "60" in text or "1 h" in text or "1h" in text:
        value = "M30_60"
    elif "2 h" in text or "2h" in text:
        value = "H1_2"
    elif "4 h" in text or "4h" in text:
        value = "H2_4"
    elif "plus de 4" in text or ">4" in text:
        value = "GT4"

    if value is None or option_by_value(value) is None:
        value = str(options[0].get("value")) if options else ""
        incertitude = max(incertitude, 1)
    if incertitude == 2 and option_by_value("?") is not None:
        value = "?"
    return {
        "value": value,
        "incertitude": incertitude,
        "reformulation": "Tu indiques : " + (
            payload.get("reponse_utilisateur", "").strip() or "réponse imprécise"
        ) + ".",
    }


def _goal_match(payload: dict) -> dict:
    task_tokens = _tokens(payload.get("tache", ""))
    best_id = None
    best_score = 0
    for goal in payload.get("objectifs", []):
        score = len(task_tokens & _tokens(goal.get("titre", "")))
        if score > best_score:
            best_id = goal.get("id")
            best_score = score
    return {"goal_id": best_id if best_score >= 1 else None}


def _goal_audit(payload: dict) -> dict:
    goal_tokens = _tokens(payload.get("objectif", ""))
    douteuses = []
    if not goal_tokens:
        return {"douteuses": douteuses}
    for task in payload.get("taches", []):
        if not (_tokens(task.get("titre", "")) & goal_tokens):
            douteuses.append({
                "id": task.get("id"),
                "raison": "Aucun mot-clé commun évident avec l'objectif.",
            })
    return {"douteuses": douteuses}


def _task_revision(payload: dict) -> dict:
    text = _norm(payload.get("information_nouvelle", ""))
    current = payload.get("evaluation_actuelle", {}).get("axes", {})
    changes = []
    for axis, patterns in AXIS_PATTERNS.items():
        best = None
        for candidate, words in patterns:
            if any(_norm(p) in text for p in words):
                best = candidate
                break
        if best is None:
            continue
        old = current.get(axis.value, {}).get("valeur")
        if old is not None and best != old and 0 <= best <= AXIS_MAX[axis]:
            changes.append({
                "axis": axis.value,
                "value": best,
                "reason": "L'information nouvelle correspond à cette valeur d'axe.",
            })
    return {
        "changes": changes[:3],
        "explanation": (
            "Je propose d'intégrer uniquement les éléments factuels explicites "
            "dans les axes concernés."
            if changes else
            "Je ne vois pas d'élément assez clair pour modifier le calcul."
        ),
    }


def _task_impact(payload: dict) -> dict:
    info = payload.get("information", "")
    today = dt.date.fromisoformat(payload.get("date_du_jour", dt.date.today().isoformat()))
    norm_info = _norm(info)
    suggested_deadline = ""
    if re.search(r"\b\d{4}-\d{2}-\d{2}\b", info):
        suggested_deadline = re.search(r"\b\d{4}-\d{2}-\d{2}\b", info).group(0)
    elif any(p in norm_info for p in ("ce soir", "aujourd'hui", "d'ici une heure", "dans une heure")):
        suggested_deadline = today.isoformat()
    elif "demain" in norm_info:
        suggested_deadline = (today + dt.timedelta(days=1)).isoformat()
    is_question = "?" in info or _norm(info).startswith(
        ("est ce", "est-ce", "que ", "quoi", "qui", "comment", "pourquoi",
         "quelle", "quel", "quand", "peux", "dois"))
    direct_answer = (
        "D'après les informations disponibles, regarde les tâches listées ci-dessous."
        if is_question else ""
    )
    info_tokens = _tokens(info)
    impacted = []
    for task in payload.get("taches_existantes", []):
        title = task.get("titre", "")
        if _tokens(title) & info_tokens:
            impacted.append({
                "id": task.get("id"),
                "impact": "L'information partage des éléments explicites avec cette tâche.",
            })
    if impacted:
        return {
            "impacted": impacted[:5],
            "new_task_title": "",
            "suggested_deadline": suggested_deadline,
            "direct_answer": direct_answer,
            "explanation": "Une ou plusieurs tâches existantes semblent concernées.",
        }
    title = info.strip()
    if len(title) > 80:
        title = title[:77].rstrip() + "..."
    return {
        "impacted": [],
        "new_task_title": title or "Nouvelle tâche issue de l'information",
        "suggested_deadline": suggested_deadline,
        "direct_answer": (
            "Je ne vois pas de tâche existante permettant de répondre clairement ; "
            "je propose d'en créer une."
            if is_question else ""
        ),
        "explanation": "Aucune tâche existante ne semble clairement impactée.",
    }


def _quadrant_questions(payload: dict) -> dict:
    title = payload.get("tache", "").strip() or "cette tâche"
    lang = payload.get("langue", "français")
    if lang == "anglais":
        return {"questions": [
            f"What concrete problem appears if '{title}' is not done today or this week?",
            f"Who benefits or is blocked if '{title}' is completed versus postponed?",
            f"Is there a real deadline or cost of delay for '{title}', or only pressure?",
        ]}
    return {"questions": [
        f"Quel problème concret apparaît si « {title} » n'est pas fait aujourd'hui ou cette semaine ?",
        f"Qui bénéficie ou reste bloqué si « {title} » est fait plutôt que reporté ?",
        f"Y a-t-il une vraie échéance ou un coût du retard pour « {title} », ou seulement de la pression ?",
    ]}


def _subjective_challenge(payload: dict) -> dict:
    title = payload.get("tache", "").strip() or "cette tâche"
    subjective = payload.get("classement_instinctif", "")
    lang = payload.get("langue", "français")
    if lang == "anglais":
        return {"questions": [
            f"What hard deadline or real damage would make '{title}' truly {subjective}?",
            f"Are you reacting to external pressure/visibility, or to measurable impact?",
            f"What fact would make you downgrade or upgrade your first instinct?",
        ]}
    return {"questions": [
        f"Quel fait concret rend vraiment « {title} » compatible avec {subjective} ?",
        "Réagis-tu à une pression/visibilité externe, ou à un impact mesurable ?",
        "Quel élément te ferait baisser ou monter ce classement instinctif ?",
    ]}


def chat(system: str, user: str) -> str:
    """Return a JSON response compatible with ChatClient.chat."""
    if '"ping": true' in user:
        return '{"pong": true}'
    if '{"ok": true}' in user or '"ok": true' in user:
        return '{"ok": true}'
    payload = json.loads(user)
    if system == prompts.INTERVIEWER_SYSTEM:
        return json.dumps(_interpret(payload), ensure_ascii=False)
    if system == prompts.QUESTION_INTERPRETER_SYSTEM:
        return json.dumps(_interpret_question(payload), ensure_ascii=False)
    if system == prompts.GOAL_MATCH_SYSTEM:
        return json.dumps(_goal_match(payload), ensure_ascii=False)
    if system == prompts.GOAL_AUDIT_SYSTEM:
        return json.dumps(_goal_audit(payload), ensure_ascii=False)
    if system == prompts.TASK_REVISION_SYSTEM:
        return json.dumps(_task_revision(payload), ensure_ascii=False)
    if system == prompts.TASK_IMPACT_SYSTEM:
        return json.dumps(_task_impact(payload), ensure_ascii=False)
    if system == prompts.QUADRANT_QUESTIONS_SYSTEM:
        return json.dumps(_quadrant_questions(payload), ensure_ascii=False)
    if system == prompts.SUBJECTIVE_CHALLENGE_SYSTEM:
        return json.dumps(_subjective_challenge(payload), ensure_ascii=False)
    return "{}"
