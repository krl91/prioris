"""Operational LLM diagnostics: warm-up and file logging."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

DEFAULT_LOG_PATH = Path("logs/llm.log")


def append_log(message: str, log_path: str | Path = DEFAULT_LOG_PATH) -> Path:
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now().isoformat(timespec="seconds")
    with path.open("a", encoding="utf-8") as f:
        f.write(f"[{now}] {message}\n")
    return path


def warm_up_with_retries(facade, attempts: int = 3,
                         log_path: str | Path = DEFAULT_LOG_PATH) -> tuple[bool, str, Path]:
    path = Path(log_path)
    if facade is None or not facade.available:
        append_log("LLM indisponible : facade absente ou enabled=false", path)
        return False, "LLM désactivé ou non configuré", path

    last_error = ""
    for i in range(1, attempts + 1):
        ok = facade.warm_up()
        if ok:
            append_log(f"warmup tentative {i}/{attempts} : OK", path)
            return True, f"LLM prêt après {i}/{attempts} tentative(s)", path
        last_error = getattr(facade, "last_error", None) or "échec sans détail"
        append_log(f"warmup tentative {i}/{attempts} : KO : {last_error}", path)
    return False, f"LLM KO après {attempts} tentative(s) : {last_error}", path
