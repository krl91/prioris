# PRIORIS - English Guide

This is the English companion to `GUIDE.md`. The French guide remains the
canonical operational document; this file mirrors the current implementation
state for English readers.

## 1. Quick Install from a Release

The recommended way to use PRIORIS is the simplest one:

1. Open the latest GitHub release:
   <https://github.com/krl91/prioris/releases/latest>
2. Download **one file**, matching your system. Do not download the `runtime-*`
   archives alone: they do not contain the full application.

| System | Compressed file to download | Commands after extraction |
|---|---|---|
| macOS Apple Silicon | `prioris-macos-arm64.zip` | `cd prioris-macos-arm64`, then `./scripts/install_unix.sh`, then `./scripts/run_unix.sh` |
| Windows x64 | `prioris-windows-x64.zip` | `cd prioris-windows-x64`, then `.\scripts\install_windows.ps1`, then `.\scripts\run_windows.ps1` |
| Linux x64 | `prioris-linux-x64.tar.gz` | `cd prioris-linux-x64`, then `./scripts/install_unix.sh`, then `./scripts/run_unix.sh` |

3. Extract the archive wherever you want.
4. Open a terminal in the extracted folder.
5. Check that `config.toml` already exists at the folder root. In a normal
   release, it is provided and ready to use.
6. Run the bundled script.

macOS Apple Silicon:

```bash
cd prioris-macos-arm64
./scripts/install_unix.sh
./scripts/run_unix.sh
```

The macOS `llama-simple` runtime is ad-hoc signed in the release.
`install_unix.sh` and `run_unix.sh` also remove the macOS quarantine attribute
from the whole extracted folder, and the local LLM provider repeats that cleanup
just before calling the binary. This is not full Apple Developer notarization,
but it avoids the common Gatekeeper block on the downloaded archive.

Linux x64:

```bash
cd prioris-linux-x64
./scripts/install_unix.sh
./scripts/run_unix.sh
```

Windows PowerShell:

```powershell
cd prioris-windows-x64
.\scripts\install_windows.ps1
.\scripts\run_windows.ps1
```

Each archive already contains everything needed to start:

- the PRIORIS application;
- documentation;
- a ready-to-run `config.toml`;
- the `ObsidianVault` folder;
- Python dependencies in `wheelhouse/` for offline installation;
- the local `llama-simple` runtime, with no server and no local port;
- the `Ministral-3-3B-Instruct-2512-Q4_K_M.gguf` model.

The default configuration starts the **local GUI**, without Telegram, using the
bundled local GGUF 3B model. No model is downloaded at startup.

If `config.toml` is missing after extraction, recreate it from the example:

macOS / Linux:

```bash
cp config.example.toml config.toml
```

Windows PowerShell:

```powershell
Copy-Item config.example.toml config.toml
```

Then open `config.toml` and check at least:

```toml
[telegram]
token = ""                  # empty = local GUI, no Telegram

[obsidian]
vault_path = "ObsidianVault"
prioris_dir = "PRIORIS"

[llm]
enabled = true
provider = "local_gguf"
runner_path = "auto"
model = "models/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf"
```

To start without an LLM, replace only:

```toml
[llm]
enabled = false
```

## 2. What PRIORIS Does

PRIORIS is a local-first decision-support assistant. It helps you capture tasks,
evaluate them through a guided interview, calculate deterministic priorities,
build a realistic daily plan, and synchronize selected information with an
Obsidian vault.

The LLM layer is optional. It can interpret free-text answers, suggest goals,
analyze `/info` messages and propose revisions, but it never writes changes
without confirmation and never computes the priority by itself.

## 3. Interfaces

PRIORIS has two interfaces:

- **Local GUI**: enabled when `[telegram] token = ""`; runs with tkinter, no
  local server and no external connection required.
- **Telegram bot**: enabled when a Telegram token is configured.

The GUI exposes the same core workflows: add task, daily plan, goals, list,
scan Obsidian, sync Obsidian, LLM diagnostics, mark done, rationale, and
Info/question.

## 4. Developer or Manual Installation

1. Open the project folder:

```bash
cd prioris
```

2. Create the virtual environment:

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Install PRIORIS:

```bash
pip install -e ".[dev]"
```

If the archive contains `wheelhouse/`, install offline instead:

```bash
pip install --no-index --find-links wheelhouse -e ".[dev]"
```

4. Create `config.toml` from the example:

macOS / Linux:

```bash
cp config.example.toml config.toml
```

Windows PowerShell:

```powershell
Copy-Item config.example.toml config.toml
```

5. Open `config.toml` and choose the interface:

Local GUI without Telegram:

```toml
[telegram]
token = ""
```

Telegram:

```toml
[telegram]
token = "1234567890:AAExample..."
```

6. Choose the LLM mode:

No LLM:

```toml
[llm]
enabled = false
```

Standalone local GGUF:

```toml
[llm]
enabled = true
provider = "local_gguf"
runner_path = "auto"
model = "models/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf"
```

7. Verify the installation.

Recent releases include the `tests/` folder. The full verification is:

```bash
python -m pytest
```

Expected result: `191 passed`.

Minimal verification if you only want to confirm that the application starts:

```bash
python -c "import prioris; print('PRIORIS import ok')"
python -m prioris.bot.main
```

If you use an older archive that does not include `tests/`, `pytest` may print
`collected 0 items`. In that case, it is not an application failure; use the
minimal verification above.

In a full source repository clone, also run:

```bash
pytest
```

Expected result: `191 passed`.

PRIORIS downloads no model at startup. A standalone local GGUF setup must ship
the inference binary and the model file with the release.

## 5. Configuration

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

`local_gguf` is inference-only. `runner_path = "auto"` selects
`llama-simple` only:

| System | Standalone runtime |
|---|---|
| macOS Apple Silicon | `runtime/macos-arm64/llama-simple` |
| macOS Intel | `runtime/macos-x64/llama-simple` |
| Windows x64 | `runtime/windows-x64/llama-simple.exe` |
| Windows arm64 | `runtime/windows-arm64/llama-simple.exe` |
| Linux x64 | `runtime/linux-x64/llama-simple` |
| Linux arm64 | `runtime/linux-arm64/llama-simple` |

Release runtime archives must contain `llama-simple` and its dependencies only.
They must not contain `llama-server`, `ggml-rpc-server`, `llama-cli`, or
server/RPC libraries. PRIORIS also refuses binaries whose help text exposes an
embedded localhost server mode.

External providers such as `openai`, `anthropic`, `custom` and `copilot` are
supported. Prefer `api_key_env` for secrets.

When `[ui] language = "en"` is set, the interview questions/options are shown
in English. French remains the default. Scoring and confirmations are unchanged.
When an LLM is available, PRIORIS also asks 3 task-specific helper questions
before the instinctive quadrant question; they help the user reason about
urgent vs important but never affect the score directly.

## 6. Core Workflow

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
