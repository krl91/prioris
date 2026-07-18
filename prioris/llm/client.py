"""OpenAI-compatible chat client: one protocol for all providers.

Ollama, LM Studio and OpenAI-compatible APIs expose `/v1/chat/completions`;
switching provider is a config change. Uses urllib only, short timeouts, and
never lets exceptions cross the facade boundary.
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable

from . import local, local_gguf
from .client_types import LocalGGUFConfig


DEFAULT_GGUF_MODEL = "models/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf"

# Presets: provider -> (base_url, default timeout).
# Local models can take over one minute on the first call. Warm-up and keep-warm
# avoid that delay in normal usage; the long timeout is a worst-case guardrail.
PRESETS: dict[str, tuple[str, float]] = {
    "ollama": ("http://localhost:11434/v1", 120.0),
    "lmstudio": ("http://localhost:1234/v1", 120.0),
    "openai": ("https://api.openai.com/v1", 15.0),
    "anthropic": ("https://api.anthropic.com/v1", 30.0),
    "copilot": ("https://api.githubcopilot.com", 30.0),
}


@dataclass
class LLMConfig:
    enabled: bool = False
    provider: str = "prioris"          # prioris | ollama | lmstudio | openai | custom
    model: str = "rules-v1"
    runner_path: str = ""              # local_gguf provider: bundled binary
    api_key: str = ""
    api_key_env: str = ""              # avoids storing secrets in config.toml
    base_url: str = ""                 # required for custom provider, otherwise optional
    timeout_s: float | None = None     # provider-specific default
    max_tokens: int = 512              # provider local_gguf

    @classmethod
    def from_dict(cls, d: dict) -> "LLMConfig":
        return cls(enabled=bool(d.get("enabled", False)),
                   provider=str(d.get("provider", "prioris")).lower(),
                   model=str(d.get("model", "rules-v1")),
                   runner_path=str(d.get("runner_path", "")),
                   api_key=str(d.get("api_key", "")),
                   api_key_env=str(d.get("api_key_env", "")),
                   base_url=str(d.get("base_url", "")),
                   timeout_s=float(d["timeout_s"]) if d.get("timeout_s") else None,
                   max_tokens=int(d.get("max_tokens", 512)))


def resolve(cfg: LLMConfig) -> tuple[str, float]:
    """Return effective base_url and timeout. Raise ValueError if invalid."""
    if cfg.base_url:
        return cfg.base_url.rstrip("/"), cfg.timeout_s or 8.0
    if cfg.provider == "prioris":
        return "builtin://prioris", 0.0
    if cfg.provider == "local_gguf":
        runner, model = _local_gguf_paths(cfg)
        if not runner:
            raise ValueError("provider local_gguf : runner_path requis")
        if not model:
            raise ValueError("provider local_gguf : model doit pointer vers le GGUF")
        return "local://gguf", cfg.timeout_s or 120.0
    if cfg.provider in PRESETS:
        url, t = PRESETS[cfg.provider]
        return url, cfg.timeout_s or t
    known = ["prioris", "local_gguf", *sorted(PRESETS)]
    raise ValueError(f"provider inconnu « {cfg.provider} » : "
                     f"choisir {known} ou renseigner base_url")


def _default_gguf_runner() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "darwin" and machine in ("arm64", "aarch64"):
        return "runtime/macos-arm64/llama-simple"
    if system == "darwin" and machine in ("x86_64", "amd64"):
        return "runtime/macos-x64/llama-simple"
    if system == "windows" and machine in ("amd64", "x86_64"):
        return "runtime/windows-x64/llama-simple.exe"
    if system == "windows" and machine in ("arm64", "aarch64"):
        return "runtime/windows-arm64/llama-simple.exe"
    if system == "linux" and machine in ("x86_64", "amd64"):
        return "runtime/linux-x64/llama-simple"
    if system == "linux" and machine in ("arm64", "aarch64"):
        return "runtime/linux-arm64/llama-simple"
    return ""


def _local_gguf_paths(cfg: LLMConfig) -> tuple[str, str]:
    runner = cfg.runner_path
    if not runner or runner == "auto":
        runner = _default_gguf_runner()
    model = cfg.model
    if not model or model == "rules-v1":
        model = DEFAULT_GGUF_MODEL
    return runner, model


class LLMError(Exception):
    pass


def _http_transport(url: str, payload: dict, headers: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


@dataclass
class ChatClient:
    """`transport` can be injected for tests, so tests use no network."""
    cfg: LLMConfig
    transport: Callable | None = field(default=None, repr=False)

    def chat(self, system: str, user: str, json_mode: bool = True,
             max_tokens: int | None = None) -> str:
        token_limit = min(self.cfg.max_tokens, max_tokens or self.cfg.max_tokens)
        if self.cfg.provider == "prioris":
            return local.chat(system, user)
        if self.cfg.provider == "local_gguf":
            timeout = resolve(self.cfg)[1]
            runner, model = _local_gguf_paths(self.cfg)
            gguf_cfg = LocalGGUFConfig(
                runner_path=runner,
                model_path=model,
                timeout_s=timeout,
                max_tokens=token_limit,
            )
            try:
                if self.transport:
                    return self.transport(gguf_cfg, system, user)
                return local_gguf.chat(gguf_cfg, system, user)
            except (OSError, subprocess.SubprocessError, RuntimeError) as e:
                raise LLMError(str(e)) from e
        base, timeout = resolve(self.cfg)
        if self.cfg.provider == "anthropic":
            return self._chat_anthropic(base, timeout, system, user, token_limit)
        url = f"{base}/chat/completions"
        headers = {"Content-Type": "application/json"}
        api_key = self.cfg.api_key
        if self.cfg.api_key_env:
            api_key = os.environ.get(self.cfg.api_key_env, api_key)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if self.cfg.provider == "copilot":
            headers["Copilot-Integration-Id"] = "prioris-local-gui"
        payload: dict = {
            "model": self.cfg.model,
            "temperature": 0,
            "max_tokens": token_limit,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        transport = self.transport or _http_transport
        try:
            data = transport(url, payload, headers, timeout)
        except urllib.error.HTTPError as e:
            if json_mode and e.code in (400, 404, 422):
                # provider sans response_format : on retente sans
                payload.pop("response_format", None)
                try:
                    data = transport(url, payload, headers, timeout)
                except Exception as e2:
                    raise LLMError(str(e2)) from e2
            else:
                raise LLMError(f"HTTP {e.code}") from e
        except Exception as e:
            raise LLMError(str(e)) from e
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise LLMError(f"réponse inattendue du provider : {data!r:.200}") from e

    def _chat_anthropic(self, base: str, timeout: float,
                        system: str, user: str, max_tokens: int) -> str:
        api_key = self.cfg.api_key
        if self.cfg.api_key_env:
            api_key = os.environ.get(self.cfg.api_key_env, api_key)
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
        payload = {
            "model": self.cfg.model,
            "max_tokens": max_tokens,
            "temperature": 0,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        transport = self.transport or _http_transport
        try:
            data = transport(f"{base}/messages", payload, headers, timeout)
        except Exception as e:
            raise LLMError(str(e)) from e
        try:
            chunks = data["content"]
            return "".join(c.get("text", "") for c in chunks if c.get("type") == "text")
        except (KeyError, TypeError) as e:
            raise LLMError(f"réponse inattendue du provider : {data!r:.200}") from e
