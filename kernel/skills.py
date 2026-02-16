import json
import os
import subprocess
from pathlib import Path

from kernel.config import load_config


def _build_skill_env(name: str) -> dict:
    """Build environment dict for a skill subprocess.

    Reads config.skills.<name>.api_key and passes it as <NAME>_API_KEY env var.
    For example, skills.search.api_key -> TAVILY_API_KEY (using default_backend).
    """
    env = os.environ.copy()
    # Remove parent project's venv so skills use their own isolated environments
    env.pop("VIRTUAL_ENV", None)
    config = load_config()
    skill_config = config.get("skills", {}).get(name, {})

    api_key = skill_config.get("api_key", "")
    if api_key:
        backend = skill_config.get("default_backend", name).upper()
        env[f"{backend}_API_KEY"] = api_key

    return env


def invoke_skill(name: str, input_data: str) -> str:
    """Run a skill as a subprocess. Communicates via stdin/stdout."""
    skill_dir = Path.cwd() / "skills" / name
    skill_main = skill_dir / "main.py"

    if not skill_main.exists():
        return json.dumps({"error": f"Skill '{name}' not found"})

    env = _build_skill_env(name)

    try:
        result = subprocess.run(
            ["uv", "run", "--directory", str(skill_dir), "python", "main.py"],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        if result.returncode != 0:
            return json.dumps({"error": result.stderr or f"Skill '{name}' failed"})
        return result.stdout
    except subprocess.TimeoutExpired:
        return json.dumps({"error": f"Skill '{name}' timed out"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def create_skill(name: str, description: str, code: str, dependencies: list[str] | None = None):
    """Create a new skill directory with the given code.

    This is the kernel's built-in skill authoring tool.
    """
    skill_dir = Path.cwd() / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)

    # Write main.py
    main_path = skill_dir / "main.py"
    main_path.write_text(code)

    # Write pyproject.toml with optional dependencies
    deps_str = ""
    if dependencies:
        deps_list = ", ".join(f'"{d}"' for d in dependencies)
        deps_str = f"dependencies = [{deps_list}]\n"

    pyproject = skill_dir / "pyproject.toml"
    pyproject.write_text(
        f'[project]\nname = "{name}"\nversion = "0.1.0"\n'
        f'requires-python = ">=3.10"\n'
        f'description = "{description}"\n'
        f'{deps_str}'
    )
