# Lumen

A consciousness architecture for self-modifying AI agents. Lumen models an agent with values, goals, and identity that evolve through experience via three core loops:

- **Action Loop** — Pursues goals using B=MAP scoring to select the best action
- **Explore Loop** — Seeks novelty by generating open-ended questions from perpetual goals
- **Reflection Loop** — Questions and modifies its own values, goals, and identity

## Architecture

```
main.py              # CLI entry point
kernel/              # Brain — orchestrates loops, manages state
  prompts/           # LLM prompt templates (system.md + prompt.md per step)
skills/              # Hands — standalone programs invoked as subprocesses
  chat/              # Primary user interaction skill
data/                # Mutable instance state (git-tracked)
  soul.md            # Identity narrative
  values.json        # Values with weights
  goals/             # Goals partitioned by year
  memory/            # Append-only JSONL memory log
```

## Usage

Requires [uv](https://docs.astral.sh/uv/) and Python.

```bash
uv run lumen init      # Scaffold a new instance
uv run lumen chat      # Start a conversation
uv run lumen run       # Start the internal action/explore loop
uv run lumen reflect   # Manually trigger self-reflection
uv run lumen status    # View current state
```

See [docs/spec.md](docs/spec.md) for the full architecture specification.
