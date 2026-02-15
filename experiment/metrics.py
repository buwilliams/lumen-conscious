"""Metric extraction from Lumen memory JSONL files.

Parses kernel-authored memories to extract prediction deltas, B=MAP scores,
reflection events, goal hygiene, value drift, and memory composition.
"""

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


@dataclass
class Delta:
    """A prediction delta from a RECORD kernel memory."""
    timestamp: str
    value: float


@dataclass
class BMAPScore:
    """A B=MAP score from a DECIDE kernel memory."""
    timestamp: str
    action: str
    m: float  # motivation
    a: float  # ability
    p: float  # prompt
    b: float  # composite


@dataclass
class ReflectionEvent:
    """A reflection trigger (actual or suppressed)."""
    timestamp: str
    suppressed: bool
    triggers: list[str] = field(default_factory=list)


@dataclass
class Metrics:
    """All extracted metrics for one system."""
    deltas: list[Delta] = field(default_factory=list)
    bmap_scores: list[BMAPScore] = field(default_factory=list)
    reflections: list[ReflectionEvent] = field(default_factory=list)
    memory_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    memory_weights: list[tuple[str, float]] = field(default_factory=list)  # (timestamp, weight)
    goal_snapshots: list[dict] = field(default_factory=list)


def _read_all_memories(data_dir: Path) -> list[dict]:
    """Read all memory JSONL files from a data directory."""
    memory_dir = data_dir / "memory"
    if not memory_dir.exists():
        return []
    memories = []
    for jsonl in sorted(memory_dir.rglob("*.jsonl")):
        with open(jsonl) as f:
            for line in f:
                line = line.strip()
                if line:
                    memories.append(json.loads(line))
    return memories


def _read_goals(data_dir: Path) -> list[dict]:
    """Read all goal files from a data directory."""
    goals_dir = data_dir / "goals"
    if not goals_dir.exists():
        return []
    all_goals = []
    for gf in sorted(goals_dir.glob("*.json")):
        with open(gf) as f:
            all_goals.extend(json.load(f))
    return all_goals


def _read_values(data_dir: Path) -> list[dict]:
    """Read values from a data directory."""
    values_path = data_dir / "values.json"
    if not values_path.exists():
        return []
    with open(values_path) as f:
        return json.load(f)


# Regex patterns for kernel memory parsing
_DELTA_RE = re.compile(r"delta[=:]\s*(-?[\d.]+)", re.IGNORECASE)
_BMAP_RE = re.compile(
    r"M[=:]\s*([\d.]+).*?A[=:]\s*([\d.]+).*?P[=:]\s*([\d.]+).*?B[=:]\s*([\d.]+)",
    re.IGNORECASE,
)
_ACTION_RE = re.compile(r"action[=:]\s*['\"]?([^'\"]+?)['\"]?\s*(?:,|$)", re.IGNORECASE)


def extract_metrics(data_dir: Path) -> Metrics:
    """Extract all metrics from a Lumen data directory."""
    data_dir = Path(data_dir)
    memories = _read_all_memories(data_dir)
    metrics = Metrics()

    for mem in memories:
        author = mem.get("author", "")
        desc = mem.get("description", "")
        ts = mem.get("timestamp", "")
        weight = mem.get("weight", 0.0)
        situation = mem.get("situation", "")

        # Memory composition
        metrics.memory_counts[author] += 1
        metrics.memory_weights.append((ts, weight))

        if author != "kernel":
            continue

        # Prediction deltas (from RECORD step)
        if desc.startswith("RECORD:"):
            delta_match = _DELTA_RE.search(desc)
            if delta_match:
                metrics.deltas.append(Delta(
                    timestamp=ts,
                    value=float(delta_match.group(1)),
                ))

        # B=MAP scores (from DECIDE step)
        if desc.startswith("DECIDE:"):
            bmap_match = _BMAP_RE.search(desc)
            if bmap_match:
                action_match = _ACTION_RE.search(desc)
                metrics.bmap_scores.append(BMAPScore(
                    timestamp=ts,
                    action=action_match.group(1) if action_match else "unknown",
                    m=float(bmap_match.group(1)),
                    a=float(bmap_match.group(2)),
                    p=float(bmap_match.group(3)),
                    b=float(bmap_match.group(4)),
                ))

        # Reflection events
        if situation == "reflection-suppressed":
            triggers_match = re.search(r"triggers:\s*\[([^\]]*)\]", desc)
            trigger_list = []
            if triggers_match:
                trigger_list = [t.strip().strip("'\"") for t in triggers_match.group(1).split(",") if t.strip()]
            metrics.reflections.append(ReflectionEvent(
                timestamp=ts,
                suppressed=True,
                triggers=trigger_list,
            ))
        elif desc.startswith("REFLECT:") or desc.startswith("REVIEW:"):
            metrics.reflections.append(ReflectionEvent(
                timestamp=ts,
                suppressed=False,
            ))

    # Goal snapshots
    metrics.goal_snapshots = [{"source": "final", "goals": _read_goals(data_dir)}]

    return metrics


def extract_value_history(data_dir: Path) -> list[dict]:
    """Extract value weight changes from git history.

    Returns a list of snapshots: [{commit, timestamp, values: [{name, weight, status}]}]
    """
    import subprocess

    data_dir = Path(data_dir)
    values_path = data_dir / "values.json"
    if not values_path.exists():
        return []

    # Get git log for values.json
    try:
        result = subprocess.run(
            ["git", "log", "--format=%H %aI", "--follow", "--", str(values_path)],
            capture_output=True, text=True, cwd=data_dir.parent,
        )
        if result.returncode != 0:
            return [{"commit": "current", "timestamp": "", "values": _read_values(data_dir)}]
    except FileNotFoundError:
        return [{"commit": "current", "timestamp": "", "values": _read_values(data_dir)}]

    snapshots = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split(" ", 1)
        commit = parts[0]
        timestamp = parts[1] if len(parts) > 1 else ""
        try:
            show = subprocess.run(
                ["git", "show", f"{commit}:{values_path.relative_to(data_dir.parent)}"],
                capture_output=True, text=True, cwd=data_dir.parent,
            )
            if show.returncode == 0:
                values = json.loads(show.stdout)
                snapshots.append({"commit": commit[:8], "timestamp": timestamp, "values": values})
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            continue

    return list(reversed(snapshots))  # chronological order
