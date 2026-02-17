"""Soul compaction — summarize soul.md into a compact system prompt preamble."""

from kernel import data
from kernel.llm import call_llm
from kernel.log import dim


def compact_soul():
    """Read soul.md, summarize it into a compact identity preamble, and save it.

    Called at the start of each loop so templates can use {{soul_compact}}.
    Skips if soul.md hasn't changed since the last compaction.
    """
    soul = data.read_soul()
    if not soul:
        return

    existing = data.read_soul_compact()

    # Skip if soul hasn't changed (check by comparing soul hash stored in first line)
    import hashlib
    soul_hash = hashlib.md5(soul.encode()).hexdigest()[:12]
    marker = f"<!-- soul:{soul_hash} -->"
    if existing.startswith(marker):
        return

    dim("  [kernel] compacting soul.md for system prompts")

    compact = call_llm(
        system=(
            "Compress the following identity document into a concise system prompt preamble "
            "(3-5 sentences max). Preserve: the system's name, core identity, key values with "
            "current weights, active capabilities, and any critical open questions. "
            "Write in first person. Do not add commentary — just the compressed identity."
        ),
        user=soul,
    )

    data.write_soul_compact(f"{marker}\n{compact}")
