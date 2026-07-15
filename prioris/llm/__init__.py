"""PRIORIS LLM layer: enrichment only, never decision-making (§1.4, §1.5).

The whole system works without this package: any failure here falls back to
button-driven flows instead of surfacing a user error.
"""
from .client import ChatClient, LLMConfig, resolve  # noqa: F401
from .facade import InterpretedAnswer, LLMFacade    # noqa: F401
