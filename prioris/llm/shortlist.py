"""Deterministic candidate selection before semantic LLM classification."""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

_STOPWORDS = {
    "avec", "cette", "dans", "des", "doit", "elle", "est", "faire", "il",
    "les", "pour", "que", "qui", "sur", "une", "the", "this", "that",
    "with", "from", "have", "will", "task",
}


def _normalized(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", _normalized(text))
            if len(token) >= 3 and token not in _STOPWORDS}


def shortlist_tasks(tasks: list[tuple[int, str]], note: str,
                    limit: int = 5) -> list[tuple[int, str]]:
    """Return at most `limit` lexically plausible tasks in deterministic order."""
    note_norm = _normalized(note)
    note_tokens = _tokens(note)
    ranked = []
    for task_id, title in tasks:
        title_norm = _normalized(title)
        title_tokens = _tokens(title)
        overlap = len(note_tokens & title_tokens)
        fuzzy = SequenceMatcher(None, note_norm, title_norm).ratio()
        if overlap == 0 and fuzzy < 0.55:
            continue
        coverage = overlap / max(len(title_tokens), 1)
        ranked.append((overlap * 10 + coverage + fuzzy, task_id, title))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [(task_id, title) for _, task_id, title in ranked[:limit]]
