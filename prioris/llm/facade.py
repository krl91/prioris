"""Single LLM facade: the only LLM contact point for the rest of the code.

Guarantees:
- never raises outward: failure returns None and the UI falls back to buttons;
- strict output validation: out-of-scale values are rejected;
- at most two attempts before fallback;
- extracted values never enter scoring without user confirmation.
"""
from __future__ import annotations

import json
import re
import time
import datetime as dt
import unicodedata
from dataclasses import dataclass
from typing import Callable

from ..core.axes import AXIS_MAX, Axis
from . import prompts
from .client import ChatClient, LLMError
from .shortlist import shortlist_tasks

MAX_ATTEMPTS = 2

# log_fn(type, model, latency_ms, ok), usually backed by store.db.log_llm_call.
LogFn = Callable[[str, str, int, bool], None]


@dataclass(frozen=True)
class InterpretedAnswer:
    axis: Axis
    valeur: int
    incertitude: int          # 0 | 1 | 2
    reformulation: str


@dataclass(frozen=True)
class InterpretedQuestionAnswer:
    value: str
    incertitude: int          # 0 | 1 | 2
    reformulation: str


def _extract_json(text: str) -> dict:
    """Tolerate markdown fences and stray text around the JSON object."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\s*|\s*```$", "", text, flags=re.S)
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        raise ValueError("aucun objet JSON dans la sortie")
    return json.loads(match.group(0))


def _validate(axis: Axis, data: dict) -> InterpretedAnswer:
    _require_confidence(data)
    valeur = data["valeur"]
    incertitude = data.get("incertitude", 0)
    reformulation = str(data.get("reformulation", "")).strip()
    if not isinstance(valeur, int) or isinstance(valeur, bool):
        raise ValueError(f"valeur non entière : {valeur!r}")
    if not 0 <= valeur <= AXIS_MAX[axis]:
        raise ValueError(f"valeur {valeur} hors échelle 0..{AXIS_MAX[axis]}")
    if incertitude not in (0, 1, 2):
        raise ValueError(f"incertitude invalide : {incertitude!r}")
    if not reformulation:
        raise ValueError("reformulation vide")
    return InterpretedAnswer(axis, valeur, int(incertitude), reformulation)


def _require_confidence(data: dict, minimum: float = 0.55) -> None:
    """Reject explicit abstention or a low-confidence model proposal."""
    status = str(data.get("status", "ok")).lower()
    confidence = data.get("confidence", 1.0)
    if status == "abstain":
        raise ValueError("le LLM s'abstient")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise ValueError("confidence invalide")
    if not 0 <= float(confidence) <= 1:
        raise ValueError("confidence hors intervalle 0..1")
    if float(confidence) < minimum:
        raise ValueError(f"confiance insuffisante : {confidence}")


def _normalize_free_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    normalized = "".join(
        char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", normalized).strip()


def _contests_premise(text: str) -> bool:
    """Recognize an explicit rejection even when a small model abstains."""
    normalized = _normalize_free_text(text)
    return any(phrase in normalized for phrase in (
        "premisse fausse",
        "premisse est fausse",
        "question fausse",
        "question est fausse",
        "information fausse",
        "information est fausse",
        "comporte une information fausse",
        "contient une information fausse",
        "hypothese fausse",
        "premise is false",
        "question is false",
        "contains false information",
        "ce n est pas vrai",
        "c est faux",
        "au contraire",
    ))


def _has_scorable_challenge_fact(text: str) -> bool:
    """Detect whether a premise rejection also contains a usable fact."""
    normalized = _normalize_free_text(text)
    markers = (
        "deadline", "echeance", "retard", "ce soir", "demain",
        "aujourd hui", "avant midi", "avant ce soir", "dois agir",
        "faut agir", "agir maintenant", "action immediate", "immediatement",
        "bloque", "attend", "depend", "impact", "important", "objectif",
        "consequence", "irreversible", "irreversibilite",
    )
    return any(marker in normalized for marker in markers) or bool(
        re.search(r"\b(?:avant|d ici)\s+\d{1,2}(?:\s*h\s*\d{0,2})?\b", normalized)
    )


def _binary_answer(text: str) -> bool | None:
    """Return an unambiguous short yes/no answer, otherwise None."""
    normalized = _normalize_free_text(text)
    if normalized in {"non", "no", "pas du tout", "absolument pas", "aucunement"}:
        return False
    if normalized in {"oui", "yes", "si", "tout a fait", "absolument"}:
        return True
    return None


def _deterministic_question_answer(
    options: list[tuple[str, str]],
    user_text: str,
    language: str,
) -> InterpretedQuestionAnswer | None:
    """Resolve only unambiguous option answers before invoking a model."""
    normalized = _normalize_free_text(user_text)
    normalized_options = [
        (_normalize_free_text(label), value) for label, value in options
    ]

    def find_option(*fragments: str) -> str | None:
        for label, value in normalized_options:
            if any(fragment in label for fragment in fragments):
                return value
        return None

    exact = next(
        (value for label, value in normalized_options if normalized == label),
        None,
    )
    binary = _binary_answer(user_text)
    if exact is not None:
        value, meaning = exact, "l'option indiquée"
    elif binary is not None:
        value = find_option("oui") if binary else find_option("non")
        meaning = "une réponse affirmative" if binary else "une réponse négative"
    elif any(phrase in normalized for phrase in (
            "je ne sais pas", "aucune idee", "impossible a dire")):
        value = find_option("sais pas", "aucune idee", "inconnu")
        meaning = "une incertitude explicite"
    else:
        value = None
        meaning = ""

    is_mirror_consequence = (
        find_option("vrai probleme") is not None
        and find_option("rien de grave") is not None
    )
    if value is None and is_mirror_consequence:
        harmless = any(phrase in normalized for phrase in (
            "rien de grave", "pas grave", "aucun probleme",
            "aucune consequence", "peut attendre", "sans consequence",
        ))
        severe = any(word in normalized.split() for word in (
            "meurs", "meurt", "mourir", "mort", "vital", "vitale",
            "survie", "danger", "grave",
        )) or any(phrase in normalized for phrase in (
            "pour vivre", "risque de mourir", "besoin de manger",
        ))
        if harmless:
            value, meaning = find_option("rien de grave"), "aucune conséquence grave"
        elif severe:
            value, meaning = find_option("vrai probleme"), "une conséquence grave ou vitale"

    if value is None:
        return None
    reformulation = (
        f"You clearly indicate {meaning}."
        if language == "en" else f"Tu indiques clairement {meaning}."
    )
    return InterpretedQuestionAnswer(
        value=value,
        incertitude=0,
        reformulation=reformulation,
    )


class LLMFacade:
    def __init__(self, client: ChatClient | None, log_fn: LogFn | None = None):
        self._client = client
        self._log_fn = log_fn or (lambda *a: None)
        self.last_error: str | None = None   # last failure cause for diagnostics

    def _log(self, type_: str, modele: str, ms: int, ok: bool) -> None:
        """Logging must never break the facade."""
        try:
            self._log_fn(type_, modele, ms, ok)
        except Exception:
            pass

    @property
    def available(self) -> bool:
        return self._client is not None and self._client.cfg.enabled

    def interpret_answer(self, axis: Axis, question: str,
                         user_text: str) -> InterpretedAnswer | None:
        """Convert free text to a candidate axis value. None means button fallback."""
        if not self.available:
            self.last_error = "LLM désactivé (enabled = false ou section absente)"
            return None
        payload = prompts.build_interpret_payload(axis, question, user_text)
        model = self._client.cfg.model
        for attempt in range(1, MAX_ATTEMPTS + 1):
            t0 = time.monotonic()
            try:
                raw = self._client.chat(prompts.INTERVIEWER_SYSTEM, payload,
                                        max_tokens=160)
                result = _validate(axis, _extract_json(raw))
            except (LLMError, TypeError, ValueError, KeyError,
                    json.JSONDecodeError) as e:
                self.last_error = f"tentative {attempt}/{MAX_ATTEMPTS} : {e}"
                self._log("nlu", model, int((time.monotonic() - t0) * 1000), False)
                continue
            self.last_error = None
            self._log("nlu", model, int((time.monotonic() - t0) * 1000), True)
            return result
        return None

    def interpret_question_answer(
        self,
        question: str,
        options: list[tuple[str, str]],
        user_text: str,
        language: str = "fr",
    ) -> InterpretedQuestionAnswer | None:
        """Convert free text to one existing button option."""
        if not self.available:
            self.last_error = "LLM désactivé (enabled = false ou section absente)"
            return None
        deterministic = _deterministic_question_answer(
            options, user_text, language)
        if deterministic is not None:
            self.last_error = None
            self._log("question_nlu", self._client.cfg.model, 0, True)
            return deterministic
        valid_values = {value for _, value in options}
        payload = prompts.build_question_interpret_payload(
            question, options, user_text, language)
        model = self._client.cfg.model
        for attempt in range(1, MAX_ATTEMPTS + 1):
            t0 = time.monotonic()
            try:
                raw = self._client.chat(prompts.QUESTION_INTERPRETER_SYSTEM, payload,
                                        max_tokens=160)
                data = _extract_json(raw)
                _require_confidence(data)
                value = str(data["value"]).strip()
                incertitude = data.get("incertitude", 0)
                reformulation = str(data.get("reformulation", "")).strip()
                if value not in valid_values:
                    raise ValueError(f"value invalide : {value!r}")
                if incertitude not in (0, 1, 2):
                    raise ValueError(f"incertitude invalide : {incertitude!r}")
                if not reformulation:
                    raise ValueError("reformulation vide")
                result = InterpretedQuestionAnswer(
                    value=value,
                    incertitude=int(incertitude),
                    reformulation=reformulation,
                )
            except (LLMError, ValueError, KeyError, json.JSONDecodeError) as e:
                self.last_error = f"tentative {attempt}/{MAX_ATTEMPTS} : {e}"
                self._log("question_nlu", model,
                          int((time.monotonic() - t0) * 1000), False)
                continue
            self.last_error = None
            self._log("question_nlu", model,
                      int((time.monotonic() - t0) * 1000), True)
            return result
        return None

    def suggest_goal(self, task_title: str,
                     goals: list[tuple[int, str]]) -> int | None:
        """Suggest the matching goal id, or None when unclear or unavailable.

        Suggestions are never applied without a button confirmation.
        """
        if not self.available or not goals:
            return None
        valid_ids = {i for i, _ in goals}
        payload = prompts.build_goal_match_payload(task_title, goals)
        model = self._client.cfg.model
        for _ in range(MAX_ATTEMPTS):
            t0 = time.monotonic()
            try:
                raw = self._client.chat(prompts.GOAL_MATCH_SYSTEM, payload,
                                        max_tokens=32)
                data = _extract_json(raw)
                _require_confidence(data)
                gid = data.get("goal_id")
                if gid is not None and (not isinstance(gid, int)
                                        or gid not in valid_ids):
                    raise ValueError(f"goal_id invalide : {gid!r}")
            except (LLMError, ValueError, KeyError, json.JSONDecodeError):
                self._log("goal_match", model,
                          int((time.monotonic() - t0) * 1000), False)
                continue
            self._log("goal_match", model,
                      int((time.monotonic() - t0) * 1000), True)
            return gid
        return None

    def audit_goal(self, goal_title: str,
                   tasks: list[tuple[int, str]]) -> list[dict] | None:
        """Return dubious tasks for this goal as [{"id", "raison"}].

        [] means everything is coherent; None means unavailable or failed LLM.
        """
        if not self.available or not tasks:
            return None if not self.available else []
        valid_ids = {i for i, _ in tasks}
        payload = prompts.build_goal_audit_payload(goal_title, tasks)
        model = self._client.cfg.model
        for _ in range(MAX_ATTEMPTS):
            t0 = time.monotonic()
            try:
                raw = self._client.chat(prompts.GOAL_AUDIT_SYSTEM, payload,
                                        max_tokens=192)
                data = _extract_json(raw)
                _require_confidence(data)
                douteuses = data.get("douteuses", [])
                if not isinstance(douteuses, list):
                    raise ValueError("douteuses n'est pas une liste")
                result = []
                for d in douteuses:
                    if not isinstance(d.get("id"), int) or d["id"] not in valid_ids:
                        raise ValueError(f"id douteux invalide : {d!r}")
                    result.append({"id": d["id"],
                                   "raison": str(d.get("raison", "")).strip()
                                   or "lien peu clair avec l'objectif"})
            except (LLMError, ValueError, KeyError, AttributeError,
                    json.JSONDecodeError):
                self._log("goal_audit", model,
                          int((time.monotonic() - t0) * 1000), False)
                continue
            self._log("goal_audit", model,
                      int((time.monotonic() - t0) * 1000), True)
            return result
        return None

    def revise_task(self, context: dict, note: str) -> dict | None:
        """Turn new task information into candidate axis changes.

        The proposal is validated here, then confirmed by the UI before writes.
        """
        if not self.available:
            self.last_error = "LLM désactivé (enabled = false ou section absente)"
            return None
        payload = prompts.build_task_revision_payload(context, note)
        model = self._client.cfg.model
        valid_axes = set(context["evaluation"]["axes"])
        for attempt in range(1, MAX_ATTEMPTS + 1):
            t0 = time.monotonic()
            try:
                raw = self._client.chat(prompts.TASK_REVISION_SYSTEM, payload,
                                        max_tokens=256)
                data = _extract_json(raw)
                _require_confidence(data)
                changes = data.get("changes", [])
                if not isinstance(changes, list):
                    raise ValueError("changes n'est pas une liste")
                clean = []
                seen = set()
                for ch in changes:
                    axis_code = str(ch.get("axis", "")).upper()
                    axis = Axis(axis_code)
                    if axis_code not in valid_axes or axis_code in seen:
                        raise ValueError(f"axe invalide : {axis_code!r}")
                    value = ch.get("value")
                    if not isinstance(value, int) or isinstance(value, bool):
                        raise ValueError(f"valeur non entière : {value!r}")
                    if not 0 <= value <= AXIS_MAX[axis]:
                        raise ValueError(
                            f"{axis_code}={value} hors échelle 0..{AXIS_MAX[axis]}")
                    clean.append({
                        "axis": axis_code,
                        "value": value,
                        "reason": str(ch.get("reason", "")).strip()
                                  or "information nouvelle",
                    })
                    seen.add(axis_code)
                result = {
                    "changes": clean,
                    "explanation": str(data.get("explanation", "")).strip(),
                }
            except (LLMError, ValueError, KeyError, json.JSONDecodeError) as e:
                self.last_error = f"tentative {attempt}/{MAX_ATTEMPTS} : {e}"
                self._log("task_revision", model,
                          int((time.monotonic() - t0) * 1000), False)
                continue
            self.last_error = None
            self._log("task_revision", model,
                      int((time.monotonic() - t0) * 1000), True)
            return result
        return None

    def impacted_tasks(self, tasks: list[tuple[int, str]], note: str) -> dict | None:
        """Map global information to potentially impacted existing tasks.

        The list is an editable proposal on the UI side.
        """
        if not self.available:
            self.last_error = "LLM désactivé (enabled = false ou section absente)"
            return None
        candidates = shortlist_tasks(tasks, note)
        valid_ids = {i for i, _ in candidates}
        payload = prompts.build_task_impact_payload(candidates, note)
        model = self._client.cfg.model
        for attempt in range(1, MAX_ATTEMPTS + 1):
            t0 = time.monotonic()
            try:
                raw = self._client.chat(prompts.TASK_IMPACT_SYSTEM, payload,
                                        max_tokens=320)
                data = _extract_json(raw)
                _require_confidence(data)
                impacted = data.get("impacted", [])
                if not isinstance(impacted, list):
                    raise ValueError("impacted n'est pas une liste")
                clean = []
                seen = set()
                for item in impacted:
                    task_id = item.get("id")
                    if task_id is None:
                        continue
                    if not isinstance(task_id, int) or task_id not in valid_ids:
                        raise ValueError(f"id impacté invalide : {task_id!r}")
                    if task_id in seen:
                        continue
                    clean.append({
                        "id": task_id,
                        "impact": str(item.get("impact", "")).strip()
                                  or "impact à vérifier",
                    })
                    seen.add(task_id)
                result = {
                    "impacted": clean,
                    "new_task_title": str(data.get("new_task_title", "")).strip(),
                    "suggested_deadline": str(data.get("suggested_deadline", "")).strip(),
                    "direct_answer": str(data.get("direct_answer", "")).strip(),
                    "explanation": str(data.get("explanation", "")).strip(),
                }
                if result["suggested_deadline"]:
                    try:
                        dt.date.fromisoformat(result["suggested_deadline"])
                    except ValueError:
                        result["suggested_deadline"] = ""
            except (LLMError, ValueError, KeyError, json.JSONDecodeError) as e:
                self.last_error = f"tentative {attempt}/{MAX_ATTEMPTS} : {e}"
                self._log("task_impact", model,
                          int((time.monotonic() - t0) * 1000), False)
                continue
            self.last_error = None
            self._log("task_impact", model,
                      int((time.monotonic() - t0) * 1000), True)
            return result
        return None

    def subjective_challenge_questions(
        self,
        task_title: str,
        subjective: str,
        language: str = "fr",
    ) -> list[str] | None:
        """Challenge the user's instinctive quadrant without changing it."""
        if not self.available:
            self.last_error = "LLM désactivé (enabled = false ou section absente)"
            return None
        lang = "en" if language == "en" else "fr"
        payload = prompts.build_subjective_challenge_payload(
            task_title, subjective, lang)
        model = self._client.cfg.model
        for attempt in range(1, MAX_ATTEMPTS + 1):
            t0 = time.monotonic()
            try:
                raw = self._client.chat(prompts.SUBJECTIVE_CHALLENGE_SYSTEM, payload,
                                        max_tokens=192)
                data = _extract_json(raw)
                _require_confidence(data)
                questions = data.get("questions")
                if not isinstance(questions, list) or len(questions) != 3:
                    raise ValueError("questions doit contenir exactement 3 éléments")
                clean = []
                for question in questions:
                    text = str(question).strip()
                    if not text or len(text) > 220:
                        raise ValueError(f"question invalide : {question!r}")
                    clean.append(text)
            except (LLMError, ValueError, KeyError, json.JSONDecodeError) as e:
                self.last_error = f"tentative {attempt}/{MAX_ATTEMPTS} : {e}"
                self._log("subjective_challenge", model,
                          int((time.monotonic() - t0) * 1000), False)
                continue
            self.last_error = None
            self._log("subjective_challenge", model,
                      int((time.monotonic() - t0) * 1000), True)
            return clean
        return None

    def interpret_challenge_answer(
        self,
        task_title: str,
        subjective: str,
        question: str,
        user_text: str,
        current_axes: dict,
        language: str = "fr",
    ) -> dict | None:
        """Interpret a challenge answer without blocking on safe abstention."""
        if not self.available:
            self.last_error = "LLM désactivé (enabled = false ou section absente)"
            return None
        binary = _binary_answer(user_text)
        if binary is not None:
            if language == "en":
                reason = (
                    "Explicit yes: the question's hypothesis is confirmed, "
                    "without evidence supporting a numeric axis correction."
                    if binary else
                    "Explicit no: the question's hypothesis is rejected, "
                    "with no axis correction required."
                )
            else:
                reason = (
                    "Réponse affirmative explicite : l'hypothèse de la question "
                    "est confirmée, sans élément permettant de chiffrer un axe."
                    if binary else
                    "Réponse négative explicite : l'hypothèse de la question est "
                    "rejetée, sans correction d'axe nécessaire."
                )
            self.last_error = None
            self._log("challenge_answer", self._client.cfg.model, 0, True)
            return {
                "axis": None,
                "value": None,
                "uncertainty": 0,
                "reason": reason,
                "outcome": "no_change",
            }
        if (_contests_premise(user_text)
                and not _has_scorable_challenge_fact(user_text)):
            self.last_error = None
            self._log("challenge_answer", self._client.cfg.model, 0, True)
            return {
                "axis": None,
                "value": None,
                "uncertainty": 0,
                "reason": (
                    "The answer explicitly rejects the question's premise; "
                    "no factual axis correction is required."
                    if language == "en" else
                    "La réponse rejette explicitement la prémisse de la "
                    "question ; aucune correction factuelle d'axe n'est requise."
                ),
                "outcome": "premise_false",
            }
        lang = "en" if language == "en" else "fr"
        payload = prompts.build_challenge_answer_payload(
            task_title, subjective, question, user_text, current_axes, lang)
        model = self._client.cfg.model
        valid_axes = {axis.value for axis in Axis}
        max_by_axis = {axis.value: AXIS_MAX[axis] for axis in Axis}
        for attempt in range(1, MAX_ATTEMPTS + 1):
            t0 = time.monotonic()
            try:
                raw = self._client.chat(prompts.CHALLENGE_ANSWER_SYSTEM, payload,
                                        max_tokens=128)
                data = _extract_json(raw)
                status = str(data.get("status", "ok")).strip().lower()
                if status not in ("ok", "premise_false", "abstain"):
                    raise ValueError(f"status invalide : {status!r}")
                confidence = data.get("confidence", 1.0)
                if (not isinstance(confidence, (int, float))
                        or isinstance(confidence, bool)
                        or not 0 <= float(confidence) <= 1):
                    raise ValueError(f"confidence invalide : {confidence!r}")
                reason = str(data.get("reason", "")).strip()
                uncertainty = int(data.get("uncertainty", 0) or 0)
                if uncertainty not in (0, 1, 2):
                    raise ValueError(f"incertitude invalide : {uncertainty}")
                low_confidence = float(confidence) < 0.55
                premise_false = (
                    status == "premise_false" or _contests_premise(user_text)
                )
                if status == "abstain" or low_confidence:
                    result = {
                        "axis": None,
                        "value": None,
                        "uncertainty": max(uncertainty, 2),
                        "reason": reason or (
                            "La prémisse de la question est contestée, mais "
                            "aucun fait ne permet de modifier un axe."
                            if premise_false else
                            "Réponse conservée, sans fait assez précis pour "
                            "modifier un axe."
                        ),
                        "outcome": (
                            "premise_false" if premise_false else "no_change"
                        ),
                    }
                    self.last_error = None
                    self._log("challenge_answer", model,
                              int((time.monotonic() - t0) * 1000), True)
                    return result
                axis = data.get("axis")
                if axis in ("", None, "null"):
                    result = {
                        "axis": None,
                        "value": None,
                        "uncertainty": uncertainty,
                        "reason": reason or "Aucune correction d'axe nécessaire.",
                        "outcome": (
                            "premise_false" if premise_false
                            else "no_change"
                        ),
                    }
                else:
                    if axis not in valid_axes:
                        raise ValueError(f"axe invalide : {axis!r}")
                    value = int(data.get("value"))
                    if value < 0 or value > max_by_axis[axis]:
                        raise ValueError(f"valeur invalide pour {axis}: {value}")
                    result = {
                        "axis": axis,
                        "value": value,
                        "uncertainty": uncertainty,
                        "reason": reason or "Un fait justifie cette correction.",
                        "outcome": (
                            "premise_false" if premise_false
                            else "correction"
                        ),
                    }
            except (LLMError, TypeError, ValueError, KeyError,
                    json.JSONDecodeError) as e:
                self.last_error = f"tentative {attempt}/{MAX_ATTEMPTS} : {e}"
                self._log("challenge_answer", model,
                          int((time.monotonic() - t0) * 1000), False)
                continue
            self.last_error = None
            self._log("challenge_answer", model,
                      int((time.monotonic() - t0) * 1000), True)
            return result
        return None

    def warm_up(self) -> bool:
        """Load the model into memory through a tiny call.

        Run at startup and periodically: Ollama unloads after about five
        minutes of inactivity. Silent by contract: never raises, only logs.
        """
        if not self.available:
            self.last_error = "LLM désactivé (enabled = false ou section absente)"
            return False
        t0 = time.monotonic()
        try:
            self._client.chat("Réponds en JSON.",
                              '{"ping": true} → réponds {"pong": true}',
                              max_tokens=16)
            self._log("warmup", self._client.cfg.model,
                      int((time.monotonic() - t0) * 1000), True)
            self.last_error = None
            return True
        except (LLMError, Exception) as e:
            self.last_error = str(e)
            self._log("warmup", self._client.cfg.model,
                      int((time.monotonic() - t0) * 1000), False)
            return False

    def self_test(self) -> tuple[bool, str]:
        """Minimal provider round trip for the /llm command."""
        if self._client is None:
            return False, "aucun client configuré (section [llm] absente ?)"
        cfg = self._client.cfg
        if not cfg.enabled:
            return False, "désactivé (enabled = false)"
        t0 = time.monotonic()
        try:
            raw = self._client.chat(
                "Tu réponds uniquement en JSON.",
                'Réponds exactement : {"ok": true}')
            data = _extract_json(raw)
            ms = int((time.monotonic() - t0) * 1000)
            self._log("selftest", cfg.model, ms, True)
            if data.get("ok") is True:
                return True, f"OK — {cfg.provider} · {cfg.model} · {ms} ms"
            return True, (f"joignable ({ms} ms) mais réponse inattendue : "
                          f"{raw[:80]!r} — le modèle suit-il les consignes JSON ?")
        except (LLMError, ValueError, json.JSONDecodeError) as e:
            ms = int((time.monotonic() - t0) * 1000)
            self._log("selftest", cfg.model, ms, False)
            hint = ""
            msg = str(e).lower()
            if "timed out" in msg or "timeout" in msg:
                hint = (" → timeout : modèle en cours de chargement ? "
                        "Réessaie, ou augmente timeout_s dans [llm].")
            elif "refused" in msg or "refusé" in msg or "connection" in msg:
                hint = " → le serveur est-il lancé ? (ollama serve / LM Studio)"
            elif "404" in msg:
                hint = (" → modèle introuvable : vérifier le nom exact "
                        "(ollama list) dans [llm].model")
            elif "401" in msg:
                hint = " → api_key invalide ou absente"
            return False, f"échec après {ms} ms : {e}{hint}"
