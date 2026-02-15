import sys

from kernel import data
from kernel.llm import run_agentic
from kernel.prompts import load_prompt
from kernel.tools import load_tools, check_required_tools


def _log(msg: str):
    """Print a kernel progress message to stderr."""
    print(f"  [kernel] {msg}", file=sys.stderr, flush=True)


def run_explore_loop() -> dict:
    """Run the explore loop: generate an open-ended question.

    Uses run_agentic with explore tools (read state + record_memory).

    Returns dict with keys: question, text.
    """
    _log("EXPLORE ...")
    explore_tools = load_tools("explore")
    system, user = load_prompt("explore", {})

    explore_result = run_agentic(system, user, explore_tools)

    # Check required tools
    missing = check_required_tools("explore", explore_result.tool_calls_made)
    if missing:
        _log(f"EXPLORE: missing required tools {missing}, retrying...")
        retry_user = user + f"\n\nYou must use the following tools: {', '.join(missing)}. Please try again."
        explore_result = run_agentic(system, retry_user, explore_tools)

    data.append_memory(data.make_memory(
        author="kernel",
        weight=0.4,
        situation="explore loop",
        description=f"EXPLORE: tools_used={len(explore_result.tool_calls_made)} iterations={explore_result.iterations}",
    ))

    return {"question": explore_result.text, "text": explore_result.text}
