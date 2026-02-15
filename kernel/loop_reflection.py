import json
import re
import sys

from kernel import data, memory
from kernel.config import load_config
from kernel.llm import call_llm, run_agentic
from kernel.prompts import load_prompt
from kernel.tools import load_tools, check_required_tools


def _log(msg: str):
    """Print a kernel progress message to stderr."""
    print(f"  [kernel] {msg}", file=sys.stderr, flush=True)


def _format_memories(memories: list[data.Memory]) -> str:
    """Format memories for prompt inclusion."""
    if not memories:
        return "(no memories yet)"
    lines = []
    for m in memories:
        lines.append(f"- [{m.timestamp}] ({m.author}) {m.description}")
    return "\n".join(lines)


def should_reflect(cycles_since_reflection: int, recent_deltas: list[float] | None = None) -> dict:
    """Evaluate whether to enter the reflection loop.

    Returns dict with should_reflect bool and triggers list.
    Uses one-shot call_llm — this is a kernel gate, not an LLM action.
    """
    config = load_config()
    ref_config = config["reflection"]
    mems = memory.retrieve_memories(ref_config.get("staleness_cycles", 10) * 4)

    deltas_str = "(none)"
    if recent_deltas:
        deltas_str = "\n".join(f"- delta={d}" for d in recent_deltas)

    system, user = load_prompt("trigger", {
        "memories": _format_memories(mems),
        "deltas": deltas_str,
        "cycles_since_reflection": str(cycles_since_reflection),
        "reflection_interval": str(ref_config["cycle_interval"]),
        "delta_threshold": str(ref_config["prediction_delta_threshold"]),
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


def run_reflection_loop(triggers: list[str] | None = None) -> dict:
    """Run the reflection loop: REVIEW -> ASK -> EVOLVE.

    Each step is a separate run_agentic call. The kernel controls step
    sequencing — the LLM gets tools appropriate to each step but cannot
    skip steps.

    Returns dict with review text, proposals text, and tool calls made.
    """
    trigger_list = triggers or ["explicit"]

    # --- REVIEW ---
    _log("REVIEW ...")
    review_tools = load_tools("review")
    system, user = load_prompt("review", {
        "triggers": ", ".join(trigger_list),
    })

    review_result = run_agentic(system, user, review_tools)

    # Check required tools
    missing = check_required_tools("review", review_result.tool_calls_made)
    if missing:
        _log(f"REVIEW: missing required tools {missing}, retrying...")
        retry_user = user + f"\n\nYou must use the following tools: {', '.join(missing)}. Please try again."
        review_result = run_agentic(system, retry_user, review_tools)
        missing = check_required_tools("review", review_result.tool_calls_made)
        if missing:
            _log(f"REVIEW: still missing {missing} after retry, continuing...")

    review_text = review_result.text

    data.append_memory(data.make_memory(
        author="kernel",
        weight=0.5,
        situation="reflection",
        description=f"REVIEW: triggers={trigger_list} tools_used={len(review_result.tool_calls_made)} iterations={review_result.iterations}",
    ))

    # --- ASK ---
    _log("ASK ...")
    ask_tools = load_tools("ask")
    system, user = load_prompt("ask", {
        "review": review_text,
    })

    ask_result = run_agentic(system, user, ask_tools)
    proposals_text = ask_result.text

    data.append_memory(data.make_memory(
        author="kernel",
        weight=0.5,
        situation="reflection",
        description=f"ASK: tools_used={len(ask_result.tool_calls_made)} iterations={ask_result.iterations}",
    ))

    if not proposals_text.strip():
        data.append_memory(data.make_memory(
            author="self",
            weight=0.6,
            situation="reflection",
            description="Reflection complete — no changes proposed. Current values and goals feel aligned.",
        ))
        return {"review": review_text, "proposals": "", "changes": []}

    # --- EVOLVE ---
    _log("EVOLVE ...")
    evolve_tools = load_tools("evolve")
    system, user = load_prompt("evolve", {
        "proposals": proposals_text,
    })

    evolve_result = run_agentic(system, user, evolve_tools)

    # Check required tools
    missing = check_required_tools("evolve", evolve_result.tool_calls_made)
    if missing:
        _log(f"EVOLVE: missing required tools {missing}, retrying...")
        retry_user = user + f"\n\nYou must use the following tools: {', '.join(missing)}. Please try again."
        evolve_result = run_agentic(system, retry_user, evolve_tools)
        missing = check_required_tools("evolve", evolve_result.tool_calls_made)
        if missing:
            _log(f"EVOLVE: still missing {missing} after retry, continuing...")

    # Extract changes from tool calls for return value
    changes = []
    for tc in evolve_result.tool_calls_made:
        if tc["name"] in ("update_value", "update_goal", "write_soul"):
            changes.append(tc["arguments"])

    data.append_memory(data.make_memory(
        author="kernel",
        weight=0.5,
        situation="reflection",
        description=f"EVOLVE: {len(changes)} changes applied, tools_used={len(evolve_result.tool_calls_made)} iterations={evolve_result.iterations}",
    ))

    return {
        "review": review_text,
        "proposals": proposals_text,
        "changes": changes,
        "evolve_text": evolve_result.text,
    }
