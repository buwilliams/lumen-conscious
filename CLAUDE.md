# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Lumen is a consciousness/AI agent architecture — a self-modifying system with values, goals, and identity that evolve through experience. Python, managed with `uv`.

## Commands

```
uv run lumen init              # Scaffold new instance (instances/default/, .git)
uv run lumen seed              # Seed instance with personalized identity (interactive or --file)
uv run lumen chat              # Interactive REPL conversation (runs action loop per turn)
uv run lumen chat --ablation   # Chat with reflection loop suppressed
uv run lumen start             # Internal loop: alternates action, explore, and reflect cycles
uv run lumen start --ablation  # Run without reflection (for experiments)
uv run lumen trigger action    # Manually trigger action loop (MODEL → CANDIDATES → PREDICT → DECIDE → ACT → RECORD)
uv run lumen trigger explore   # Manually trigger explore loop (generate open-ended question)
uv run lumen trigger reflect   # Manually trigger reflection (REVIEW → ASK → EVOLVE)
uv run lumen about             # Print soul, values, goals, skills, memory counts
uv run lumen about --memories          # Also show recent memories
uv run lumen about --author self       # Filter memories by author
uv run lumen about --date 2026-02-14   # Filter memories by date
uv run lumen --data-dir PATH chat      # Use a different instance data directory
uv run lumen experiment list           # List registered experiments
uv run lumen experiment run NAME       # Run a named experiment
uv run lumen experiment compare NAME   # Generate comparison report
```

## Architecture

Three layers: **main.py** (CLI router) → **kernel/** (brain) → **skills/** (hands).

### Kernel (`kernel/`)

Central orchestrator. Runs three loops, manages all state in instance data directories, invokes skills as subprocesses. Has a built-in "create skill" tool for LLM-driven skill authoring. All prompt templates live in `kernel/prompts/[step]/` as `system.md` + `prompt.md` pairs — no prompt text in Python source. Chat is handled in-kernel (`kernel/chat.py`).

Key modules: `data.py` (all file I/O with file locking), `tools.py` (tool registry + handlers), `llm/` (multi-provider: Anthropic, OpenAI, xAI), `memory.py` (semantic retrieval via embeddings), `context.py` (conversation compaction), `config.py` (config loading with deep merge).

### Skills (`skills/[name]/`)

Standalone programs created by the system at runtime. Each has a required `main.py` entry point, communicates via stdin/stdout, must implement `--help`. Skills manage their own dependencies independent of kernel's .venv. No skill-to-skill communication — everything routes through kernel.

### Instance Data (`instances/[name]/`)

Mutable instance state. Git-tracked for rollback and audit.

- `soul.md` — Identity narrative (reflection loop only writes)
- `values.json` — `{name, weight: 0.0-1.0, status: active|deprecated}`
- `goals/[year].json` — `{name, weight: 0.0-1.0, status: todo|working|done|perpetual|deprecated}`
- `memory/[year]/[year]-[month]-[day].jsonl` — Append-only log with `{timestamp, author: self|kernel|goal|external, weight, situation, description}`

## Three Loops

**Action Loop** (exploits goals): MODEL → CANDIDATES → PREDICT → DECIDE → ACT → RECORD. Writes memories and goal status changes. Cannot modify values or soul.md.

**Explore Loop** (seeks novelty): EXPLORE → PREDICT → RECORD. Generates open-ended questions from perpetual goals. Writes memories and can create new goals. Alternates with action loop during `lumen start`.

**Reflection Loop** (metaprogramming): REVIEW → ASK → PREDICT → EVOLVE. The only loop that can modify values, goal weights, perpetual status, and soul.md. Triggered by: prediction deltas, value conflicts, goal completion/staleness, periodic cycles, or explicit request.

All three loops include a PREDICT step for counterfactual reasoning (cause and effect) before committing to action.

## B=MAP Scoring

Candidate actions scored as **B = M × A × P**:
- **M (Motivation)**: Value+goal alignment (0.0–1.0)
- **A (Ability)**: Skill exists? 1.0 or 0.0 (if 0, create skill instead)
- **P (Prompt)**: Trigger strength — 1.0 for direct, decays for indirect

## Tool Filtering

- `read_values` excludes deprecated values by default
- `read_goals` excludes done and deprecated goals by default (pass explicit `status` to override)

## Write Permissions

| File | Action Loop | Explore Loop | Reflection Loop |
|------|------------|-------------|-----------------|
| soul.md | read | read | read+write |
| values.json | read | read | read+write |
| goals (status) | read+write | read+write (create) | read+write |
| goals (weight/perpetual) | read | read | read+write |
| skills | read+write (create) | read | read |
| memory | read+write | read+write | read+write |

## Configuration

`config.default.json` holds defaults; `config.json` overrides via deep merge. Key settings:

- `llm.provider` / `llm.model` — LLM backend (anthropic, openai, xai)
- `embedding.provider` / `embedding.model` — Embedding backend for semantic memory retrieval
- `memory.retrieve_count` — How many memories to retrieve per query
- `reflection.cycle_interval` / `prediction_delta_threshold` — When reflection triggers
- `run.throttle_seconds` — Pause between trios in `lumen start`
- `tools.steps.[step].tools` / `.required` — Per-step tool availability and required tool calls

## LLM Integration

`kernel/llm/` provides two calling patterns:
- `call_llm(system, user)` — Single-shot text completion
- `run_agentic(system, user, tools)` — Agentic tool-use loop: sends prompts + tool schemas, executes returned tool calls, loops until LLM stops or max_iterations (default 10)

Each loop step uses `run_agentic` with the tool set defined in config for that step. Required tools are enforced — if the LLM doesn't call them, the step retries.

## Key Constraints

- Kernel enforces loop sequencing and write permissions; LLM provides judgment within that structure
- The system can change what it thinks/values/is — it cannot change how thinking happens
- Memory: kernel-authored entries are the audit trail (immutable, below consciousness); reflection reads only self/goal/external memories
- Concurrency: `lumen start` and `lumen chat` can coexist — append-only JSONL, file locking for JSON writes (fcntl)
- Memory retrieval: union of N most recent + top-K semantic (OpenAI embeddings), with weight decay over time
- Context compaction: long conversations are automatically summarized when they exceed ~12K chars, keeping the last 6 turns verbatim

## Experiment Framework (`experiment/`)

Supports ablation studies with record/replay. `lumen start --record PATH` captures events; `--replay PATH` replays them. The `--ablation` flag suppresses reflection to measure its impact. Experiments are registered in `experiment/__init__.py` and run via `lumen experiment run NAME`.
