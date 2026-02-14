import json
import sys

from kernel import data, memory, skills
from kernel.config import load_config
from kernel.llm import call_llm, extract_json
from kernel.prompts import load_prompt


def _log(msg: str):
    """Print a kernel progress message to stderr."""
    print(f"  [kernel] {msg}", file=sys.stderr, flush=True)


def format_values(values: list[data.Value]) -> str:
    return "\n".join(f"- {v.name} (weight: {v.weight}, status: {v.status})" for v in values)


def format_goals(goals: list[data.Goal]) -> str:
    return "\n".join(f"- {g.name} (weight: {g.weight}, status: {g.status})" for g in goals)


def format_memories(memories: list[data.Memory]) -> str:
    if not memories:
        return "(no memories yet)"
    lines = []
    for m in memories:
        lines.append(f"- [{m.timestamp}] ({m.author}) {m.description}")
    return "\n".join(lines)


def format_skills(skill_names: list[str]) -> str:
    if not skill_names:
        return "- respond (built-in: generate a direct response)"
    lines = ["- respond (built-in: generate a direct response)"]
    for name in skill_names:
        lines.append(f"- {name}")
    return "\n".join(lines)


def run_action_loop(situation: str | None = None, conversation_history: str = "") -> dict:
    """Run the action loop: THINK → DECIDE → ACT → RECORD.

    Returns dict with keys: action, result, response, record, delta.
    """
    config = load_config()
    sit = situation or "No external trigger. Internal cycle."

    # Load state
    soul = data.read_soul()
    values = data.read_values()
    goals = data.read_active_goals()
    mems = memory.retrieve_memories(config["memory"]["retrieve_count"])
    skill_names = data.list_skills()

    # --- THINK ---
    _log("THINK ...")
    system, user = load_prompt("think", {
        "soul": soul,
        "values": format_values(values),
        "goals": format_goals(goals),
        "memories": format_memories(mems),
        "situation": sit,
        "conversation_history": conversation_history,
    })
    think_raw = call_llm(system, user)
    think_result = extract_json(think_raw) or {"analysis": think_raw, "candidates": []}

    data.append_memory(data.make_memory(
        author="kernel",
        weight=0.5,
        situation=sit,
        description=f"THINK: {json.dumps(think_result.get('analysis', ''))}",
    ))

    candidates = think_result.get("candidates", [])
    if not candidates:
        # Fallback: treat the whole response as a single candidate
        candidates = [{
            "action": "respond to the situation",
            "skill": "respond",
            "values": [v.name for v in values],
            "goals": [g.name for g in goals],
            "prediction": "provide a helpful response",
            "response": think_raw,
        }]

    # --- DECIDE ---
    _log("DECIDE ...")
    system, user = load_prompt("decide", {
        "candidates": json.dumps(candidates, indent=2),
        "values": format_values(values),
        "goals": format_goals(goals),
        "skills": format_skills(skill_names),
    })
    decide_raw = call_llm(system, user)
    decide_result = extract_json(decide_raw) or {}

    selected = decide_result.get("selected", candidates[0])
    scores = decide_result.get("scores", [])

    data.append_memory(data.make_memory(
        author="kernel",
        weight=0.5,
        situation=sit,
        description=f"DECIDE: selected={json.dumps(selected.get('action', ''))} scores={json.dumps(scores)}",
    ))

    # Check motivation threshold
    top_score = max((s.get("B", 0) for s in scores), default=1.0) if scores else 1.0
    if top_score < config["motivation_threshold"]:
        data.append_memory(data.make_memory(
            author="kernel",
            weight=0.3,
            situation=sit,
            description=f"DECIDE: Skipped — motivation too low (B={top_score})",
        ))
        return {"action": "skip", "result": None, "response": None, "record": None, "delta": 0.0}

    # --- ACT ---
    _log(f"ACT (skill: {selected.get('skill', 'respond')}) ...")
    skill_name = selected.get("skill", "respond")
    result = None
    response = None

    if skill_name == "respond":
        # Direct response — use the response from THINK/DECIDE
        response = selected.get("response", "")
        if not response:
            # Fallback: use the first candidate's response
            response = candidates[0].get("response", think_raw)
        result = response
    else:
        # Invoke external skill
        skill_input = selected.get("input", json.dumps({"situation": sit}))
        result = skills.invoke_skill(skill_name, skill_input)
        response = result

    data.append_memory(data.make_memory(
        author="kernel",
        weight=0.5,
        situation=sit,
        description=f"ACT: skill={skill_name} result_length={len(str(result))}",
    ))

    # --- RECORD ---
    _log("RECORD ...")
    prediction = selected.get("prediction", "")
    system, user = load_prompt("record", {
        "situation": sit,
        "prediction": prediction,
        "outcome": str(result)[:2000],
    })
    record_raw = call_llm(system, user)
    record_result = extract_json(record_raw) or {}
    delta = record_result.get("delta", 0.0)

    data.append_memory(data.make_memory(
        author="kernel",
        weight=0.5,
        situation=sit,
        description=f"RECORD: delta={delta} {json.dumps(record_result.get('delta_description', ''))}",
    ))

    return {
        "action": selected.get("action", ""),
        "result": result,
        "response": response,
        "record": record_result,
        "delta": delta,
    }


def run_explore_loop() -> dict:
    """Run the explore loop: generate an open-ended question.

    Returns dict with keys: question, rationale, domain.
    """
    soul = data.read_soul()
    values = data.read_values()
    perpetual = data.read_perpetual_goals()
    mems = memory.retrieve_memories(10)

    system, user = load_prompt("explore", {
        "soul": soul,
        "values": format_values(values),
        "goals": format_goals(perpetual),
        "memories": format_memories(mems),
    })
    explore_raw = call_llm(system, user)
    explore_result = extract_json(explore_raw) or {"question": explore_raw}

    # Record the question as self memory
    data.append_memory(data.make_memory(
        author="self",
        weight=0.6,
        situation="explore loop",
        description=f"Question: {explore_result.get('question', explore_raw)}",
    ))

    # Record mechanics as kernel memory
    data.append_memory(data.make_memory(
        author="kernel",
        weight=0.4,
        situation="explore loop",
        description=f"EXPLORE: domain={explore_result.get('domain', 'unknown')} rationale={explore_result.get('rationale', '')}",
    ))

    return explore_result
