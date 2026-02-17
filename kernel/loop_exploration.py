from kernel import data
from kernel.llm import call_llm, run_agentic
from kernel.log import dim
from kernel.prompts import load_prompt
from kernel.tools import load_tools, check_required_tools


def _log(msg: str):
    """Print a dim kernel progress message to stderr."""
    dim(f"  [kernel] {msg}")


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


def run_explore_loop(replay_data: dict | None = None) -> dict:
    """Run the explore loop: EXPLORE -> PREDICT -> RECORD.

    EXPLORE generates a question (agentic, reads state).
    PREDICT evaluates whether pursuing it matters (call_llm, no tools).
    RECORD commits the question and prediction to memory and optionally
    creates a goal (agentic, has record_memory and update_goal).

    If replay_data is provided (keys: question, prediction), EXPLORE and
    PREDICT are skipped and the recorded outputs are used instead. The
    RECORD step still runs so both systems accumulate the same goals.

    Returns dict with keys: question, prediction, text.
    """
    from kernel.soul import compact_soul
    compact_soul()

    if replay_data:
        # --- REPLAY MODE: skip LLM calls, use recorded outputs ---
        explore_output = replay_data["question"]
        prediction_output = replay_data["prediction"]
        _log(f"EXPLORE (replay): {explore_output[:100]}")
        _log(f"PREDICT (replay): {prediction_output[:100]}")

        data.append_memory(data.make_memory(
            author="kernel",
            weight=0.4,
            situation="explore loop",
            description=f"EXPLORE: {explore_output}",
        ))
        data.append_memory(data.make_memory(
            author="kernel",
            weight=0.4,
            situation="explore loop",
            description=f"PREDICT: {prediction_output}",
        ))
    else:
        # --- EXPLORE ---
        _log("EXPLORE ...")
        explore_result = _run_agentic_step("explore", {})
        explore_output = explore_result.text

        data.append_memory(data.make_memory(
            author="kernel",
            weight=0.4,
            situation="explore loop",
            description=f"EXPLORE: {explore_output}",
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
            description=f"PREDICT: {prediction_output}",
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
        description=f"RECORD: {record_result.text}",
    ))

    return {
        "question": explore_output,
        "prediction": prediction_output,
        "text": record_result.text,
    }
