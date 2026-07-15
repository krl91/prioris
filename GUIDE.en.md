# PRIORIS - English Guide

This is the English companion to `GUIDE.md`. The French guide remains the
canonical operational document; this file mirrors the current implementation
state for English readers.

## 1. What PRIORIS Does

PRIORIS is a local-first decision-support assistant. It helps you capture tasks,
evaluate them through a guided interview, calculate deterministic priorities,
build a realistic daily plan, and synchronize selected information with an
Obsidian vault.

The LLM layer is optional. It can interpret free-text answers, suggest goals,
analyze `/info` messages and propose revisions, but it never writes changes
without confirmation and never computes the priority by itself.

## 2. Interfaces

PRIORIS has two interfaces:

- **Local GUI**: enabled when `[telegram] token = ""`; runs with tkinter, no
  local server and no external connection required.
- **Telegram bot**: enabled when a Telegram token is configured.

The GUI exposes the same core workflows: add task, daily plan, goals, list,
scan Obsidian, sync Obsidian, LLM diagnostics, mark done, rationale, and
Info/question.

## 3. Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Expected result: `190 passed`.

For offline installation, provide a `wheelhouse/` directory and run:

```bash
pip install --no-index --find-links wheelhouse -e ".[dev]"
```

PRIORIS downloads no model at startup. A standalone local GGUF setup must ship
the inference binary and the model file with the release.

## 4. Configuration

Minimal GUI configuration:

```toml
[telegram]
token = ""

[database]
path = "prioris.db"

[ui]
language = "fr"  # default; use "en" for English interview questions/options
```

Optional Obsidian configuration:

```toml
[obsidian]
vault_path = "/absolute/path/to/vault"
prioris_dir = "PRIORIS"
```

On Windows, prefer forward slashes:

```toml
[obsidian]
vault_path = "C:/Users/Example/Documents/Vault"
```

Backslashes also work when written with TOML single quotes:

```toml
[obsidian]
vault_path = 'C:\Users\Example\Documents\Vault'
```

Optional LLM configuration examples:

```toml
[llm]
enabled = false
```

```toml
[llm]
enabled = true
provider = "prioris"
model = "rules-v1"
```

```toml
[llm]
enabled = true
provider = "local_gguf"
runner_path = "auto"
model = "models/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf"
timeout_s = 120
```

External providers such as `openai`, `anthropic`, `custom` and `copilot` are
supported. Prefer `api_key_env` for secrets.

When `[ui] language = "en"` is set, the interview questions/options are shown
in English. French remains the default. Scoring and confirmations are unchanged.
When an LLM is available, PRIORIS also asks 3 task-specific helper questions
before the instinctive quadrant question; they help the user reason about
urgent vs important but never affect the score directly.

## 5. Core Workflow

1. Add a task with `/add <title>` or the GUI button.
2. Choose a category.
3. Optionally enter a real deadline.
4. Answer the guided interview.
5. PRIORIS computes P1-P4 deterministically.
6. Use `/why` or the GUI rationale button to inspect the calculation.
7. Use `/today` or the GUI daily-plan button to build a realistic plan.

The interview can switch from express to full mode when the facts justify it:
strong subjective urgency, severe inaction, nearby deadline or contradiction.

## 6. `/info`

`/info` adds new information or asks a question about current work.

Supported flows:

- global analysis: `/info <text>`;
- targeted analysis: `/info <task_id> <text>`;
- impacted-task proposal with per-task explanation;
- direct answer when the input is a question;
- new-task proposal when no existing task matches;
- detected deadline proposal that the user must confirm or edit;
- confirmed axis revision with deterministic recalculation;
- manual fallback without LLM, for example `BLK=4 reason`.

When the task is linked to Obsidian, accepting a revision can trigger an
Obsidian sync proposal with a before/after preview. No vault write happens
without explicit confirmation.

## 7. Obsidian

`/scan` and the GUI **Scan** button read unmarked `- [ ]` tasks from the vault,
ignore `PRIORIS/`, and import new tasks one by one.

After prioritization, the source line is annotated with a short marker:

```md
- [ ] Update CV 🎯P2 [[PRIORIS/12]]
```

The detail note is written as:

```text
PRIORIS/12.md
```

It contains:

- clear heading: `# PRIORIS #12 - Update CV`;
- source backlink;
- priority, quadrant and score;
- axis table;
- deterministic adjustments;
- bias flags;
- information added through `/info`.

Older long links like `[[PRIORIS/details/12 - title|detail]]` remain readable
and are migrated to the short format by **Sync Obsidian**.

## 8. LLM Modes

1. **No LLM**: buttons and deterministic scoring only.
2. **Built-in local rules**: `provider = "prioris"`, no network.
3. **Standalone local GGUF**: `provider = "local_gguf"`, no port, no server.
4. **Ollama / LM Studio**: local OpenAI-compatible services.
5. **External providers**: OpenAI, Anthropic/Claude, custom endpoints, GitHub
   Copilot.

The GUI shows a green/red LLM status indicator. Telegram and GUI diagnostics use
warm-up retries and write details to `logs/llm.log`.

## 9. Current Status

Implemented:

- deterministic scoring and rationale;
- GUI and Telegram;
- optional LLM layer;
- `/info` with impact analysis and confirmed revisions;
- Obsidian scan/import/export/sync;
- short Obsidian links;
- daily plan;
- goals and mirror question;
- 190 passing automated tests.

Still possible future work:

- advanced scenario comparison;
- life-balance alerts;
- monthly bias report;
- richer decision memory;
- controlled creation of Obsidian source lines for local tasks.
