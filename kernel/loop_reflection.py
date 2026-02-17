import json
import re

from kernel import data, memory
from kernel.config import load_config
from kernel.llm import call_llm, run_agentic
from kernel.log import dim
from kernel.prompts import load_prompt
from kernel.tools import load_tools, check_required_tools


def _log(msg: str):
    """Print a dim kernel progress message to stderr."""
    dim(f"  [kernel] {msg}")


def _format_memories(memories: list[data.Memory]) -> str:
    """Format memories for prompt inclusion."""
    if not memories:
        return "(no memories yet)"
    lines = []
    for m in memories:
        lines.append(f"- [{m.timestamp}] ({m.author}) {m.description}")
    return "\n".join(lines)


def should_reflect(cycles_since_reflection: int, recent_prediction_errors: list[float] | None = None) -> dict:
    """Evaluate whether to enter the reflection loop.

    Returns dict with should_reflect bool and triggers list.
    Uses one-shot call_llm — this is a kernel gate, not an LLM action.
    """
    config = load_config()
    ref_config = config["reflection"]
    mems = memory.retrieve_memories(ref_config.get("staleness_cycles", 10) * 4)

    pe_str = "(none)"
    if recent_prediction_errors:
        lines = []
        for pe in recent_prediction_errors:
            sign = "+" if pe > 0 else ""
            label = "better than expected" if pe > 0 else "worse than expected"
            lines.append(f"- pe={sign}{pe:.2f} ({label})")
        pe_str = "\n".join(lines)

    system, user = load_prompt("trigger", {
        "memories": _format_memories(mems),
        "prediction_errors": pe_str,
        "cycles_since_reflection": str(cycles_since_reflection),
        "reflection_interval": str(ref_config["cycle_interval"]),
        "prediction_error_threshold": str(ref_config["prediction_error_threshold"]),
    })

    result_raw = call_llm(system, user)
    # Parse JSON from the response (keeping simple one-shot parsing for this gate)
    pattern = r'```(?:json)?\s*\n(.*?)\n```'
    match = re.search(pattern, result_raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(result_raw)
    except (json.JSONDecodeError, ValueError):
        return {"should_reflect": False, "triggers": []}


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


def run_reflection_loop(triggers: list[str] | None = None) -> dict:
    """Run the reflection loop: REVIEW -> ASK -> PREDICT -> EVOLVE.

    Each step is a separate call. The kernel controls step sequencing —
    the LLM gets tools appropriate to each step but cannot skip steps.
    PREDICT uses call_llm (no tools, pure counterfactual reasoning).

    Returns dict with review text, proposals text, predictions, and changes.
    """
    from kernel.soul import compact_soul
    compact_soul()

    trigger_list = triggers or ["explicit"]

    # --- REVIEW ---
    _log("REVIEW ...")
    review_result = _run_agentic_step("review", {
        "triggers": ", ".join(trigger_list),
    })
    review_text = review_result.text

    data.append_memory(data.make_memory(
        author="kernel",
        weight=0.5,
        situation="reflection",
        description=f"REVIEW: {review_text}",
    ))

    # --- ASK ---
    _log("ASK ...")
    ask_result = _run_agentic_step("ask", {
        "review": review_text,
    })
    proposals_text = ask_result.text

    data.append_memory(data.make_memory(
        author="kernel",
        weight=0.5,
        situation="reflection",
        description=f"ASK: {proposals_text}",
    ))

    if not proposals_text.strip():
        data.append_memory(data.make_memory(
            author="self",
            weight=0.6,
            situation="reflection",
            description="Reflection complete — no changes proposed. Current values and goals feel aligned.",
        ))
        return {"review": review_text, "proposals": "", "predictions": "", "changes": []}

    # --- PREDICT ---
    _log("PREDICT ...")
    system, user = load_prompt("reflect_predict", {
        "proposals_output": proposals_text,
    })
    predictions_text = call_llm(system, user)

    data.append_memory(data.make_memory(
        author="kernel",
        weight=0.5,
        situation="reflection",
        description=f"PREDICT: {predictions_text}",
    ))

    # --- EVOLVE ---
    _log("EVOLVE ...")
    evolve_result = _run_agentic_step("evolve", {
        "proposals": predictions_text,
    })

    # Extract changes from tool calls for return value
    changes = []
    for tc in evolve_result.tool_calls_made:
        if tc["name"] in ("update_value", "update_goal", "write_soul"):
            changes.append(tc["arguments"])

    data.append_memory(data.make_memory(
        author="kernel",
        weight=0.5,
        situation="reflection",
        description=f"EVOLVE: {len(changes)} changes — {evolve_result.text}",
    ))

    return {
        "review": review_text,
        "proposals": proposals_text,
        "predictions": predictions_text,
        "changes": changes,
        "evolve_text": evolve_result.text,
    }
