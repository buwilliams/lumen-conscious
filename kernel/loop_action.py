import json
import re
import sys

from kernel import data
from kernel.config import load_config
from kernel.llm import call_llm, run_agentic
from kernel.prompts import load_prompt
from kernel.tools import load_tools, check_required_tools


def _log(msg: str):
    """Print a kernel progress message to stderr."""
    print(f"  [kernel] {msg}", file=sys.stderr, flush=True)


def _run_agentic_step(step: str, variables: dict) -> "AgenticResult":
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


def run_action_loop(situation: str | None = None, conversation_history: str = "") -> dict:
    """Run the action loop: MODEL -> CANDIDATES -> PREDICT -> DECIDE -> ACT -> RECORD.

    Each step does one cognitive task. MODEL and CANDIDATES use agentic tool calls.
    PREDICT and RECORD use plain call_llm (no tools, pure reasoning).
    DECIDE uses agentic tool calls. ACT uses agentic tool calls.

    Returns dict with keys: action, result, response, record, delta.
    """
    from kernel.soul import compact_soul
    compact_soul()

    config = load_config()
    sit = situation or "No external trigger. Internal cycle."

    # --- MODEL ---
    _log("MODEL ...")
    model_result = _run_agentic_step("model", {
        "situation": sit,
        "conversation_history": conversation_history,
    })
    model_output = model_result.text

    data.append_memory(data.make_memory(
        author="kernel",
        weight=0.5,
        situation=sit,
        description=f"MODEL: {model_output}",
    ))

    # --- CANDIDATES ---
    _log("CANDIDATES ...")
    candidates_result = _run_agentic_step("candidates", {
        "model_output": model_output,
    })
    candidates_output = candidates_result.text

    data.append_memory(data.make_memory(
        author="kernel",
        weight=0.5,
        situation=sit,
        description=f"CANDIDATES: {candidates_output}",
    ))

    # --- PREDICT ---
    _log("PREDICT ...")
    system, user = load_prompt("predict", {
        "candidates_output": candidates_output,
    })
    predictions_output = call_llm(system, user)

    data.append_memory(data.make_memory(
        author="kernel",
        weight=0.5,
        situation=sit,
        description=f"PREDICT: {predictions_output}",
    ))

    # --- DECIDE ---
    _log("DECIDE ...")
    decide_result = _run_agentic_step("decide", {
        "predictions_output": predictions_output,
    })

    decision = _parse_json(decide_result.text) or {}
    selected = decision.get("selected", {})

    data.append_memory(data.make_memory(
        author="kernel",
        weight=0.5,
        situation=sit,
        description=f"DECIDE: {json.dumps(decision)}",
    ))

    # Check for skip recommendation (motivation too low)
    if decision.get("skip"):
        data.append_memory(data.make_memory(
            author="kernel",
            weight=0.3,
            situation=sit,
            description="DECIDE: Skipped — motivation too low",
        ))
        return {"action": "skip", "result": None, "response": None, "record": None, "delta": 0.0}

    # --- ACT ---
    _log("ACT ...")
    act_tools = load_tools("act")
    system, user = load_prompt("act", {
        "selected_output": json.dumps(selected, indent=2),
    })

    act_result = run_agentic(system, user, act_tools)
    response = act_result.text

    # Ensure skill outputs aren't lost if the LLM doesn't repeat them in its text
    skill_outputs = [
        tc["result"] for tc in act_result.tool_calls_made
        if tc["name"] == "invoke_skill" and tc.get("result")
    ]
    if skill_outputs and not response:
        response = skill_outputs[-1]
    elif skill_outputs:
        for so in skill_outputs:
            if so not in response:
                response = f"{response}\n\n{so}"

    data.append_memory(data.make_memory(
        author="kernel",
        weight=0.5,
        situation=sit,
        description=f"ACT: {response}",
    ))

    # --- RECORD ---
    _log("RECORD ...")
    prediction = selected.get("prediction", predictions_output[-500:])
    system, user = load_prompt("record", {
        "prediction": prediction,
        "outcome": str(response)[:2000],
    })
    record_raw = call_llm(system, user)
    record_result = _parse_json(record_raw) or {}
    delta = record_result.get("delta", 0.0)

    data.append_memory(data.make_memory(
        author="kernel",
        weight=0.5,
        situation=sit,
        description=f"RECORD: delta={delta} {json.dumps(record_result)}",
    ))

    return {
        "action": selected.get("action", "action"),
        "result": response,
        "response": response,
        "record": record_result,
        "delta": delta,
    }


def _parse_json(text: str) -> dict | None:
    """Parse JSON from markdown code fences or raw JSON. Used only for RECORD step."""
    pattern = r'```(?:json)?\s*\n(.*?)\n```'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
