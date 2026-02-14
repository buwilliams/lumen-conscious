import json
import subprocess
from pathlib import Path


def invoke_skill(name: str, input_data: str) -> str:
    """Run a skill as a subprocess. Communicates via stdin/stdout."""
    skill_dir = Path.cwd() / "skills" / name
    skill_main = skill_dir / "main.py"

    if not skill_main.exists():
        return json.dumps({"error": f"Skill '{name}' not found"})

    try:
        result = subprocess.run(
            ["uv", "run", "--directory", str(skill_dir), "python", "main.py"],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            return json.dumps({"error": result.stderr or f"Skill '{name}' failed"})
        return result.stdout
    except subprocess.TimeoutExpired:
        return json.dumps({"error": f"Skill '{name}' timed out"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def create_skill(name: str, description: str, code: str):
    """Create a new skill directory with the given code.

    This is the kernel's built-in skill authoring tool.
    """
    skill_dir = Path.cwd() / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)

    # Write main.py
    main_path = skill_dir / "main.py"
    main_path.write_text(code)

    # Write a minimal pyproject.toml
    pyproject = skill_dir / "pyproject.toml"
    pyproject.write_text(
        f'[project]\nname = "{name}"\nversion = "0.1.0"\n'
        f'description = "{description}"\n'
    )
