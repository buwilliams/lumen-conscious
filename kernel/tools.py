import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Callable

from kernel import data, memory, skills
from kernel.config import load_config

# --- Ablation Mode ---
_ABLATION_MODE = False


def set_ablation_mode(enabled: bool):
    """Enable or disable ablation mode (suppresses reflection)."""
    global _ABLATION_MODE
    _ABLATION_MODE = enabled


@dataclass
class Tool:
    """A tool that the LLM can invoke during an agentic step."""
    name: str
    description: str
    parameters: dict
    handler: Callable

    def schema(self) -> dict:
        """Return the Anthropic tool-use schema."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }

    def execute(self, arguments: dict) -> str:
        """Execute the tool handler and return a string result."""
        result = self.handler(**arguments)
        if isinstance(result, str):
            return result
        return json.dumps(result, indent=2)


# --- Tool Handlers ---

def handle_read_soul() -> str:
    return data.read_soul() or "(no soul defined yet)"


def handle_read_values() -> str:
    values = data.read_values()
    active = [v for v in values if v.status != "deprecated"]
    if not active:
        return "(no values defined)"
    return json.dumps([asdict(v) for v in active], indent=2)


def handle_read_goals(status: str | None = None) -> str:
    goals = data.read_goals()
    if status:
        goals = [g for g in goals if g.status == status]
    else:
        goals = [g for g in goals if g.status not in ("deprecated", "done")]
    if not goals:
        return "(no goals found)"
    return json.dumps([asdict(g) for g in goals], indent=2)


MAX_TOOL_OUTPUT = 30000  # Total char budget for memory tool output


def _format_memories(mems: list, max_chars: int = MAX_TOOL_OUTPUT) -> str:
    """Format memories into a string, stopping when the char budget is reached."""
    if not mems:
        return "(no memories found)"
    lines = []
    total = 0
    for m in mems:
        line = f"[{m.timestamp}] ({m.author}, w={m.weight}) {m.situation}: {m.description}"
        if total + len(line) > max_chars and lines:
            lines.append(f"(... {len(mems) - len(lines)} older memories omitted)")
            break
        lines.append(line)
        total += len(line)
    return "\n".join(lines)


def handle_read_memories(author: str | None = None, n: int = 20) -> str:
    if author and author != "kernel":
        mems = memory.retrieve_non_kernel_memories(n)
        mems = [m for m in mems if m.author == author]
    elif author == "kernel":
        mems = memory.retrieve_memories(n)
        mems = [m for m in mems if m.author == "kernel"]
    else:
        mems = memory.retrieve_memories(n)
    return _format_memories(mems)


def handle_read_memories_non_kernel(n: int = 40) -> str:
    """Read memories excluding kernel-authored ones (for reflection steps)."""
    mems = memory.retrieve_non_kernel_memories(n)
    return _format_memories(mems)


def handle_list_skills() -> str:
    skill_names = data.list_skills()
    lines = ["- respond (built-in: generate a direct response)"]
    for name in skill_names:
        help_text = data.get_skill_help(name)
        lines.append(f"- {name}: {help_text.strip()[:200]}")
    if len(lines) == 1:
        lines.append("(no custom skills installed)")
    return "\n".join(lines)


def handle_write_soul(content: str) -> str:
    data.write_soul(content)
    return "Soul updated successfully."


def handle_update_value(name: str, weight: float | None = None, status: str | None = None,
                        description: str | None = None, origin: str | None = None,
                        tags: list[str] | None = None, tensions: str | None = None,
                        conditions: str | None = None, counterexamples: str | None = None) -> str:
    values = data.read_values()
    found = False
    for v in values:
        if v.name == name:
            if weight is not None:
                v.weight = float(weight)
            if status is not None:
                v.status = status
            if description is not None:
                v.description = description
            if origin is not None:
                v.origin = origin
            if tags is not None:
                v.tags = tags
            if tensions is not None:
                v.tensions = tensions
            if conditions is not None:
                v.conditions = conditions
            if counterexamples is not None:
                v.counterexamples = counterexamples
            found = True
            break

    if not found:
        # Add new value
        values.append(data.Value(
            name=name,
            weight=float(weight) if weight is not None else 0.5,
            status=status or "active",
            description=description or "",
            origin=origin or "",
            tags=tags or [],
            tensions=tensions or "",
            conditions=conditions or "",
            counterexamples=counterexamples or "",
        ))

    data.write_values(values)
    return f"Value '{name}' updated." if found else f"Value '{name}' added."


def handle_update_goal(name: str, weight: float | None = None, status: str | None = None) -> str:
    goals = data.read_goals()
    year = datetime.now().year
    found = False
    for g in goals:
        if g.name == name:
            if weight is not None:
                g.weight = float(weight)
            if status is not None:
                g.status = status
            found = True
            break

    if not found:
        goals.append(data.Goal(
            name=name,
            weight=float(weight) if weight is not None else 0.5,
            status=status or "todo",
        ))

    data.write_goals(goals, year)
    return f"Goal '{name}' updated." if found else f"Goal '{name}' added."


def handle_update_goal_status(name: str, status: str) -> str:
    data.update_goal_status(name, status)
    return f"Goal '{name}' status changed to '{status}'."


def handle_invoke_skill(name: str, input_data: str = "") -> str:
    return skills.invoke_skill(name, input_data)


def handle_create_skill(name: str, description: str, code: str) -> str:
    skills.create_skill(name, description, code)
    return f"Skill '{name}' created successfully."


def handle_record_memory(description: str, situation: str = "", weight: float = 0.6) -> str:
    data.append_memory(data.make_memory(
        author="self",
        weight=weight,
        situation=situation,
        description=description,
    ))
    return "Memory recorded."


def handle_reflect(triggers: list[str] | None = None) -> str:
    """Meta-tool: trigger the reflection loop from chat."""
    if _ABLATION_MODE:
        data.append_memory(data.make_memory(
            author="kernel",
            weight=0.3,
            situation="reflection-suppressed",
            description=f"REFLECT: suppressed by ablation mode (triggers: {triggers or ['chat-requested']})",
        ))
        return "Reflection suppressed (ablation mode active)."

    from kernel.loop_reflection import run_reflection_loop
    trigger_list = triggers or ["chat-requested"]
    result = run_reflection_loop(trigger_list)
    changes = result.get("changes", [])
    if not changes:
        summary = "Reflection complete. No changes proposed — current values and goals feel aligned."
    else:
        change_lines = []
        for c in changes:
            change_lines.append(f"- {c.get('type')}: {c.get('target')} -> {c.get('new_value')}")
        summary = f"Reflection complete. {len(changes)} changes applied:\n" + "\n".join(change_lines)
    review = result.get("review", {})
    if isinstance(review, dict) and review.get("summary"):
        summary = f"Review: {review['summary'][:500]}\n\n{summary}"
    return summary


# --- Tool Registry ---

TOOL_REGISTRY: dict[str, Tool] = {}


def _register(name: str, description: str, parameters: dict, handler: Callable):
    TOOL_REGISTRY[name] = Tool(name=name, description=description, parameters=parameters, handler=handler)


# Read tools
_register("read_soul", "Read the system's identity narrative (soul.md).", {
    "type": "object", "properties": {}, "required": [],
}, handle_read_soul)

_register("read_values", "Read the system's current values with all fields: name, weight, status, description, origin, tags, tensions, conditions, and counterexamples.", {
    "type": "object", "properties": {}, "required": [],
}, handle_read_values)

_register("read_goals", "Read the system's current goals. Optionally filter by status.", {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["todo", "working", "done", "perpetual"],
                    "description": "Filter goals by status."},
    },
    "required": [],
}, handle_read_goals)

_register("read_memories", "Read recent memories. Returns memories with timestamps, authors, and descriptions.", {
    "type": "object",
    "properties": {
        "author": {"type": "string", "enum": ["self", "kernel", "goal", "external"],
                    "description": "Filter memories by author."},
        "n": {"type": "integer", "description": "Number of memories to retrieve (default: 20)."},
    },
    "required": [],
}, handle_read_memories)

_register("list_skills", "List all available skills with their descriptions.", {
    "type": "object", "properties": {}, "required": [],
}, handle_list_skills)

# Reflection write tools
_register("write_soul", "Update the system's identity narrative (soul.md). Provide the complete new text.", {
    "type": "object",
    "properties": {
        "content": {"type": "string", "description": "The complete new soul.md content."},
    },
    "required": ["content"],
}, handle_write_soul)

_register("update_value", "Update or add a value. Supports partial updates — only specified fields are changed. Values are rich representations carrying description, origin, tags, tensions, conditions, and counterexamples.", {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "The value name (short identifier)."},
        "weight": {"type": "number", "description": "Importance weight (0.0-1.0)."},
        "status": {"type": "string", "enum": ["active", "deprecated"], "description": "Value status."},
        "description": {"type": "string", "description": "What this value means — the belief/lesson/principle in first person."},
        "origin": {"type": "string", "description": "Experience or reasoning that gave rise to this value."},
        "tags": {"type": "array", "items": {"type": "string"}, "description": "Free-form tags: belief, lesson, principle, conjecture, ethic, moral, about-self, about-world, etc."},
        "tensions": {"type": "string", "description": "Known conflicts with other values or internal contradictions."},
        "conditions": {"type": "string", "description": "When/where this value applies most strongly."},
        "counterexamples": {"type": "string", "description": "Cases where this value was challenged or needs nuance."},
    },
    "required": ["name"],
}, handle_update_value)

_register("update_goal", "Update or add a goal. For existing goals, updates weight and/or status. For new goals, creates them.", {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "The goal name."},
        "weight": {"type": "number", "description": "New weight (0.0-1.0)."},
        "status": {"type": "string", "enum": ["todo", "working", "done", "perpetual", "deprecated"], "description": "New status."},
    },
    "required": ["name"],
}, handle_update_goal)

# Action write tools
_register("update_goal_status", "Change a goal's status (e.g., todo -> working -> done).", {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "The goal name."},
        "status": {"type": "string", "enum": ["todo", "working", "done"], "description": "New status."},
    },
    "required": ["name", "status"],
}, handle_update_goal_status)

_register("invoke_skill", "Invoke a skill by name, passing input data via stdin.", {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "The skill name."},
        "input_data": {"type": "string", "description": "Input data to pass to the skill via stdin."},
    },
    "required": ["name"],
}, handle_invoke_skill)

_register("create_skill", "Create a new skill. Writes main.py and pyproject.toml in skills/<name>/.", {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "The skill name (directory name)."},
        "description": {"type": "string", "description": "Short description of what the skill does."},
        "code": {"type": "string", "description": "Python code for main.py."},
    },
    "required": ["name", "description", "code"],
}, handle_create_skill)

# Memory tool
_register("record_memory", "Record a memory as author='self'. Use this to note observations, learnings, or reflections.", {
    "type": "object",
    "properties": {
        "description": {"type": "string", "description": "What to remember."},
        "situation": {"type": "string", "description": "Context/situation for this memory."},
        "weight": {"type": "number", "description": "Importance weight 0.0-1.0 (default: 0.6)."},
    },
    "required": ["description"],
}, handle_record_memory)

# Meta tool (chat only)
_register("reflect", "Trigger the reflection loop (REVIEW -> ASK -> EVOLVE). Use when the user guides self-examination or you want to reconsider values/goals.", {
    "type": "object",
    "properties": {
        "triggers": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Reasons for triggering reflection.",
        },
    },
    "required": [],
}, handle_reflect)


def load_tools(step: str) -> list[Tool]:
    """Load the tools permitted for a given step, based on config."""
    config = load_config()
    step_config = config.get("tools", {}).get("steps", {}).get(step, {})
    tool_names = step_config.get("tools", [])

    loaded = []
    for name in tool_names:
        if name == "read_memories":
            # Always use non-kernel variant — kernel memories are audit trail, not cognition
            loaded.append(Tool(
                name="read_memories",
                description="Read recent memories (excluding kernel-authored audit trail).",
                parameters=TOOL_REGISTRY["read_memories"].parameters,
                handler=handle_read_memories_non_kernel,
            ))
        elif name in TOOL_REGISTRY:
            loaded.append(TOOL_REGISTRY[name])
        else:
            print(f"  [warning] Unknown tool '{name}' in config for step '{step}'", file=sys.stderr)

    return loaded


def get_required_tools(step: str) -> list[str]:
    """Get the list of required tool names for a step."""
    config = load_config()
    step_config = config.get("tools", {}).get("steps", {}).get(step, {})
    return step_config.get("required", [])


def check_required_tools(step: str, tool_calls_made: list[dict]) -> list[str]:
    """Check which required tools were NOT called. Returns list of missing tool names."""
    required = get_required_tools(step)
    called = {tc["name"] for tc in tool_calls_made}
    return [name for name in required if name not in called]
