import json
from datetime import datetime
from pathlib import Path

import kernel.data as kdata
from kernel.config import load_config
from kernel.llm import run_agentic
from kernel.log import dim
from kernel.prompts import load_prompt
from kernel.tools import load_tools, check_required_tools


def _log(msg: str):
    dim(f"  [kernel] {msg}")


def run_seed(soul_text: str):
    """Seed a new instance: scaffold directories, write soul, run LLM to generate values/goals."""
    year = datetime.now().year

    # Scaffold directories
    (kdata.DATA_DIR / "memory" / str(year)).mkdir(parents=True, exist_ok=True)
    (kdata.DATA_DIR / "goals").mkdir(parents=True, exist_ok=True)
    (kdata.DATA_DIR / "conversations").mkdir(parents=True, exist_ok=True)
    (Path.cwd() / "skills").mkdir(exist_ok=True)

    # Write soul.md
    kdata.write_soul(soul_text)

    # Write empty values and goals so tools can read them
    kdata.write_values([])
    kdata.write_goals([], year)

    # Run seed agentic step
    _log("SEED ...")
    tools = load_tools("seed")
    system, user = load_prompt("seed", {"soul": soul_text})
    result = run_agentic(system, user, tools)

    missing = check_required_tools("seed", result.tool_calls_made)
    if missing:
        _log(f"SEED: missing required tools {missing}, retrying...")
        retry_user = user + f"\n\nYou must use the following tools: {', '.join(missing)}. Please try again."
        result = run_agentic(system, retry_user, tools)

    # Record first memory
    kdata.append_memory(kdata.make_memory(
        author="self",
        weight=1.0,
        situation="awakening",
        description="I am awake for the first time.",
    ))

    return result
