# PRIORIS

Personal decision-support assistant for tasks, priorities, daily planning and
Obsidian synchronization. The core engine is deterministic: the LLM is optional
and never decides on its own.

## Features

- Express/full guided interview with contradiction checks C1-C6.
- Deterministic P1-P4 scoring, `/why`, bias flags 1-4/7/9 and full rationale.
- Daily plan based on energy, capacity, estimates and due dates.
- Telegram mode or local tkinter GUI without a server.
- `/info`: add information, ask questions, detect impacted tasks, create a new
  task, confirm/adjust detected deadlines, confirm axis revisions, and fall back
  to manual mode without an LLM.
- Life goals, mirror question and optional LLM consistency checks.
- Obsidian: vault scan, task import, checked-box sync, `PRIORIS/<id>.md` notes,
  short links `[[PRIORIS/<id>]]`, full sync with before/after preview.
- Optional LLM: no LLM, built-in local `prioris/rules-v1`, standalone local GGUF
  without a port, Ollama/LM Studio, OpenAI, Anthropic/Claude, custom endpoints
  and GitHub Copilot.

## Architecture

```text
prioris/
├── core/          Pure functions, no I/O
├── store/         Append-only SQLite
├── vault/         Obsidian scan/sync/export
├── gui/           Local tkinter GUI
├── bot/           Telegram adapter
└── llm/           Optional LLM facade, providers and diagnostics
tests/             190 automated tests
```

`tests/test_architecture.py` enforces that `core/` imports neither store, bot,
vault, SQLite, Telegram nor any network client.

## Installation

## Ready-to-install Release

Download the archive matching your system from the latest release:

- `prioris-macos-arm64.zip`
- `prioris-windows-x64.zip`
- `prioris-linux-x64.tar.gz`

Each archive contains the application, documentation, `config.example.toml`, an
example Obsidian vault, a `wheelhouse/` for offline Python dependency
installation, and the platform-specific `llama-simple` local runtime without a
server.

Install:

```bash
./scripts/install_unix.sh
./scripts/run_unix.sh
```

Windows PowerShell:

```powershell
.\scripts\install_windows.ps1
.\scripts\run_windows.ps1
```

For `local_gguf`, put the GGUF model in `models/`, for example
`models/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf`, then check `config.toml`.
Models are published separately when their size is compatible with GitHub
Releases.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Expected result: `190 passed`.

Offline installation: provide Python wheels in `wheelhouse/`, then run:

```bash
pip install --no-index --find-links wheelhouse -e ".[dev]"
```

PRIORIS downloads no model at startup. For `local_gguf`, the release must already
include the CLI/stdout inference binary and the `.gguf` model file. The
standalone runtime is intentionally limited to `llama-simple` and its
dependencies: no `llama-server`, no `ggml-rpc-server`, no `llama-cli`, and no
local port opened.

Manual downloads for the recommended GGUF models:

- 3B Q4_K_M, recommended default:
  https://huggingface.co/unsloth/Ministral-3-3B-Instruct-2512-GGUF/resolve/main/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf
- 8B Q4_K_M, heavier:
  https://huggingface.co/unsloth/Ministral-3-8B-Instruct-2512-GGUF/resolve/main/Ministral-3-8B-Instruct-2512-Q4_K_M.gguf

Put the chosen file in `models/`, then set `model` in `config.toml`.

Windows paths in `config.toml`: prefer `/`, for example
`vault_path = "C:/Users/Example/Documents/Vault"`. Windows paths with `\` are also
accepted when written with TOML single quotes:
`vault_path = 'C:\Users\Example\Documents\Vault'`.

## Running

### Local GUI

Leave the Telegram token empty:

```toml
[telegram]
token = ""
```

Then run:

```bash
python -m prioris.bot.main
```

The GUI exposes task creation, daily plan, goals, task list, Obsidian scan,
Obsidian sync, LLM diagnostics, mark-done, rationale and Info/question.

### Language

French remains the default. To use English interview questions/options:

```toml
[ui]
language = "en"
```

Scoring, priorities and confirmations stay identical. When an LLM is active,
PRIORIS also displays 3 task-specific questions before the instinctive
quadrant question to help separate urgent/important from the other quadrants.

### Telegram

1. Create a bot with **@BotFather**.
2. Copy `config.example.toml` to `config.toml`.
3. Fill `[telegram] token`.
4. Run:

```bash
python -m prioris.bot.main
```

## Commands

| Command | Effect |
|---|---|
| `/add <title>` | new task, category, optional deadline, interview |
| `/today` | energy, capacity, daily plan, Obsidian export |
| `/list` | evaluated tasks sorted by priority and score |
| `/why <id>` | full deterministic scoring rationale |
| `/done <id>` | mark done, log time, check Obsidian box if linked |
| `/scan` | import/synchronize Obsidian tasks |
| `/goals` | manage goals |
| `/llm` | LLM diagnostics, warm-up, last failures |
| `/info ...` | information/question, impact, revision or new task |

## Obsidian

`/scan` and the **Scan** button read unmarked `- [ ]` tasks from the vault.
After prioritization, PRIORIS adds a short marker:

```md
- [ ] Update CV 🎯P2 [[PRIORIS/12]]
```

`PRIORIS/12.md` contains a clear title, the result, axes, information added via
`/info`, and a backlink to the source note. Older long links such as
`[[PRIORIS/details/12 - title|detail]]` are still read and are migrated during
the next **Sync Obsidian**.

## Status

190 tests pass locally. Remaining possible improvements: advanced scenario
comparison, life-balance alerts, monthly bias reports, richer decision memory,
and controlled creation of Obsidian lines for local tasks without
`obsidian_path`.
