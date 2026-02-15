# Lumen

Lumen is a consciousness architecture for AI agents. It models a system with values, goals, and identity that evolve through experience — the system can change what it thinks, what it values, and who it is, but it cannot change how thinking happens.

The theoretical foundation is described in [A Theory of Consciousness](https://github.com/buwilliams/buddy-williams-writings/blob/main/essays/theory-of-consciousness.md).

## How It Works

Lumen runs three loops that together produce something like a cognitive cycle:

- **Action** — Pursues goals. Perceives the current situation, generates candidate actions, scores them, executes the best one, and records what happened versus what was predicted.
- **Explore** — Seeks novelty. Generates open-ended questions from perpetual goals to surface gaps in the system's understanding. Without this, the system can only exploit what it already knows.
- **Reflection** — Questions itself. Reviews recent experience, asks whether its values and goals still make sense, and modifies them if they don't. This is the only loop that can rewrite the system's identity.

Each loop includes a prediction step for counterfactual reasoning before committing to action. When predictions are wrong, the delta can trigger reflection.

## Usage

Requires [uv](https://docs.astral.sh/uv/) and Python.

```bash
uv run lumen init                        # Scaffold a new instance
uv run lumen chat                        # Interactive conversation
uv run lumen start                       # Autonomous loop: action → explore → reflect
uv run lumen about                       # Print soul, values, goals, skills, memory counts
```

You can also trigger individual loops manually:

```bash
uv run lumen trigger action              # Run one action cycle
uv run lumen trigger explore             # Run one explore cycle
uv run lumen trigger reflect             # Run one reflection cycle
```

Inspect the system's memory:

```bash
uv run lumen about --memories            # Show recent memories
uv run lumen about --author self         # Filter by author (self, kernel, goal, external)
uv run lumen about --date 2026-02-14     # Filter by date
```

Multiple instances can run from separate data directories:

```bash
uv run lumen --data-dir ./instances/other chat
```

## Architecture

The codebase has three layers: the CLI routes commands, the kernel orchestrates loops and manages state, and skills are standalone programs the kernel invokes as subprocesses.

```
main.py                  # CLI (Click)
kernel/                  # Orchestrates loops, manages state
  prompts/               # LLM prompt templates (system.md + prompt.md per step)
  chat.py                # Conversation session management
  loop_action.py         # Action loop
  loop_exploration.py    # Explore loop
  loop_reflection.py     # Reflection loop
skills/                  # Standalone skill programs (created by the system at runtime)
instances/               # Instance data directories
  default/               # Default instance
experiment/              # Experiment framework for ablation studies
```

### Instance Data

Each instance maintains its own mutable state, git-tracked for rollback and audit:

- `soul.md` — Identity narrative
- `values.json` — Weighted values that guide action scoring
- `goals/` — Goals partitioned by year, with weights and statuses
- `memory/` — Append-only daily JSONL logs

### Write Permissions

The kernel enforces what each loop can modify. Action and explore loops can read the full state but can only write memories and goal statuses. Reflection is the only loop that can change values, goal weights, and the identity narrative.

### Skills

Skills are standalone programs with a `main.py` entry point that communicate via stdin/stdout. The system can author new skills at runtime through the action loop. Skills manage their own dependencies and route all communication through the kernel.
