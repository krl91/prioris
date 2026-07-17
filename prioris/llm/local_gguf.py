"""Local GGUF runtime through a bundled binary.

This provider can run a Ministral-like model without Ollama or LM Studio, as
long as the release also provides:
- a local llama.cpp-compatible inference binary (`llama-simple`);
- a local GGUF model file.

This module downloads nothing and does not use the shell.
"""
from __future__ import annotations

import subprocess
import re
import platform
from pathlib import Path

from .client_types import LocalGGUFConfig


def _assert_no_embedded_server(runner: Path) -> None:
    """Refuse llama.cpp launchers that can start a localhost server internally."""
    try:
        proc = subprocess.run(
            [str(runner), "--help"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return
    help_text = f"{proc.stdout}\n{proc.stderr}".lower()
    if "--server-base" in help_text or "instead of starting a new one" in help_text:
        raise RuntimeError(
            "runtime local refusé : ce binaire peut démarrer un serveur localhost. "
            "Utilise un runtime d'inférence pure sans port local."
        )


def _is_llama_simple(runner: Path) -> bool:
    if runner.name == "llama-simple":
        return True
    try:
        proc = subprocess.run(
            [str(runner), "--help"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    help_text = f"{proc.stdout}\n{proc.stderr}"
    return "example usage:" in help_text and "[-n n_predict]" in help_text


def _clear_macos_quarantine(runner: Path) -> None:
    """Best effort: downloaded release archives can quarantine bundled binaries."""
    if platform.system() != "Darwin":
        return
    subprocess.run(
        ["xattr", "-dr", "com.apple.quarantine", str(runner.parent)],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )


def _clean_stdout(text: str) -> str:
    """llama.cpp binaries may mix logs, prompt and answer on stdout."""
    fenced = re.findall(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.S)
    if fenced:
        return fenced[-1].strip()
    if "<|assistant|>" in text:
        text = text.rsplit("<|assistant|>", 1)[-1]
    text = re.sub(r"\[ Prompt:.*?\]", "", text, flags=re.S)
    text = text.replace("Exiting...", "")
    return text.strip()


def chat(cfg: LocalGGUFConfig, system: str, user: str) -> str:
    runner = Path(cfg.runner_path)
    model = Path(cfg.model_path)
    if not runner.exists():
        raise FileNotFoundError(f"runtime local introuvable : {runner}")
    if not model.exists():
        raise FileNotFoundError(f"modèle local introuvable : {model}")
    _clear_macos_quarantine(runner)
    _assert_no_embedded_server(runner)

    prompt = (
        "<|system|>\n" + system.strip() +
        "\n<|user|>\n" + user.strip() +
        "\n<|assistant|>\n"
    )
    if _is_llama_simple(runner):
        args = [
            str(runner),
            "-m", str(model),
            "-n", str(cfg.max_tokens),
            prompt,
        ]
    else:
        args = [
            str(runner),
            "-m", str(model),
            "-p", prompt,
            "-n", str(cfg.max_tokens),
            "--temp", "0",
            "--single-turn",
            "--simple-io",
            "--no-display-prompt",
        ]
    proc = subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=cfg.timeout_s,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"runtime local rc={proc.returncode}")
    return _clean_stdout(proc.stdout)
