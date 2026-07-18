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

The macOS `llama-simple` runtime is ad-hoc signed with Hardened Runtime in the
release. `install_unix.sh` and `run_unix.sh` also remove the macOS quarantine
attribute from the whole extracted folder, and the local LLM provider repeats
that cleanup just before calling the binary. This is not full Apple Developer
notarization, but it avoids the common Gatekeeper block on the downloaded
archive.

> **If macOS blocks `llama-simple` with "Apple could not verify…"**
> (Gatekeeper dialog on first launch): this is expected for a binary downloaded
> without paid Apple notarization. Two ways to allow it:
>
> **Option A – included script (runtime zip only)**
> ```bash
> chmod +x allow-macos.sh && ./allow-macos.sh
> ```
> This script removes the quarantine attribute from the whole directory.
>
> **Option B – via the full app bundle (recommended)**
> Run `./scripts/install_unix.sh`: the script automatically strips quarantine
> from the entire extracted folder.
>
> **Option C – manually**
> ```bash
> xattr -dr com.apple.quarantine /path/to/prioris-macos-arm64
> ```

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

Expected result: `205 passed`.

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

Expected result: `205 passed`.

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
When an LLM is available, free-text answers are accepted for every
choice-based question. PRIORIS interprets the answer, proposes the understood
option, then waits for confirmation. If the LLM is down/offline, the UI falls
back to buttons. After the instinctive P1/P2/P3/P4 answer is confirmed,
PRIORIS prepares 3 challenge questions. It finishes the factual interview,
then asks them one at a time just before scoring. Each answer may propose an
axis correction, and nothing enters the calculation without confirmation.

## 6. Core Workflow

1. Add a task with `/add <title>` or the GUI button.
2. Choose a category.
3. Optionally enter a real deadline.
4. Answer the guided interview.
5. PRIORIS computes P1-P4 deterministically.
6. Use `/why` or the GUI rationale button to inspect the calculation.
7. Use `/today` or the GUI daily-plan button to build a realistic plan.

The interview can switch from express to full mode when the facts justify it:
strong subjective urgency, severe inaction, a nearby deadline or a
contradiction.

### 6.1 How LLM Answers Affect The Quadrant

PRIORIS follows a strict rule: **one displayed question = one expected answer**.
LLM-generated text affects the score only through this confirmed flow:

1. PRIORIS finishes the factual questions, then asks one challenge.
2. You answer.
3. The LLM interprets the answer as a candidate axis/value update:
   `CDR` cost of delay, `INA` consequence of doing nothing, `BLK` blockage,
   `IMP` impact, `HOR` time horizon, `IRR` irreversibility, `ALN` life goal.
4. PRIORIS explains the proposed correction.
5. You accept or reject it.
6. Only accepted corrections update the interview session.

The final calculation is deterministic and does not call the LLM:

- urgency `U = 30×BLK/5 + 40×CDR/4 + 30×HOR/4`
- importance `I = 35×IMP/4 + 25×INA/4 + 20×IRR/3 + 20×ALN/3`
- global score `G = 0.6×I + 0.4×U`
- urgent threshold: `U >= 55`
- important threshold: `I >= 50`
- quadrant: `Q1` if urgent and important, `Q2` if important only, `Q3` if
  urgent only, `Q4` otherwise
- priority: `Q1 -> P1`, `Q2 -> P2`, `Q3 -> P3`, `Q4 -> P4`

### 6.2 Exhaustive Parameter Reference

The seven axes are the **only weighted inputs to the score**. A button answer,
a confirmed free-text interpretation, a clarification, and a mirror question
all produce the same thing: an integer value on one axis scale. A confirmed
deadline can only activate the deterministic floor described below. The LLM
never provides `U`, `I`, `G`, the quadrant, or the priority directly.

| Axis | Feeds | Factual question and complete scale | Worked example |
|---|---|---|---|
| `BLK`, actual blockage, `0..5` | Urgency, weight 30 | “Who is blocked if this is not done this week?” `0` nobody; `1` only me; `2` another person; `3` one team; `4` the client; `5` several teams. | A client genuinely unable to proceed gives `BLK=4`, hence `30×4/5 = 24` urgency points. Someone merely waiting is not necessarily blocked. |
| `CDR`, cost of delay, `0..4` | Urgency, weight 40 | “How does the cost change if you wait?” `0` no change; `1` slow accumulation; `2` clear accumulation; `3` increasing damage; `4` a date cliff. | A submission that becomes impossible after Friday gives `CDR=4`, hence `40×4/4 = 40` urgency points. |
| `HOR`, visibility horizon, `0..4` | Urgency, weight 30 | “When will the problem become visible?” `0` never; `1` in over a month; `2` in 2-4 weeks; `3` this week; `4` already visible. | A consequence visible this week gives `HOR=3`, hence `30×3/4 = 22.5` urgency points. |
| `IMP`, impact, `0..4` | Importance, weight 35 | “What is the real difference between done and not done?” `0` negligible; `1` some comfort; `2` noticeable; `3` major; `4` structural. | A certification that materially changes access to a role may give `IMP=3`, hence `35×3/4 = 26.25` importance points. |
| `INA`, one-month inaction, `0..4` | Importance, weight 25 | “What concretely happens if nobody touches it for a month?” `0` nothing; `1` inconvenience; `2` real problem; `3` crisis; `4` irrecoverable damage. | If one month creates a real problem but not a crisis, `INA=2`, hence `25×2/4 = 12.5` importance points. |
| `IRR`, irreversibility, `0..3` | Importance, weight 20 | “Can it be reversed or recovered later?” `0` reversible; `1` recoverable with effort; `2` recoverable until a date; `3` irreversible. | An option recoverable only before signature gives `IRR=2`, hence `20×2/3 = 13.33` importance points. |
| `ALN`, goal alignment, `0..3` | Importance, weight 20 | “Does this task contribute to one of your life goals?” `0` none; `1` indirect; `2` direct; `3` major. | Preparing the decisive exam for an active goal may give `ALN=3`, hence 20 points and the importance floor below. |

**Express interview and derived values.** Express mode asks for the instinctive
priority, `INA`, `BLK`, `CDR`, `ALN`, and the estimate. If it does not escalate
to full mode, missing axes are filled deterministically: `IMP = min(INA, 3)`,
`IRR = 1`, and `HOR` comes from the deadline: `4` when overdue or due today,
`3` in 1-7 days, `2` in 8-30 days, `1` beyond 30 days, or median `2` without a
deadline. The rationale marks these values as defaults. Full mode asks for
`IMP`, `HOR`, `IRR`, effort, and bias metadata explicitly.

**Uncertainty.** “I don't know” is not zero. The value falls back to the
conservative axis median: `BLK=2`, `CDR=2`, `HOR=2`, `IMP=2`, `INA=2`, `IRR=1`,
`ALN=1`, and the evaluation becomes provisional. Hesitation is recorded but
does not replace a confirmed value.

**Parameters that do not directly enter the score.**

| Parameter | Question or source | Actual use | Example |
|---|---|---|---|
| Instinctive `P1..P4` | “Instinctively, how would you classify it?” | May escalate the interview, selects challenge questions, and measures bias; never forces the quadrant. | Saying P1 and obtaining P4 creates a three-level gap to explain, not an artificial score increase. |
| Deadline | Entered on creation or proposed by `/info` and confirmed | Derives `HOR` in express mode, escalates to full mode when under 7 days, may activate the deadline floor, and gives a planning bonus. | J+3 derives `HOR=3`; with `CDR=4`, `U` is then at least 70. |
| Estimate | `<15`, `15-30`, `30-60`, `1-2 h`, `2-4 h`, `>4 h`, unknown | Converted to `10, 22, 45, 90, 180, 300` minutes; used for gem status, leverage, and plan capacity. Unknown makes the evaluation provisional and excludes the task from the plan. | `30-60 min` becomes 45 planning minutes. |
| Effort | Low, medium, high | Adjusts planning value for daily energy; high effort also makes the task major. | At energy 1, a high-effort P2 is excluded; a true P1 remains with a warning. |
| Requester | Me, colleague, manager, client | Bias detection only, never the score. | A client request with no blockage or delay cost can trigger a client-bias flag. |
| Visibility `0..3` | Task exposure | Visibility/noise bias detection only. | A highly discussed task with `IMP<=1` and `INA<=1` is flagged as noise. |
| Pressure `0..3` | Felt pressure | Guilt-bias detection only. | High pressure with `BLK<=1` and `INA<=1` raises a flag without adding points. |

### 6.3 Exact Score And Complete Example

Each axis is divided by its maximum before its weight is applied, so all three
scores remain between 0 and 100:

```text
U = 30 × BLK/5 + 40 × CDR/4 + 30 × HOR/4
I = 35 × IMP/4 + 25 × INA/4 + 20 × IRR/3 + 20 × ALN/3
G = 0.6 × I + 0.4 × U
```

Before `G` is computed, three deterministic floors are applied in this order:

1. deadline in 7 days or less **and** `CDR=4`: `U = max(U, 70)`;
2. `IRR=3` **and** `INA>=3`: `I = max(I, 70)`;
3. `ALN=3`: `I = max(I, 55)`.

A floor does not add 70 points; it only raises a lower total to that minimum.
The rationale JSON keeps the weighted terms and every before/after adjustment.

The quadrant then uses `U >= 55` and `I >= 50`:

| Urgent | Important | Quadrant | Priority | Meaning |
|---|---|---|---|---|
| yes | yes | Q1 | P1 | do first |
| no | yes | Q2 | P2 | schedule and protect |
| yes | no | Q3 | P3 | delegate or handle quickly |
| no | no | Q4 | P4 | postpone or drop |

**Complete example: 45 minutes of physical activity tied to a goal.** Assume
`BLK=1`, `CDR=3`, `HOR=1`, `IMP=3`, `INA=2`, `IRR=1`, `ALN=3`:

```text
U = 30×1/5 + 40×3/4 + 30×1/4 = 6 + 30 + 7.5 = 43.5
I = 35×3/4 + 25×2/4 + 20×1/3 + 20×3/3
  = 26.25 + 12.5 + 6.67 + 20 = 65.42
G = 0.6×65.42 + 0.4×43.5 = 56.65
```

`U < 55` and `I >= 50` produce Q2/P2. The goal floor changes nothing because
`I` already exceeds 55. With a known 45-minute estimate, this is also a
**gem**: `I >= 45` and duration `<= 60 min`. Displayed leverage is
`I / max(duration_in_hours, 0.25)`, about `87.2` importance points per hour
here. Leverage is informative; only the +10 gem bonus enters daily planning.

### 6.4 Exhaustive Daily-Plan Calculation

1. **Usable capacity:** `integer(declared capacity × 0.8)`. Four controlled
   hours therefore provide 192 schedulable minutes.
2. **Eligibility:** P4 and unknown estimates are excluded before ranking.
3. **Ranking value:**

```text
V = G + gem_bonus + deadline_bonus + energy_adjustment
```

The gem bonus is `+10` when `I >= 45`, the estimate is known, and duration is
`<= 60 min`. Deadline bonuses are bounded:

| Deadline | D<=0 | D<=1 | D<=3 | D<=7 | D<=14 | D<=30 | >30 or none |
|---|---:|---:|---:|---:|---:|---:|---:|
| Bonus | +40 | +35 | +28 | +20 | +12 | +6 | 0 |

Energy adjustment depends on effort:

| Energy | Low effort | Medium effort | High effort |
|---|---:|---:|---:|
| 1, very low | 0 | -25 | excluded, except P1 |
| 2, low | 0 | 0 | -25 |
| 3, medium | 0 | 0 | 0 |
| 4 or 5, high/excellent | -10 | 0 | +10 |

4. **Order:** all eligible P1 tasks are sorted by decreasing `V` and considered
   before any P2/P3. Remaining capacity is filled with P2/P3, also by decreasing
   `V`. Task id breaks ties, making the plan reproducible.
5. **Guardrails:** a major task lasts at least 60 minutes or has high effort;
   at most three are planned. A demanding P1 at very low energy remains
   considered with a warning. An incompatible P2/P3 is excluded.
6. **Insufficient capacity:** a task is selected whole when it fits. Otherwise,
   when `G >= 60` and at least 60 minutes remain, PRIORIS proposes a 60-minute
   “start” slice. Otherwise it is excluded for insufficient remaining capacity.

**Deadline-versus-score example, with no gem bonus.** A P2 with `G=72`, due in
30 days and medium effort has `V=72+6=78`. A P2 with `G=55`, due tomorrow, has
`V=55+35=90` and comes first. A P4 due today remains excluded despite its
theoretical bonus, because eligibility is checked before `V`.

## 7. `/info`

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

## 8. Obsidian

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

## 9. LLM Modes

1. **No LLM**: buttons and deterministic scoring only.
2. **Built-in local rules**: `provider = "prioris"`, no network.
3. **Standalone local GGUF**: `provider = "local_gguf"`, no port, no server.
4. **Ollama / LM Studio**: local OpenAI-compatible services.
5. **External providers**: OpenAI, Anthropic/Claude, custom endpoints, GitHub
   Copilot.

The GUI shows a green/red LLM status indicator. Telegram and GUI diagnostics use
warm-up retries and write details to `logs/llm.log`.

## 10. Current Status

Implemented:

- deterministic scoring and rationale;
- GUI and Telegram;
- optional LLM layer;
- `/info` with impact analysis and confirmed revisions;
- Obsidian scan/import/export/sync;
- short Obsidian links;
- daily plan;
- goals and mirror question;
- 205 passing automated tests.

Still possible future work:

- advanced scenario comparison;
- life-balance alerts;
- monthly bias report;
- richer decision memory;
- controlled creation of Obsidian source lines for local tasks.
