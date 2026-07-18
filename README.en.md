# PRIORIS

PRIORIS helps you focus on what truly matters.

When everything feels urgent, PRIORIS guides you through a structured decision process to determine what to do now, what to schedule, what to delegate, and what to ignore.

Inspired by the Eisenhower Matrix and enhanced by intelligent questioning, every recommendation is transparent, justified, and easy to understand.

✔ Clear and explainable priorities
✔ Realistic daily action plans
✔ Reduced cognitive load
✔ Seamless Obsidian integration
✔ Human-controlled decision making

AI supports your thinking. You remain in control.

## What It Is For

PRIORIS helps when a basic todo-list is no longer enough:

- choose genuinely important tasks instead of following urgency alone;
- compare personal, professional, health, finance or family tasks;
- avoid impulsive decisions with a guided interview;
- build a daily plan that respects energy, capacity and deadlines;
- keep a clear rationale for each priority;
- synchronize tasks and decisions with an Obsidian vault.

## What You Can Do

- Add a task, choose a category, optionally set a deadline and answer an express
  or full interview.
- Get a P1-P4 score with detailed rationale, contradiction checks and bias
  signals.
- Generate a daily plan that balances score, real urgency, due dates, available
  energy and estimated duration.
- Add information or ask a question with `/info`: PRIORIS proposes impacted
  tasks, explains the impact, suggests a revision or a new task, then asks for
  confirmation.
- Manage life goals and connect tasks to those goals.
- Scan an Obsidian vault, import `- [ ]` tasks, write `PRIORIS/<id>.md` notes,
  check completed tasks and synchronize with a before/after preview.

## Interfaces

| Interface | Use | Strengths |
|---|---|---|
| Local GUI | Simple desktop window | No account, no server, no local port |
| Telegram | Mobile use and notifications | Convenient capture and triage anywhere |
| Obsidian | Personal Markdown vault | Readable notes, short links, durable history |
| Optional LLM | Interpretation and decision support | Better questions, `/info` analysis, rewrites |

The local GUI is the default release mode. Telegram remains optional: leave the
token empty to avoid using it.

## LLM Modes

PRIORIS works with or without an LLM:

- **No LLM**: button-based interview, local scoring and deterministic daily plan.
- **Standalone local LLM**: bundled GGUF model, `llama-simple` runtime, no
  Ollama, no LM Studio, no server and no local port.
- **Ollama / LM Studio**: supported if you prefer managing models with those
  tools.
- **External LLM**: OpenAI, Anthropic/Claude, compatible endpoint, GitHub
  Copilot or another configured provider.

The standard release already includes and configures the local 3B model.

## Potential

PRIORIS can become a personal decision cockpit: daily priorities, goal tracking,
decision memory, recurring-bias audits, periodic reports, Markdown
synchronization and controlled LLM assistance. The current base favors
reliability: local data, confirmation before changes, logs, tests and a clear
separation between deterministic scoring and LLM assistance.

## Architecture

```text
prioris/
├── core/          Pure functions, no I/O
├── store/         Append-only SQLite
├── vault/         Obsidian scan/sync/export
├── gui/           Local tkinter GUI
├── bot/           Telegram adapter
└── llm/           Optional LLM facade, providers and diagnostics
tests/             229 automated tests
```

`tests/test_architecture.py` enforces that `core/` imports neither store, bot,
vault, SQLite, Telegram nor any network client.

The experimental native port lives in [`rust/`](rust/README.md). Its releases
use `rust-v*` tags and remain separate from the Python `v0.x` releases. Starting
with Rust 0.2.5, the macOS archive contains `PRIORIS.app`. Without a paid Apple
account it is signed ad hoc, so the user approves the first launch in **System
Settings > Privacy & Security > Open Anyway**. Writable data lives in
`~/Library/Application Support/PRIORIS`, and the bundle remains compatible with
App Translocation. When all six Apple secrets are configured, the same workflow
uses Developer ID signing and notarization.

## Install from the Release

The standard path is to download the latest ready-to-run archive:
<https://github.com/krl91/prioris/releases/latest>

Download **one compressed file**, matching your system. Do not download the
`runtime-*` assets alone: they do not contain the full application.

| System | File to download | Commands after extraction |
|---|---|---|
| macOS Apple Silicon | `prioris-macos-arm64.zip` | `cd prioris-macos-arm64`, then `./scripts/install_unix.sh`, then `./scripts/run_unix.sh` |
| Windows x64 | `prioris-windows-x64.zip` | `cd prioris-windows-x64`, then `.\scripts\install_windows.ps1`, then `.\scripts\run_windows.ps1` |
| Linux x64 | `prioris-linux-x64.tar.gz` | `cd prioris-linux-x64`, then `./scripts/install_unix.sh`, then `./scripts/run_unix.sh` |

Each archive contains the application, documentation, `config.example.toml`, an
example Obsidian vault, a `wheelhouse/` for offline Python dependency
installation, the platform-specific `llama-simple` local runtime without a
server, the `Ministral-3-3B-Instruct-2512-Q4_K_M.gguf` model, and a ready-to-run
`config.toml` configured for the local GUI with that model. New archives also
include `tests/` so the installation can be verified after extraction.

macOS Apple Silicon:

```bash
cd prioris-macos-arm64
./scripts/install_unix.sh
./scripts/run_unix.sh
```

On macOS, run `install_unix.sh` before the first launch. `llama-simple` is
ad-hoc signed, and the scripts remove the macOS quarantine attribute from the
whole extracted folder. The local LLM provider also repeats that cleanup just
before calling the binary. This is not full Apple Developer notarization, but it
avoids the common Gatekeeper block on the downloaded archive.

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

For `local_gguf`, put the GGUF model in `models/`, for example
`models/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf`, then check `config.toml`.
Recent releases already include the 3B model in each OS bundle. The 8B model
remains optional and is downloaded separately.

## Developer Installation from the Source Repository

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Expected result in a full source repository clone: `229 passed`.

New ready-to-run release archives include `tests/`. To verify a release after
extraction:

```bash
python -m pytest
```

If you use an older archive and get `collected 0 items`, it did not include the
tests yet. In that case, verify at least:

```bash
python -c "import prioris; print('PRIORIS import ok')"
python -m prioris.bot.main
```

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
  https://huggingface.co/unsloth/Ministral-3-3B-Instruct-2512-GGUF/resolve/7564922f37fa5bbb62b87f09a55c12f1f91d7a6a/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf
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
you can answer every choice-based question in free text: PRIORIS interprets the
answer, proposes the understood option, then waits for your confirmation. If the
LLM is down/offline, the UI falls back to buttons. The answer to “Instinctively,
how would you classify it?” does not force the score: it prepares anti-bias
challenge questions. They are asked one at a time after the factual questions,
just before scoring. Each answer may propose an axis correction, which is
explained and confirmed before it can affect the calculation. An LLM-generated
question may have a false premise: state that freely. PRIORIS records the
objection and continues without changing the score; if the answer also gives a
scorable fact, it proposes the corresponding correction. LLM abstention never
blocks an anti-bias question. Short `yes` and `no` answers are recognized
directly as complete, certain answers. An explicit premise rejection with no
other fact is also recognized before the LLM call. The mirror check recognizes
explicitly severe or vital consequences without forcing ambiguous answers into
an arbitrary option.

### Calculation And Planning

- One displayed question always expects one answer. An unconfirmed LLM
  interpretation is never used.
- The seven axes come from factual questions: `BLK` actual blockage (for
  example, a blocked critical stakeholder), `CDR` cost of delay (a cost cliff at a date),
  `HOR` visibility horizon (visible this week), `IMP` difference between done
  and not done (a structural gain), `INA` consequence of one month of inaction
  (a crisis), `IRR` irreversibility (cannot be recovered), and `ALN` alignment
  with a goal (direct contribution).
- Every value is normalized by the maximum of its scale. Exact calculation:
  `U = 30×BLK/5 + 40×CDR/4 + 30×HOR/4`;
  `I = 35×IMP/4 + 25×INA/4 + 20×IRR/3 + 20×ALN/3`;
  `G = 0.6×I + 0.4×U`.
- Thresholds: urgent if `U >= 55`, important if `I >= 50`. `Q1 -> P1`, `Q2 ->
  P2`, `Q3 -> P3`, `Q4 -> P4`.
- Express mode now asks `IMP` independently from `INA`: strategic impact is no
  longer inferred from, or suppressed by, one-month inaction cost. Hesitant or
  unknown answers also produce a `U/I` interval; the rationale reports whether
  the quadrant is robust, all possible quadrants, and the pivot axis.
- `G` ranks and schedules tasks; it does not select the quadrant, which depends
  only on the `U` and `I` thresholds.
- Planning value: `V = G + deadline bonus (0 to 40) + gem bonus (0 or 10) +
  energy adjustment (-25 to +10, or exclusion)`. P1 tasks are considered before
  P2/P3; P4 tasks and unknown estimates are excluded.

The complete scales, one worked example per axis, express-mode defaults,
robustness intervals, score floors, known limitations, and every planning rule
are documented in [GUIDE.en.md](GUIDE.en.md),
sections 6.2 to 6.4.

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

229 tests pass locally. Remaining possible improvements: advanced scenario
comparison, life-balance alerts, monthly bias reports, richer decision memory,
and controlled creation of Obsidian lines for local tasks without
`obsidian_path`.
