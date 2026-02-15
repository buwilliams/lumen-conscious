# Lumen

A consciousness architecture for AI agents. A self-modifying system with values, goals, and identity that evolve through experience via three core loops.

Based on the essay [A Theory of Consciousness](https://github.com/buwilliams/buddy-williams-writings/blob/main/essays/theory-of-consciousness.md).

## Architecture

Three layers: **CLI** (router) → **Kernel** (brain) → **Skills** (hands).

```
main.py                  # CLI entry point (Click)
kernel/                  # Orchestrates loops, manages state, invokes skills
  prompts/               # LLM prompt templates (system.md + prompt.md per step)
    model/               # Perception — reads state, produces situation model
    candidates/          # Generates 1-3 candidate actions
    predict/             # Counterfactual reasoning for action candidates
    explore_predict/     # Counterfactual reasoning for explore questions
    reflect_predict/     # Counterfactual reasoning for proposed changes
    decide/              # B=MAP scoring, selects best candidate
    act/                 # Executes the selected action
    record/              # Compares prediction vs outcome, computes delta
    explore/             # Generates open-ended questions
    explore_record/      # Records question, optionally creates goal
    review/              # Summarizes what happened since last reflection
    ask/                 # Questions own values and goals
    evolve/              # Consistency-checks and applies changes
    trigger/             # Evaluates whether to enter reflection
    summarize/           # Yearly memory summarization
skills/                  # Standalone programs, each with main.py entry point
  chat/                  # Primary user interaction skill
instances/               # Instance data directories
  default/               # Default instance (scaffolded by `lumen init`)
experiment/              # Experiment framework for ablation studies
```

### Kernel

Central orchestrator. Runs three loops, manages all state, invokes skills as subprocesses. Has a built-in "create skill" tool for LLM-driven skill authoring. All prompt templates live in `kernel/prompts/[step]/` as `system.md` + `prompt.md` pairs — no prompt text in Python source.

### Skills

Standalone programs. Each has a required `main.py` entry point, communicates via stdin/stdout, must implement `--help`. Skills manage their own dependencies independent of kernel's .venv. No skill-to-skill communication — everything routes through kernel.

### Instance Data

Mutable instance state. Git-tracked for rollback and audit.

- `soul.md` — Identity narrative (only reflection loop can write)
- `values.json` — `{name, weight: 0.0-1.0, status: active|deprecated}`
- `goals/[year].json` — `{name, weight: 0.0-1.0, status: todo|working|done|perpetual}`
- `memory/[year]/[year]-[month]-[day].jsonl` — Append-only log with `{timestamp, author, weight, situation, description}`

## Three Loops

**Action Loop** (exploit): MODEL → CANDIDATES → PREDICT → DECIDE → ACT → RECORD
Pursues goals. Writes memories and goal status changes. Cannot modify values or soul.

**Explore Loop** (novelty): EXPLORE → PREDICT → RECORD
Generates open-ended questions from perpetual goals. Writes memories and can create new goals.

**Reflection Loop** (metaprogramming): REVIEW → ASK → PREDICT → EVOLVE
The only loop that can modify values, goal weights, perpetual status, and soul. Triggered by prediction deltas, value conflicts, goal completion/staleness, periodic cycles, or explicit request.

All three loops include a PREDICT step for counterfactual reasoning before committing.

## B=MAP Scoring

Candidate actions scored as **B = M × A × P**:
- **M (Motivation)**: Value+goal alignment (0.0–1.0)
- **A (Ability)**: Skill exists? 1.0 or 0.0 (if 0, create skill instead)
- **P (Prompt)**: Trigger strength — 1.0 for direct, decays for indirect

## Write Permissions

| File | Action | Explore | Reflection |
|------|--------|---------|------------|
| soul.md | read | read | read+write |
| values.json | read | read | read+write |
| goals (status) | read+write | read+write (create) | read+write |
| goals (weight/perpetual) | read | read | read+write |
| skills | read+write (create) | read | read |
| memory | read+write | read+write | read+write |

## Usage

Requires [uv](https://docs.astral.sh/uv/) and Python.

```bash
uv run lumen init                        # Scaffold a new instance
uv run lumen chat                        # Interactive conversation (action loop per turn)
uv run lumen start                       # Internal loop: action → explore → reflect cycles
uv run lumen trigger action              # Manually trigger one action loop
uv run lumen trigger explore             # Manually trigger one explore loop
uv run lumen trigger reflect             # Manually trigger one reflection loop
uv run lumen about                       # Print soul, values, goals, skills, memory counts
uv run lumen about --memories            # Also show recent memories
uv run lumen about --author self         # Filter memories by author
uv run lumen about --date 2026-02-14     # Filter memories by date
```

### Options

```bash
--data-dir PATH          # Use a different instance data directory (env: LUMEN_DATA_DIR)
chat --session ID        # Resume a conversation session
chat --ablation          # Suppress reflection loop
start --timeout MS       # Timeout in milliseconds (default: 1800000)
start --ablation         # Suppress reflection loop (for experiments)
```

### Experiments

```bash
uv run lumen experiment list             # List registered experiments
uv run lumen experiment run <name>       # Run an experiment
uv run lumen experiment compare <name>   # Generate comparison report
uv run lumen experiment cleanup <name>   # Delete experiment output
```

## Key Constraints

- Kernel enforces loop sequencing and write permissions; LLM provides judgment within that structure
- The system can change what it thinks/values/is — it cannot change how thinking happens
- Kernel-authored memories are the audit trail (below consciousness); reflection reads only self/goal/external memories
- `lumen start` and `lumen chat` can coexist — append-only JSONL, last-write-wins for JSON
- Memory retrieval: union of N most recent + top-K semantic (OpenAI embeddings), with weight decay over time
