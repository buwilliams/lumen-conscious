import re
from pathlib import Path


PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(step: str, variables: dict) -> tuple[str, str]:
    """Load and render a prompt template pair.

    Returns (system_prompt, user_prompt) with {{variables}} replaced.
    """
    step_dir = PROMPTS_DIR / step
    system_path = step_dir / "system.md"
    prompt_path = step_dir / "prompt.md"

    system = system_path.read_text()
    prompt = prompt_path.read_text()

    system = _render(system, variables)
    prompt = _render(prompt, variables)

    return system, prompt


def _render(template: str, variables: dict) -> str:
    """Replace {{variable}} placeholders with values."""
    def replacer(match):
        key = match.group(1).strip()
        return str(variables.get(key, f"{{{{key}}}}"))
    return re.sub(r'\{\{(\s*\w+\s*)\}\}', replacer, template)
