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


def run_action_loop(situation: str | None = None, conversation_history: str = "") -> dict:
    """Run the action loop: THINK -> DECIDE -> ACT -> RECORD.

    Each step (except RECORD) is a run_agentic call with step-appropriate tools.
    The kernel controls step sequencing — the LLM cannot skip steps.

    Returns dict with keys: action, result, response, record, delta.
    """
    config = load_config()
    sit = situation or "No external trigger. Internal cycle."

    # --- THINK ---
    _log("THINK ...")
    think_tools = load_tools("think")
    system, user = load_prompt("think", {
        "situation": sit,
        "conversation_history": conversation_history,
    })

    think_result = run_agentic(system, user, think_tools)

    # Check required tools
    missing = check_required_tools("think", think_result.tool_calls_made)
    if missing:
        _log(f"THINK: missing required tools {missing}, retrying...")
        retry_user = user + f"\n\nYou must use the following tools: {', '.join(missing)}. Please try again."
        think_result = run_agentic(system, retry_user, think_tools)

    think_text = think_result.text

    data.append_memory(data.make_memory(
        author="kernel",
        weight=0.5,
        situation=sit,
        description=f"THINK: tools_used={len(think_result.tool_calls_made)} iterations={think_result.iterations}",
    ))

    # --- DECIDE ---
    _log("DECIDE ...")
    decide_tools = load_tools("decide")
    system, user = load_prompt("decide", {
        "candidates": think_text,
    })

    decide_result = run_agentic(system, user, decide_tools)

    # Check required tools
    missing = check_required_tools("decide", decide_result.tool_calls_made)
    if missing:
        _log(f"DECIDE: missing required tools {missing}, retrying...")
        retry_user = user + f"\n\nYou must use the following tools: {', '.join(missing)}. Please try again."
        decide_result = run_agentic(system, retry_user, decide_tools)

    decide_text = decide_result.text

    data.append_memory(data.make_memory(
        author="kernel",
        weight=0.5,
        situation=sit,
        description=f"DECIDE: tools_used={len(decide_result.tool_calls_made)} iterations={decide_result.iterations}",
    ))

    # Check for skip recommendation (motivation too low)
    decide_lower = decide_text.lower()
    if "skip" in decide_lower and "motivation" in decide_lower and "low" in decide_lower:
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
        "selected": decide_text,
        "situation": sit,
    })

    act_result = run_agentic(system, user, act_tools)
    response = act_result.text

    # If skills were invoked, capture their output
    for tc in act_result.tool_calls_made:
        if tc["name"] == "invoke_skill":
            response = tc.get("result", response)

    data.append_memory(data.make_memory(
        author="kernel",
        weight=0.5,
        situation=sit,
        description=f"ACT: tools_used={len(act_result.tool_calls_made)} response_length={len(response)}",
    ))

    # --- RECORD ---
    # One-shot call_llm — kernel writes prediction vs outcome as audit trail
    _log("RECORD ...")
    system, user = load_prompt("record", {
        "situation": sit,
        "prediction": _extract_prediction(decide_text),
        "outcome": str(response)[:2000],
    })
    record_raw = call_llm(system, user)
    record_result = _parse_json(record_raw) or {}
    delta = record_result.get("delta", 0.0)

    data.append_memory(data.make_memory(
        author="kernel",
        weight=0.5,
        situation=sit,
        description=f"RECORD: delta={delta} {json.dumps(record_result.get('delta_description', ''))}",
    ))

    return {
        "action": _extract_action(decide_text),
        "result": response,
        "response": response,
        "record": record_result,
        "delta": delta,
    }


def _extract_prediction(decide_text: str) -> str:
    """Extract prediction from DECIDE text. Best-effort."""
    lower = decide_text.lower()
    for marker in ["prediction:", "predicted outcome:", "expected outcome:"]:
        idx = lower.find(marker)
        if idx >= 0:
            start = idx + len(marker)
            end = decide_text.find("\n", start + 1)
            if end < 0 or end - start > 500:
                end = start + 500
            return decide_text[start:end].strip()
    return decide_text[-200:] if decide_text else "(no prediction)"


def _extract_action(decide_text: str) -> str:
    """Extract action name from DECIDE text. Best-effort."""
    lower = decide_text.lower()
    for marker in ["selected action:", "selected:", "action:"]:
        idx = lower.find(marker)
        if idx >= 0:
            start = idx + len(marker)
            end = decide_text.find("\n", start + 1)
            if end < 0:
                end = start + 200
            return decide_text[start:end].strip()[:200]
    return "action"


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
