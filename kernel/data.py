import json
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime, date
from pathlib import Path


DATA_DIR = Path.cwd() / "data"


# --- Type definitions ---

@dataclass
class Value:
    name: str
    weight: float
    status: str  # active | deprecated


@dataclass
class Goal:
    name: str
    weight: float
    status: str  # todo | working | done | perpetual


@dataclass
class Memory:
    timestamp: str
    author: str  # self | kernel | goal | external
    weight: float
    situation: str
    description: str


@dataclass
class ConversationTurn:
    role: str  # user | assistant
    content: str
    timestamp: str


# --- Soul ---

def read_soul() -> str:
    path = DATA_DIR / "soul.md"
    if not path.exists():
        return ""
    return path.read_text()


def write_soul(content: str):
    path = DATA_DIR / "soul.md"
    path.write_text(content)


# --- Values ---

def read_values() -> list[Value]:
    path = DATA_DIR / "values.json"
    if not path.exists():
        return []
    with open(path) as f:
        data = json.load(f)
    return [Value(**v) for v in data]


def write_values(values: list[Value]):
    path = DATA_DIR / "values.json"
    with open(path, "w") as f:
        json.dump([asdict(v) for v in values], f, indent=2)


# --- Goals ---

def _goals_path(year: int) -> Path:
    return DATA_DIR / "goals" / f"{year}.json"


def read_goals(year: int | None = None) -> list[Goal]:
    """Read goals. If year is None, read all years."""
    goals_dir = DATA_DIR / "goals"
    if not goals_dir.exists():
        return []

    if year is not None:
        path = _goals_path(year)
        if not path.exists():
            return []
        with open(path) as f:
            data = json.load(f)
        return [Goal(**g) for g in data]

    # Read all years
    all_goals = []
    for path in sorted(goals_dir.glob("*.json")):
        with open(path) as f:
            data = json.load(f)
        all_goals.extend(Goal(**g) for g in data)
    return all_goals


def write_goals(goals: list[Goal], year: int):
    path = _goals_path(year)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump([asdict(g) for g in goals], f, indent=2)


def read_active_goals() -> list[Goal]:
    """Read goals with status todo, working, or perpetual."""
    return [g for g in read_goals() if g.status in ("todo", "working", "perpetual")]


def read_perpetual_goals() -> list[Goal]:
    return [g for g in read_goals() if g.status == "perpetual"]


def update_goal_status(name: str, new_status: str):
    """Update a goal's status. Searches all year files."""
    goals_dir = DATA_DIR / "goals"
    if not goals_dir.exists():
        return
    for path in goals_dir.glob("*.json"):
        with open(path) as f:
            data = json.load(f)
        modified = False
        for g in data:
            if g["name"] == name:
                g["status"] = new_status
                modified = True
        if modified:
            with open(path, "w") as f:
                json.dump(data, f, indent=2)


# --- Memory ---

def _memory_path(dt: date | None = None) -> Path:
    if dt is None:
        dt = date.today()
    return DATA_DIR / "memory" / str(dt.year) / f"{dt.isoformat()}.jsonl"


def append_memory(mem: Memory):
    path = _memory_path(date.fromisoformat(mem.timestamp[:10]))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(asdict(mem)) + "\n")


def make_memory(author: str, weight: float, situation: str, description: str) -> Memory:
    """Helper to create a memory with current timestamp."""
    return Memory(
        timestamp=datetime.now().isoformat(),
        author=author,
        weight=weight,
        situation=situation,
        description=description,
    )


def read_memories(author: str | None = None, dt: date | None = None, all_memories: bool = False) -> list[Memory]:
    """Read memories with optional filters."""
    memory_dir = DATA_DIR / "memory"
    if not memory_dir.exists():
        return []

    memories = []

    if dt is not None:
        # Specific date
        path = _memory_path(dt)
        if path.exists():
            memories = _read_jsonl(path)
    elif all_memories:
        # All memories across all years
        for year_dir in sorted(memory_dir.iterdir()):
            if year_dir.is_dir():
                for path in sorted(year_dir.glob("*.jsonl")):
                    memories.extend(_read_jsonl(path))
    else:
        # Default: recent files
        memories = _read_recent_files(memory_dir, limit=100)

    if author:
        memories = [m for m in memories if m.author == author]

    return memories


def read_recent_memories(n: int = 20) -> list[Memory]:
    """Read the N most recent memories across all files."""
    memory_dir = DATA_DIR / "memory"
    if not memory_dir.exists():
        return []
    all_mems = _read_recent_files(memory_dir, limit=n * 2)
    all_mems.sort(key=lambda m: m.timestamp, reverse=True)
    return all_mems[:n]


def _read_jsonl(path: Path) -> list[Memory]:
    memories = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                memories.append(Memory(**json.loads(line)))
    return memories


def _read_recent_files(memory_dir: Path, limit: int) -> list[Memory]:
    """Read memories from the most recent JSONL files."""
    all_files = []
    for year_dir in memory_dir.iterdir():
        if year_dir.is_dir():
            all_files.extend(year_dir.glob("*.jsonl"))
    all_files.sort(reverse=True)

    memories = []
    for path in all_files:
        memories.extend(_read_jsonl(path))
        if len(memories) >= limit:
            break
    return memories


# --- Skills ---

def list_skills() -> list[str]:
    skills_dir = Path.cwd() / "skills"
    if not skills_dir.exists():
        return []
    return [
        d.name for d in sorted(skills_dir.iterdir())
        if d.is_dir() and (d / "main.py").exists()
    ]


def get_skill_help(name: str) -> str:
    skill_main = Path.cwd() / "skills" / name / "main.py"
    if not skill_main.exists():
        return f"Skill '{name}' not found."
    try:
        result = subprocess.run(
            ["python", str(skill_main), "--help"],
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout or result.stderr
    except Exception as e:
        return f"Error getting help for '{name}': {e}"


# --- Conversations ---

def _conversations_dir() -> Path:
    return DATA_DIR / "conversations"


def create_conversation(session_id: str):
    path = _conversations_dir() / f"{session_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


def append_turn(session_id: str, turn: ConversationTurn):
    path = _conversations_dir() / f"{session_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(asdict(turn)) + "\n")


def read_conversation(session_id: str) -> list[ConversationTurn]:
    path = _conversations_dir() / f"{session_id}.jsonl"
    if not path.exists():
        return []
    turns = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                turns.append(ConversationTurn(**json.loads(line)))
    return turns
