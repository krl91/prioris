"""Shared types for LLM clients."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LocalGGUFConfig:
    runner_path: str
    model_path: str
    timeout_s: float
    max_tokens: int
