import re
from pathlib import Path


PROMPTS_DIR = Path(__file__).parent / "prompts"

# Steps where soul.md context would be noise (pure utility/analysis)
_SKIP_SOUL_STEPS = {"summarize", "memory_summarize", "history"}


def load_prompt(step: str, variables: dict) -> tuple[str, str]:
    """Load and render a prompt template pair.

    Returns (system_prompt, user_prompt) with {{variables}} replaced.
    Soul.md is automatically injected into system prompts unless the step
    is a pure utility step (summarize, memory_summarize, history).
    """
    from kernel import data

    step_dir = PROMPTS_DIR / step
    system_path = step_dir / "system.md"
    prompt_path = step_dir / "prompt.md"

    system = system_path.read_text()
    prompt = prompt_path.read_text()

    # Auto-populate soul and soul_compact variables for templates
    if step not in _SKIP_SOUL_STEPS:
        if "soul" not in variables:
            soul = data.read_soul()
            if soul:
                variables = {**variables, "soul": soul}
        if "soul_compact" not in variables:
            soul_compact = data.read_soul_compact()
            if soul_compact:
                # Strip the hash marker line
                lines = soul_compact.split("\n", 1)
                variables = {**variables, "soul_compact": lines[1] if len(lines) > 1 else soul_compact}

    system = _render(system, variables)
    prompt = _render(prompt, variables)

    return system, prompt


def _render(template: str, variables: dict) -> str:
    """Replace {{variable}} placeholders with values."""
    def replacer(match):
        key = match.group(1).strip()
        return str(variables.get(key, f"{{{{key}}}}"))
    return re.sub(r'\{\{(\s*\w+\s*)\}\}', replacer, template)
