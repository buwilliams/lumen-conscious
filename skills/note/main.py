#!/usr/bin/env python3
"""Simple key-value note storage — append, list, read.

Usage:
  echo '{"action": "append", "key": "mykey", "value": "some text"}' | python main.py
  echo '{"action": "read", "key": "mykey"}' | python main.py
  echo '{"action": "list"}' | python main.py
  python main.py --help

Input (JSON via stdin):
  action - "append", "read", or "list" (required)
  key    - Note key/name (required for append/read)
  value  - Note content (required for append)

Output (JSON to stdout):
  For append: {"status": "ok", "key": "...", "entries": N}
  For read:   {"key": "...", "entries": ["...", ...]}
  For list:   {"keys": ["...", ...], "count": N}
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone


NOTES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notes.json")


def load_notes():
    if os.path.exists(NOTES_FILE):
        try:
            with open(NOTES_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_notes(notes):
    with open(NOTES_FILE, "w") as f:
        json.dump(notes, f, indent=2)


def append_note(notes, key, value):
    if key not in notes:
        notes[key] = []
    entry = {
        "value": value,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    notes[key].append(entry)
    save_notes(notes)
    return {"status": "ok", "key": key, "entries": len(notes[key])}


def read_note(notes, key):
    if key not in notes:
        return {"error": f"No note found with key '{key}'"}
    entries = [e["value"] for e in notes[key]]
    timestamps = [e["timestamp"] for e in notes[key]]
    return {
        "key": key,
        "entries": entries,
        "timestamps": timestamps,
        "count": len(entries)
    }


def list_notes(notes):
    keys = list(notes.keys())
    summary = {k: len(v) for k, v in notes.items()}
    return {"keys": keys, "count": len(keys), "summary": summary}


def main():
    parser = argparse.ArgumentParser(description="Simple key-value note storage. Append, list, read.")
    parser.add_argument("input", nargs="?", default=None,
                        help="JSON input (also accepts stdin)")
    args = parser.parse_args()

    raw = args.input
    if raw is None:
        if not sys.stdin.isatty():
            raw = sys.stdin.read().strip()
        else:
            parser.print_help()
            sys.exit(1)

    if not raw:
        print(json.dumps({"error": "No input provided"}))
        sys.exit(1)

    try:
        params = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: treat plain text as a quick append to "scratch"
        params = {"action": "append", "key": "scratch", "value": raw}

    action = params.get("action", "").lower()
    notes = load_notes()

    if action == "append":
        key = params.get("key")
        value = params.get("value")
        if not key or not value:
            print(json.dumps({"error": "append requires 'key' and 'value'"}))
            sys.exit(1)
        result = append_note(notes, key, value)

    elif action == "read":
        key = params.get("key")
        if not key:
            print(json.dumps({"error": "read requires 'key'"}))
            sys.exit(1)
        result = read_note(notes, key)

    elif action == "list":
        result = list_notes(notes)

    elif action == "delete":
        key = params.get("key")
        if not key:
            print(json.dumps({"error": "delete requires 'key'"}))
            sys.exit(1)
        if key in notes:
            del notes[key]
            save_notes(notes)
            result = {"status": "ok", "deleted": key}
        else:
            result = {"error": f"No note found with key '{key}'"}

    else:
        print(json.dumps({"error": f"Unknown action '{action}'. Use: append, read, list, delete"}))
        sys.exit(1)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
