"""Event recording and replay for the reflexivity ablation experiment.

EventRecorder appends events during System A's run.
EventReplayer reads them back for System B's deterministic replay.
"""

import json
from datetime import datetime
from pathlib import Path


class EventRecorder:
    """Appends experiment events to a JSONL file."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._seq = 0

    def record(self, event_type: str, data: dict | None = None):
        """Append an event to the log."""
        self._seq += 1
        event = {
            "seq": self._seq,
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "data": data or {},
        }
        with open(self.path, "a") as f:
            f.write(json.dumps(event) + "\n")

    def trio_start(self, trio: int):
        self.record("trio_start", {"trio": trio})

    def trio_end(self, trio: int):
        self.record("trio_end", {"trio": trio})

    def action_situation(self, situation: str):
        self.record("action_situation", {"situation": situation})

    def explore_output(self, question: str, prediction: str, text: str):
        self.record("explore_output", {
            "question": question,
            "prediction": prediction,
            "text": text,
        })

    def chat_input(self, user_input: str):
        self.record("chat_input", {"user_input": user_input})


class EventReplayer:
    """Reads a recorded event log for deterministic replay."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._events: list[dict] = []
        self._index: dict[str, list[dict]] = {}
        self._cursors: dict[str, int] = {}
        self._load()

    def _load(self):
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                event = json.loads(line)
                self._events.append(event)
                et = event["event_type"]
                self._index.setdefault(et, []).append(event)

    def next(self, event_type: str) -> dict | None:
        """Get the next event of a given type, advancing the cursor."""
        cursor = self._cursors.get(event_type, 0)
        events = self._index.get(event_type, [])
        if cursor >= len(events):
            return None
        event = events[cursor]
        self._cursors[event_type] = cursor + 1
        return event["data"]

    def peek(self, event_type: str) -> dict | None:
        """Peek at the next event without advancing."""
        cursor = self._cursors.get(event_type, 0)
        events = self._index.get(event_type, [])
        if cursor >= len(events):
            return None
        return events[cursor]["data"]

    def has_more(self, event_type: str) -> bool:
        cursor = self._cursors.get(event_type, 0)
        return cursor < len(self._index.get(event_type, []))

    @property
    def total_trios(self) -> int:
        return len(self._index.get("trio_start", []))
