import json
from datetime import datetime

from kernel import data, memory
from kernel.config import load_config
from kernel.llm import call_llm, extract_json
from kernel.prompts import load_prompt
from kernel.loops import format_values, format_goals, format_memories


def should_reflect(cycles_since_reflection: int, recent_deltas: list[float] | None = None) -> dict:
    """Evaluate whether to enter the reflection loop.

    Returns dict with should_reflect bool and triggers list.
    """
    config = load_config()
    ref_config = config["reflection"]
    mems = memory.retrieve_memories(ref_config.get("staleness_cycles", 10) * 4)

    # Format deltas
    deltas_str = "(none)"
    if recent_deltas:
        deltas_str = "\n".join(f"- delta={d}" for d in recent_deltas)

    system, user = load_prompt("trigger", {
        "memories": format_memories(mems),
        "deltas": deltas_str,
        "cycles_since_reflection": str(cycles_since_reflection),
        "reflection_interval": str(ref_config["cycle_interval"]),
        "delta_threshold": str(ref_config["prediction_delta_threshold"]),
    })

    result_raw = call_llm(system, user)
    result = extract_json(result_raw) or {"should_reflect": False, "triggers": []}

    return result


def run_reflection_loop(triggers: list[str] | None = None) -> dict:
    """Run the reflection loop: REVIEW → ASK → EVOLVE.

    Returns dict with review, proposals, and changes applied.
    """
    trigger_list = triggers or ["explicit"]

    soul = data.read_soul()
    values = data.read_values()
    goals = data.read_goals()
    mems = memory.retrieve_non_kernel_memories(40)

    # --- REVIEW ---
    system, user = load_prompt("review", {
        "soul": soul,
        "values": format_values(values),
        "goals": format_goals(goals),
        "memories": format_memories(mems),
        "triggers": ", ".join(trigger_list),
    })
    review_raw = call_llm(system, user)
    review_result = extract_json(review_raw) or {"summary": review_raw}

    data.append_memory(data.make_memory(
        author="kernel",
        weight=0.5,
        situation="reflection",
        description=f"REVIEW: triggers={trigger_list} summary_length={len(review_result.get('summary', ''))}",
    ))

    # --- ASK ---
    system, user = load_prompt("ask", {
        "soul": soul,
        "values": format_values(values),
        "goals": format_goals(goals),
        "review": json.dumps(review_result, indent=2),
    })
    ask_raw = call_llm(system, user)
    ask_result = extract_json(ask_raw) or {"proposals": []}

    proposals = ask_result.get("proposals", [])

    data.append_memory(data.make_memory(
        author="kernel",
        weight=0.5,
        situation="reflection",
        description=f"ASK: {len(proposals)} proposals generated",
    ))

    if not proposals:
        data.append_memory(data.make_memory(
            author="self",
            weight=0.6,
            situation="reflection",
            description="Reflection complete — no changes proposed. Current values and goals feel aligned.",
        ))
        return {"review": review_result, "proposals": [], "changes": []}

    # --- EVOLVE ---
    system, user = load_prompt("evolve", {
        "soul": soul,
        "values": format_values(values),
        "goals": format_goals(goals),
        "proposals": json.dumps(proposals, indent=2),
    })
    evolve_raw = call_llm(system, user)
    evolve_result = extract_json(evolve_raw) or {"changes": []}

    changes = evolve_result.get("changes", [])
    conflicts = evolve_result.get("conflicts", [])

    # Apply changes
    _apply_changes(changes, values, goals, evolve_result.get("soul_update"))

    # Log each change
    for change in changes:
        data.append_memory(data.make_memory(
            author="self",
            weight=0.8,
            situation="reflection — evolve",
            description=f"Changed {change.get('type')}: {change.get('target')} → {change.get('new_value')}. Rationale: {change.get('rationale', '')}",
        ))

    data.append_memory(data.make_memory(
        author="kernel",
        weight=0.5,
        situation="reflection",
        description=f"EVOLVE: {len(changes)} changes applied, {len(conflicts)} conflicts resolved",
    ))

    return {"review": review_result, "proposals": proposals, "changes": changes, "conflicts": conflicts}


def _apply_changes(changes: list[dict], current_values: list[data.Value], current_goals: list[data.Goal], soul_update: str | None):
    """Apply evolved changes to data files."""
    year = datetime.now().year
    values_modified = False
    goals_modified = False

    for change in changes:
        change_type = change.get("type", "")
        target = change.get("target", "")
        new_value = change.get("new_value")

        if change_type == "reweight_value":
            for v in current_values:
                if v.name == target:
                    v.weight = float(new_value)
                    values_modified = True

        elif change_type == "deprecate_value":
            for v in current_values:
                if v.name == target:
                    v.status = "deprecated"
                    values_modified = True

        elif change_type == "add_value":
            current_values.append(data.Value(
                name=target,
                weight=float(new_value) if new_value else 0.5,
                status="active",
            ))
            values_modified = True

        elif change_type == "reweight_goal":
            for g in current_goals:
                if g.name == target:
                    g.weight = float(new_value)
                    goals_modified = True

        elif change_type == "change_goal_status":
            for g in current_goals:
                if g.name == target:
                    g.status = str(new_value)
                    goals_modified = True

        elif change_type == "add_goal":
            current_goals.append(data.Goal(
                name=target,
                weight=float(new_value) if new_value else 0.5,
                status="todo",
            ))
            goals_modified = True

        elif change_type == "update_soul" and soul_update:
            pass  # Handled below

    if values_modified:
        data.write_values(current_values)

    if goals_modified:
        data.write_goals(current_goals, year)

    if soul_update:
        data.write_soul(soul_update)
