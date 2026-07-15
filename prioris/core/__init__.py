"""Deterministic PRIORIS core: pure functions, no I/O, no LLM.

Architecture constraint: this package imports neither prioris.store,
prioris.bot, prioris.vault, nor any LLM or network client. Enforced by
tests/test_architecture.py.
"""
