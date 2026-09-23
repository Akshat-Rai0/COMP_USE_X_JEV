# Reflex Arc

> A macOS desktop agent that splits its thinking in two: a fast decision model handles each small step, and a slower language model steps in only when the fast one is unsure.

**Status:** Week 0 — setting up tools and requesting access.
**Platform:** macOS on Apple Silicon only.
**Timeline:** 12 weeks, Sep 28 – Dec 20.

---

## Table of Contents

- [What This Project Does](#what-this-project-does)
- [The Four Layers](#the-four-layers)
- [How One Step Works](#how-one-step-works)
- [Architecture Overview](#architecture-overview)
- [Quick Start (Experienced Devs)](#quick-start-experienced-devs)
- [Detailed Setup Walkthrough](#detailed-setup-walkthrough)
  - [Step 0 — Prerequisites](#step-0--prerequisites)
  - [Step 1 — Clone the Repo](#step-1--clone-the-repo)
  - [Step 2 — Install Cua Driver](#step-2--install-cua-driver)
  - [Step 3 — Grant macOS Permissions](#step-3--grant-macos-permissions)
  - [Step 4 — Verify the Driver](#step-4--verify-the-driver)
  - [Step 5 — Request Jev Early Access](#step-5--request-jev-early-access)
  - [Step 6 — Set Up kev (Local Stand-In)](#step-6--set-up-kev-local-stand-in)
  - [Step 7 — Get an OpenRouter API Key](#step-7--get-an-openrouter-api-key)
  - [Step 8 — Configure Environment Variables](#step-8--configure-environment-variables)
  - [Step 9 — Install Python Dependencies](#step-9--install-python-dependencies)
  - [Step 10 — Create a Sandbox User (Recommended)](#step-10--create-a-sandbox-user-recommended)
  - [Step 11 — Pin All Versions](#step-11--pin-all-versions)
  - [Step 12 — Run the Calculator Tutorial](#step-12--run-the-calculator-tutorial)
  - [Step 13 — Read the Jev Docs](#step-13--read-the-jev-docs)
  - [Step 14 — Read Licence Terms](#step-14--read-licence-terms)
- [Running a Task](#running-a-task)
- [The Hero Task](#the-hero-task)
- [Voice Input](#voice-input)
- [Decision Backend: Jev → kev → LLM](#decision-backend-jev--kev--llm)
- [Safety Rules](#safety-rules)
- [Success Metrics](#success-metrics)
- [Run Console (Web UI)](#run-console-web-ui)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Roadmap](#roadmap)
- [Open Decisions](#open-decisions)
- [Known Caveats](#known-caveats)
- [Deliverables](#deliverables)
- [Docs](#docs)
- [License](#license)

---

## What This Project Does

Reflex Arc is a research project that answers one question:

> **How much of a desktop agent's inner loop can a fast "System One" model (Jev) handle alone, how cheap and fast is that in practice, and how often is it confidently wrong?**

The agent operates real macOS apps by reading the UI element tree, asking Jev which control to act on next, and clicking/typing through Cua Driver. A slower planner LLM steps in only when Jev is unsure. Every run produces a full trace with measured numbers — latency, cost, accuracy, and a calibration table showing how well Jev's confidence matches reality.

**The analogy:** Touch a hot pan and your hand pulls back before you've consciously decided anything. That's a spinal reflex — fast, narrow, good at one job. Deliberate thinking only kicks in when the reflex has no good answer. Here, **Jev is the spine**, the **planner LLM is the cortex**, and **Cua Driver is the eyes and hands**.

---

## The Four Layers

| Layer | Component | Role |
|-------|-----------|------|
| 🔘 **Body** | Cua Driver | Reads the screen (UI tree + screenshot) and acts (click, type, press) |
| 🔵 **Reflex** | Jev (or kev) | Picks which control to act on next — fast, stateless, returns probabilities |
| 🟠 **Planner** | LLM via OpenRouter | Plans the task, writes text, rescues when the reflex is unsure |
| 🟢 **Verify** | Noul questions (via Jev) | Yes/no checks: "did it work?", "is the goal reached?", "is an error visible?" |

---

## How One Step Works

Every step in a task follows the same five moves:

1. **Look** (Body) — Cua Driver reads the UI element tree of the front window and saves a screenshot.
2. **Describe** (Body) — A serializer turns the tree into short numbered lines like `e17 button "Add reminder"`, pruned to at most 255 elements.
3. **Decide** (Reflex) — One Jev request carries the state plus several small questions: a **Choice** (which element to act on) and **Noul** questions (yes/no checks). Jev answers with probabilities and a confidence value.
4. **Act** (Body) — If confidence clears the gates, the Driver clicks or types. If not, the step **escalates to the planner LLM**.
5. **Check** (Verify) — On the next pass, a Noul question checks: did the intended change happen? Two failures in a row trigger a replan.

### Escalation triggers

| Trigger | What happens |
|---------|-------------|
| Confidence below 0.70 | Planner LLM sees candidates + screenshot, picks one |
| Top two choices gap < 0.15 | Same as above |
| Intended effect not seen 2× in a row | Planner replans from current screen |
| Same screen appears 3× | Loop breaker: replan once, then stop |
| Risky action (delete, send, buy) | **Always** ask a human, regardless of confidence |
| Planner also unsure / budget exceeded | Pause and ask human, or stop |

---

## Architecture Overview

```
┌─────────────────────────────────┐
│  Sandbox: dedicated macOS user  │
│  ┌───────────────────────────┐  │
│  │     Target Apps           │  │
│  │  (Reminders, Finder, ...) │  │
│  └─────────┬─────────────────┘  │
│            ↕ reads & controls   │
│  ┌───────────────────────────┐  │
│  │     Cua Driver            │  │
│  │  (CuaDriver.app daemon)   │  │
│  └─────────┬─────────────────┘  │
└────────────┼────────────────────┘
             │ UI tree + screenshot
             ↓
┌────────────────────────────────────────┐
│  Orchestrator: one Python process      │
│  (holds every API key)                 │
│                                        │
│  ┌──────────────┐  ┌───────────────┐   │   ┌──────────────────────┐
│  │ State        │→ │ Loop          │ ←→│→  │ Decision Backend     │
│  │ Serializer   │  │ Controller    │   │   │  • Jev (remote API)  │
│  └──────────────┘  │ (LangGraph)   │   │   │  • kev (local)       │
│                    └──────┬────────┘   │   │  • LLM adapter       │
│                           ↓            │   └──────────────────────┘
│                    ┌──────────────┐    │   ┌──────────────────────┐
│                    │ Gates        │ ←→ │→  │ Planner & Text LLM   │
│                    │ (confidence, │    │   │ (via OpenRouter)      │
│                    │  risk rules) │    │   └──────────────────────┘
│                    └──────┬────────┘   │
│                           ↓            │
│                    ┌──────────────┐    │   ┌──────────────────────┐
│                    │ Trace Writer │ ←→ │→  │ Trace Store          │
│                    └──────────────┘    │   │ (SQLite + screenshots)│
└────────────────────────────────────────┘   └──────────────────────┘
                           ↓
                    ┌──────────────┐
                    │ Run Console  │
                    │ (FastAPI +   │
                    │  WebSocket)  │
                    └──────────────┘
```

**Voice input** runs locally (push-to-talk + `mlx-whisper`), writes transcripts into a small queue that the loop controller drains once per step — never mid-step. It can start a task or redirect a running one, but it can **never approve a risky action**.

---

## Quick Start (Experienced Devs)

> For the full walkthrough with every small step, see [Detailed Setup Walkthrough](#detailed-setup-walkthrough) below.

```bash
# 1. Clone and enter
git clone <your-repo-url>
cd reflex-arc

# 2. Install Cua Driver (macOS only, Apple Silicon)
#    Download CuaDriver.app from https://github.com/trycua/cua
#    Grant Accessibility + Screen Recording in System Settings > Privacy & Security

# 3. Verify Driver
cua-driver doctor

# 4. Set up kev (local Jev stand-in while waiting for access)
git clone https://github.com/jaredpalmer/kev.git
cd kev
# Download the kev-0.5b release weights
# Start the local server:
# kev serve --model kev-0.5b --port 8009

# 5. Get an OpenRouter key
#    https://openrouter.ai → create account → generate API key

# 6. Configure environment
cp .env.example .env
# Fill in:
#   OPENROUTER_API_KEY=or-...
#   KEV_BASE_URL=http://localhost:8009
#   JEV_API_KEY=           # leave empty until access arrives
#   DECISION_BACKEND=kev   # "kev", "jev", or "llm"

# 7. Install Python deps
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 8. Run the Calculator tutorial to verify everything works
reflex run tasks/calculator.yaml
```

---

## Detailed Setup Walkthrough

### Step 0 — Prerequisites

Before anything else, confirm you have:

- [ ] **An Apple Silicon Mac** (M1/M2/M3/M4) — this project is macOS-only
- [ ] **macOS 13 (Ventura) or later** — required for Cua Driver's accessibility APIs
- [ ] **Python 3.12** — the orchestrator is pinned to this version (3.13 is incompatible with mlx-whisper)
  ```bash
  python3 --version
  # Should show Python 3.12.x
  # If not: brew install python@3.12
  ```
- [ ] **Git** installed
  ```bash
  git --version
  ```
- [ ] **Homebrew** (recommended, for installing dependencies)
  ```bash
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  ```

### Step 1 — Clone the Repo

```bash
git clone <your-repo-url>
cd reflex-arc
```

Create the initial folder structure:

```bash
mkdir -p docs tasks runs
```

Copy the five project documents into `/docs`:
```bash
cp files/*.html docs/
```

### Step 2 — Install Cua Driver

Cua Driver is the "eyes and hands" — it reads the UI element tree and performs clicks, typing, and key presses.

1. **Download** `CuaDriver.app` from [https://github.com/trycua/cua](https://github.com/trycua/cua)
2. **Move** it to `/Applications/`
3. **Install the Python SDK** (or CLI — this decision is D2, to be made in week 2):
   ```bash
   pip install cua-driver
   ```

> ⚠️ **Important:** macOS grants Accessibility and Screen Recording permissions to an **app identity**, not a file path. Always use the installed `CuaDriver.app` and its daemon. Never grant permissions to loose binaries — Cua documents this as unsupported.

> ⚠️ **Avoid AGPL extras:** Cua's licence notes mention OmniParser and an optional `cua-agent[omni]` extra that includes an AGPL-licensed dependency. Avoid installing it unless truly needed. Keep AGPL extras out of the repo.

### Step 3 — Grant macOS Permissions

The Driver needs two macOS permissions to work:

1. Open **System Settings → Privacy & Security → Accessibility**
   - Click the `+` button
   - Navigate to `/Applications/CuaDriver.app` and add it
   - Toggle it **on**

2. Open **System Settings → Privacy & Security → Screen Recording**
   - Click the `+` button
   - Add `CuaDriver.app`
   - Toggle it **on**

3. **Restart your Mac** (or at minimum, log out and back in) — macOS sometimes requires this for new permissions to take effect.

### Step 4 — Verify the Driver

```bash
cua-driver doctor
```

This should report all checks passing. If it fails:
- Confirm `CuaDriver.app` is in `/Applications/`
- Confirm both Accessibility and Screen Recording permissions are granted
- Try logging out and back in
- Check the Cua GitHub issues for your macOS version

Then test launching from Python:
```python
# test_driver.py
from cua_driver import CuaDriver

driver = CuaDriver()
window = driver.read_frontmost_window()
print(f"Front window: {window.title}")
print(f"Elements: {len(window.elements)}")
```
```bash
python test_driver.py
```

### Step 5 — Request Jev Early Access

Jev is the fast decision model from TypeSafe. It is in **early access with a waitlist**, so do this first — it may take days or weeks.

1. Go to [https://typesafe.ai](https://typesafe.ai)
2. Request early access to Jev
3. Create a console account
4. Once approved, you'll receive an API key

> 📝 **While waiting:** Everything else can be built and tested using `kev` (Step 6) as a drop-in local stand-in. The system is designed so that swapping to real Jev later needs only a URL and a key change.

### Step 6 — Set Up kev (Local Stand-In)

`kev` is a 0.5B-parameter local model from `jaredpalmer/kev` that serves the **identical** `POST /v1/systemone` contract as Jev. TypeSafe's own SDK works against it with only a `base_url` change.

```bash
# Clone the repo
git clone https://github.com/jaredpalmer/kev.git
cd kev

# Install dependencies using uv (required)
uv sync --extra serve

# Download kev-0.5b weights from GitHub release v0.1.0
# https://github.com/jaredpalmer/kev/releases/download/v0.1.0/kev-0.5b.tar.gz
# Extract to runs/kev/ directory in the kev repo

# Start the local server
uv run --extra serve python -m kev.serve --run jaredpalmer/kev-0.5b --port 8009
```

Verify it's running:
```bash
curl http://localhost:8009/v1/systemone \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"state": "test", "questions": [{"type": "noul", "name": "test", "statement": "The sky is blue"}]}'
```

> ⚠️ **kev is a development stand-in only**, not a copy of Jev. Key limitations:
> - 0.5B parameters (much smaller than Jev)
> - 8,192 token context (vs Jev's ~32k per branch)
> - Untrained on tasks far from passage classification
> - Single-author project with no fine-tuning for this task
>
> **Every number that matters for the final write-up must be measured on real Jev.** kev numbers are for development and testing only.

### Step 7 — Get an OpenRouter API Key

The planner LLM (used for planning, text generation, and escalation rescue) runs through OpenRouter, giving access to many vision-capable models via one API key.

1. Go to [https://openrouter.ai](https://openrouter.ai)
2. Create an account
3. Go to **Keys** → **Create Key**
4. Copy the key (starts with `or-`)

The specific planner model is chosen in week 3 (decision D4), picked by cost and screenshot accuracy. Any vision-capable model on OpenRouter works.

### Step 8 — Configure Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Fill in:

```env
# ─── Decision Backend ───
DECISION_BACKEND=kev          # "kev" (local), "jev" (remote), or "llm" (adapter)

# ─── kev (local stand-in) ───
KEV_BASE_URL=http://localhost:8009

# ─── Jev (fill in when access arrives) ───
JEV_API_KEY=
JEV_BASE_URL=https://api.typesafe.ai

# ─── Planner LLM ───
OPENROUTER_API_KEY=or-your-key-here
PLANNER_MODEL=                # chosen in week 3; any vision-capable model on OpenRouter

# ─── Safety Limits ───
MAX_STEPS=40
MAX_TIME_SECONDS=120
CONFIDENCE_GATE=0.70
MIN_GAP=0.15

# ─── Paths ───
TRACE_DB=./runs/traces.sqlite
SCREENSHOT_DIR=./runs
```

> 🔒 **Security:** API keys live **only** in the orchestrator process. Nothing in the sandbox has access to them. Never commit `.env` to version control.

### Step 9 — Install Python Dependencies

```bash
# Create a virtual environment with Python 3.12
python3.12 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

Key dependencies (expected):
- `langgraph` — state machine for the loop controller
- `cua-driver` or `cua` — the Cua Python SDK
- `fastapi` + `uvicorn` — for the run console backend
- `websockets` — for live trace streaming to the console
- `openai` or `httpx` — for OpenRouter API calls
- `mlx-whisper` — local speech-to-text for voice input (Apple Silicon)
- `pytest` — testing

### Step 10 — Create a Sandbox User (Recommended)

The agent controls a real Mac, so isolation is important. Create a dedicated macOS user:

1. Open **System Settings → Users & Groups**
2. Click the `+` to add a new user
3. Create a standard user (e.g., `reflex-sandbox`)
4. Log into that user and grant `CuaDriver.app` the same Accessibility + Screen Recording permissions
5. Set up an **app allowlist** — only the apps you want the agent to control should be available

> 📝 This is the initial sandbox approach (decision D3). A Lume VM is a stretch goal for later, only if the Driver can run inside it.

### Step 11 — Pin All Versions

Create a `VERSIONS.md` file to track exact versions of everything:

```markdown
# Versions

| Component | Version | Pinned On |
|-----------|---------|-----------|
| Cua Driver | `<exact release>` | Week 0 |
| kev model | `kev-0.5b` | Week 0 |
| Jev model | `<pending access>` | TBD |
| Planner LLM | `<pending selection>` | Week 3 |
| Python | `3.12.x` | Week 0 |
| macOS | `<your version>` | Week 0 |
```

> ⚠️ **Never use "latest"** as a model version. Model aliases can drift — "latest" may change behaviour between runs. Pin the exact version string, store it in every `StepRecord`, and rerun the baseline if it changes.

### Step 12 — Run the Calculator Tutorial

Cua's built-in Calculator tutorial (`6 × 7`) is the first end-to-end test:

```bash
# Follow Cua's getting-started guide to run the Calculator 6 × 7 tutorial
# This verifies that the Driver can read and control an app
```

If this works, the Driver is correctly installed and your permissions are set up right.

### Step 13 — Read the Jev Docs

Before writing any Jev integration code, read these pages from the TypeSafe docs:

- [ ] **Quick Start** — the basic API contract
- [ ] **Choice** — how to ask "which element?" with up to 255 options
- [ ] **Noul** — how to ask yes/no questions with probability answers
- [ ] **Confidence** — how to interpret the confidence value
- [ ] **Patterns** — recommended usage patterns (two-stage score-then-choose, etc.)

### Step 14 — Read Licence Terms

- [ ] Read the **Cua licence** — it's MIT, but extras have other licences (AGPL for OmniParser)
- [ ] Read **TypeSafe's terms of use** — specifically around publishing benchmark results
- [ ] Keep AGPL extras out of the repo

---

## Running a Task

```bash
# Proposed command (finalized during development)
reflex run tasks/reminder.yaml
```

A task YAML file defines:
- The natural-language instruction
- The target app
- The end-state code check

The orchestrator will:
1. Ask the planner LLM to create a plan (once per task)
2. Enter the step loop: look → describe → decide → act → check
3. Log every step to SQLite with screenshots
4. Stream live events to the run console via WebSocket
5. Stop when the goal is reached, a budget is exceeded, or a human stops it

---

## The Hero Task

The hero task is chosen at the end of week 2, after a spike shows which apps expose a usable UI tree. A task qualifies when:

- The app exposes a usable UI element tree (checked in the spike)
- It takes **at least 8 steps** and needs at least **one typed-in text value**
- The end state can be **checked by code**, not only by Jev
- It is **reversible** inside the sandbox and touches no real account, money, or message

### Candidate Tasks

| Candidate | Why it fits | Watch out for |
|-----------|------------|---------------|
| **Reminders / Calendar entry from a sentence** | Small forms, date pickers; easy end-state check | Pickers can be awkward to read from the UI tree |
| **Finder: sort a Downloads folder by rule** | Many steps, visible result, natural approval gate for moves/deletes | Drag and drop may not be reachable through the tree |
| **Two-app handoff: Notes → Mail draft (never sent)** | Shows multi-app work | Mail is heavy; drafts only, never send |

---

## Voice Input

Push-to-talk speech, transcribed locally with `mlx-whisper`, acts as a second input channel:

- **No run active:** A transcript becomes the task, just like typed input.
- **Run active:** The transcript is queued and drained at the top of the next loop iteration. It goes to `planner.replan()` as a correction.
- **Risky action pending:** A spoken correction can redirect or cancel, but **it can never approve a risky action**. The click-to-approve gate is a fixed rule in code.

The mic thread only ever writes to a small queue. It never calls `body.act()`, never touches the gates, and never talks to the decision backend directly.

---

## Decision Backend: Jev → kev → LLM

The `DecisionBackend` is an interface with three implementations:

| Backend | When to use | Notes |
|---------|------------|-------|
| **`JevBackend`** | Production — once Jev access arrives | The real thing. All final measurements use this. |
| **`KevBackend`** | Development — while waiting on Jev access | Speaks the identical `POST /v1/systemone` contract. Swap to Jev by changing `base_url` + key. |
| **`LLMBackend`** | Fallback and baseline comparison | An LLM wrapped to return the same typed answers. Also useful for the stretch-goal head-to-head comparison. |

Switching backends requires only a config change — no code changes.

---

## Safety Rules

These rules are enforced in code and **never depend on a model's confidence**:

1. **Sandbox isolation** — The agent runs in a dedicated macOS user with no personal accounts signed in.
2. **App allowlist** — Only allowlisted apps can be controlled.
3. **Human approval for risky actions** — Deleting, overwriting, sending, and buying **always** need a human click. Voice cannot approve.
4. **Kill switch** — Stops the run within one step.
5. **Hard budgets** — Limits on steps, time, and cost are hard caps, not suggestions.
6. **Key isolation** — API keys live only in the orchestrator process, never in the sandbox.

---

## Success Metrics

| Measure | How it's measured | Target |
|---------|------------------|--------|
| **Task success** | Code check on real end state, over 20 consecutive runs | ≥ 80% (hypothesis) |
| **Steps decided by Jev alone** | Steps with no escalation ÷ all steps | ≥ 70% (hypothesis) |
| **Confident and wrong** | Steps above confidence gate where chosen control was wrong | Reported (calibration table) |
| **Decision latency** | Round trip to Jev per step, p50 and p95 | Reported |
| **Cost per successful run** | Jev + LLM spend, logged per step | Reported |

> Targets marked "hypothesis" are revised after the week 2 baseline. The point is honest numbers, including bad ones.

---

## Run Console (Web UI)

The run console is a web UI that shows three screens:

1. **Run screen** — Live timeline, step list, step inspector with Jev probabilities, confidence gauge, timing breakdown, and screenshots.
2. **Approval screen** — Full-width panel when a risky action needs human approval. Shows what, why, Jev's confidence, and approve/reject/stop buttons.
3. **Batch results** — Task success rate over 20 runs, calibration table (is Jev's confidence honest?), cost per run.

Built with **FastAPI + WebSocket** on the backend; frontend decided in week 10 (plain HTML+JS or React).

---

## Testing

```bash
# Run all tests
pytest

# Run with a fake Body and fake backend (no API cost, no real Mac needed)
pytest tests/ -m "not integration"
```

The testing strategy:
- **Fake Body** — Returns pre-recorded UI trees and screenshots
- **Fake Backend** — Returns pre-recorded Jev/kev answers
- **Record and Replay** — Record a real run, then replay it in tests to verify gates and loop logic without API cost

---

## Project Structure

```
reflex-arc/
├── README.md               # This file
├── VERSIONS.md             # Pinned versions of all components
├── .env                    # API keys and config (not committed)
├── .env.example            # Template for .env
├── requirements.txt        # Python dependencies
├── docs/                   # The five project documents (HTML)
│   ├── project_difination.html
│   ├── how_it_should_work.html
│   ├── system-wiring.html
│   ├── UI.html
│   └── roadmap.html
├── src/                    # Source code
│   ├── orchestrator/       # Loop controller (LangGraph state machine)
│   ├── body/               # Cua Driver adapter
│   ├── backend/            # DecisionBackend interface + Jev/kev/LLM implementations
│   ├── planner/            # Planner LLM integration
│   ├── serializer/         # UI tree → numbered elements
│   ├── gates/              # Confidence, gap, risk, loop-breaker logic
│   ├── trace/              # Trace writer (SQLite + screenshots)
│   ├── voice/              # Push-to-talk + mlx-whisper
│   └── console/            # FastAPI + WebSocket run console
├── tasks/                  # Task YAML definitions
├── runs/                   # Run traces, screenshots, SQLite DB
└── tests/                  # pytest tests with fakes and recorded replays
```

---

## Roadmap

| Phase | Weeks | Dates | What happens |
|-------|-------|-------|-------------|
| **Week 0** | 0 | Sep 22–27 | Request Jev access, install Cua, set up repo, read docs, set up kev |
| **A. Spike** | 1–2 | Sep 28 – Oct 11 | Dump UI trees, measure Jev latency from India, choose hero task, write interfaces |
| **B. Walking Skeleton** | 3–4 | Oct 12–25 | Serializer, loop controller, trace writer, record/replay tests |
| **C. Hero Task + v0 Video** | 5–6 | Oct 26 – Nov 8 | Pruning, planner, all gates, hero task end-to-end, record demo |
| **Reduced Hours** | 7–8 | Nov 9–25 | Exams + festivals. Background runs only, no new features |
| **D. Harden** | 9–10 | Nov 26 – Dec 6 | Tune gates from data, 20 consecutive runs, sandbox, kill switch |
| **E. Console + Eval** | 11 | Dec 7–13 | Live run console, batch results, calibration table |
| **F. Ship** | 12 | Dec 14–20 | README with numbers, final demo video, resume bullet |

### Cut lines (if time runs short, drop in this order)

1. LLM-only baseline comparison
2. A second hero task
3. Lume VM sandbox
4. Live console (fall back to static trace viewer)
5. The write-up

**Never cut:** confidence gating, Noul checks, trace logging, safety rules, or honest metrics. They are the project.

---

## Open Decisions

| ID | Decision | Options | Decide by |
|----|----------|---------|-----------|
| D1 | Hero task | Reminders, Finder, or Notes→Mail | End of week 2 (Oct 11) |
| D2 | How orchestrator talks to Driver | Python SDK (see DECISIONS.md) | ✅ Sep 23, 2026 |
| D3 | Sandbox approach | Dedicated macOS user now; Lume VM later if Driver runs inside it | Week 4, final in weeks 9–10 |
| D4 | Planner/text LLM model | Any vision-capable model on OpenRouter, picked by cost + screenshot accuracy | Week 3 |
| D5 | Console frontend | Plain HTML+JS, or React | Week 10 |
| D6 | When to switch from kev to real Jev | As soon as Jev access arrives; kev stays as offline fallback | Target: no later than week 9 |

---

## Known Caveats

| ID | Caveat | Mitigation |
|----|--------|-----------|
| C1 | **Jev is early access with a waitlist.** No key = no final numbers. | kev serves the same contract as a dev stand-in; LLM adapter as fallback. |
| C2 | **Jev takes text state, not images.** The Driver must yield a usable UI tree. | Spike rates candidate apps in weeks 1–2. Screenshots go only to the planner fallback. |
| C3 | **Choice questions max at 255 options.** Real UI trees are larger. | Serializer prunes and ranks. Score questions can pre-filter. |
| C4 | **Jev answers one request, remembers nothing, can't write text.** | Controller puts short history into each state. Planning and text stay with the LLM. |
| C5 | **Speed claims are from TypeSafe's US labs.** Round trip from India will be longer. | Measure p50/p95 in week 1. Pack all questions per step into one request. |
| C6 | **macOS grants permissions to an app identity, not a path.** | Use installed CuaDriver.app. Never grant permissions to loose binaries. |
| C7 | **Driver SDK is marked experimental and moves fast.** | Pin the release, hide calls behind a Body adapter, test against a fake Body. |
| C8 | **Model aliases can drift.** | Pin exact version strings, store in every StepRecord. |
| C9 | **Agent controls a real Mac.** | Sandbox user, app allowlist, approval gate, kill switch, hard budgets. |
| C10 | **Vendor numbers ≠ your numbers.** | Measure everything on the hero task. Judge by code check, not Jev. |
| C11 | **Licences.** Cua extras have AGPL. TypeSafe terms on benchmarks are unread. | Read terms in week 0. Keep AGPL out of repo. |
| C12 | **Voice is a second input channel reaching a running loop.** | Queue drains at one fixed point. Risky actions always need a UI click. |
| C13 | **kev is a 0.5B stand-in, not Jev.** | Dev/test only. Final numbers on real Jev. |

---

## Deliverables

- [ ] A **public repo** with a README that states measured numbers and a failure analysis
- [ ] A **demo video** (~90 seconds): screen recording beside the live trace
- [ ] The **run console** (web UI)
- [ ] These **five docs**, kept current, under `/docs`
- [ ] One **resume bullet** that uses only numbers from your own runs

---

## Docs

The five project documents live under `/docs` and can be opened in a browser:

| Document | What it covers |
|----------|---------------|
| [Project Definition](docs/project_difination.html) | Scope, hero task candidates, success measures, constraints |
| [How It Should Work](docs/how_it_should_work.html) | The step loop, who decides what, escalation triggers, sample run |
| [System Wiring](docs/system-wiring.html) | Architecture diagram, interfaces, StepRecord shape, tech choices, caveats |
| [UI](docs/UI.html) | Run console mockup (interactive), approval screen, batch results, design rules |
| [Roadmap](docs/roadmap.html) | 12-week plan with Gantt chart, phase details, cut lines, caveat resolution timeline |

---

## License

TBD — to be decided after reading TypeSafe's terms and Cua's licence requirements.
