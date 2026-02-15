import sys

from kernel import data
from kernel.llm import call_llm, run_agentic
from kernel.prompts import load_prompt
from kernel.tools import load_tools, check_required_tools


def _log(msg: str):
    """Print a kernel progress message to stderr."""
    print(f"  [kernel] {msg}", file=sys.stderr, flush=True)


def _run_agentic_step(step: str, variables: dict):
    """Run an agentic step with tool checking and retry."""
    tools = load_tools(step)
    system, user = load_prompt(step, variables)
    result = run_agentic(system, user, tools)

    missing = check_required_tools(step, result.tool_calls_made)
    if missing:
        _log(f"{step.upper()}: missing required tools {missing}, retrying...")
        retry_user = user + f"\n\nYou must use the following tools: {', '.join(missing)}. Please try again."
        result = run_agentic(system, retry_user, tools)

    return result


def run_explore_loop() -> dict:
    """Run the explore loop: EXPLORE -> PREDICT -> RECORD.

    EXPLORE generates a question (agentic, reads state).
    PREDICT evaluates whether pursuing it matters (call_llm, no tools).
    RECORD commits the question and prediction to memory and optionally
    creates a goal (agentic, has record_memory and update_goal).

    Returns dict with keys: question, prediction, text.
    """
    # --- EXPLORE ---
    _log("EXPLORE ...")
    explore_result = _run_agentic_step("explore", {})
    explore_output = explore_result.text

    data.append_memory(data.make_memory(
        author="kernel",
        weight=0.4,
        situation="explore loop",
        description=f"EXPLORE: tools_used={len(explore_result.tool_calls_made)} iterations={explore_result.iterations}",
    ))

    # --- PREDICT ---
    _log("PREDICT ...")
    system, user = load_prompt("explore_predict", {
        "explore_output": explore_output,
    })
    prediction_output = call_llm(system, user)

    data.append_memory(data.make_memory(
        author="kernel",
        weight=0.4,
        situation="explore loop",
        description="PREDICT: evaluated whether question is worth pursuing",
    ))

    # --- RECORD ---
    _log("RECORD ...")
    record_result = _run_agentic_step("explore_record", {
        "explore_output": explore_output,
        "prediction_output": prediction_output,
    })

    data.append_memory(data.make_memory(
        author="kernel",
        weight=0.4,
        situation="explore loop",
        description=f"RECORD: tools_used={len(record_result.tool_calls_made)} iterations={record_result.iterations}",
    ))

    return {
        "question": explore_output,
        "prediction": prediction_output,
        "text": record_result.text,
    }
