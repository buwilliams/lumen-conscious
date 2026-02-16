import subprocess
from pathlib import Path

from kernel import data
from kernel.llm import call_llm
from kernel.prompts import load_prompt

MAX_DIFF_CHARS = 30000

# Files to track in history
TRACKED_FILES = ["soul.md", "values.json"]
TRACKED_GLOBS = ["goals/*.json"]


def _git_log_diffs(data_dir: Path) -> str:
    """Extract git log with diffs for tracked identity files."""
    parts = []

    targets = [str(data_dir / f) for f in TRACKED_FILES]
    # Expand goal globs
    goals_dir = data_dir / "goals"
    if goals_dir.exists():
        targets.extend(str(p) for p in goals_dir.glob("*.json"))

    if not targets:
        return "(no tracked files found)"

    try:
        result = subprocess.run(
            ["git", "log", "-p", "--follow", "--", *targets],
            capture_output=True, text=True, timeout=30,
        )
        output = result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return "(git log failed)"

    if not output:
        return "(no git history found)"

    # Truncate to fit LLM context
    if len(output) > MAX_DIFF_CHARS:
        output = output[:MAX_DIFF_CHARS] + "\n\n... (truncated)"

    return output


def generate_history(data_dir: Path | None = None) -> str:
    """Generate a narrative history of the instance's evolution using git diffs."""
    if data_dir is None:
        data_dir = data.DATA_DIR

    diff_text = _git_log_diffs(data_dir)
    if diff_text.startswith("("):
        return diff_text  # Error/empty case

    system, user = load_prompt("history", {"diffs": diff_text})
    return call_llm(system, user)
