"""Context compaction for long conversations and loop histories.

When context exceeds a character threshold, older turns are summarized
by the LLM into a compact summary. Recent turns stay verbatim. The
summary replaces the older turns so context stays bounded.
"""

import sys

from kernel.llm import call_llm


COMPACT_THRESHOLD = 12000  # Total chars before compaction triggers
RECENT_WINDOW = 6          # Number of recent turns to always keep verbatim


def compact_history(history: list[dict], prior_summary: str = "") -> tuple[list[dict], str]:
    """Compact conversation history if it exceeds the threshold.

    Args:
        history: List of {"role": "user"|"assistant", "content": "..."} dicts.
        prior_summary: Any existing summary from previous compactions.

    Returns:
        (compacted_history, summary) — the recent turns kept verbatim, and
        the updated summary covering everything before them.
    """
    total = sum(len(t["content"]) for t in history)
    if prior_summary:
        total += len(prior_summary)

    if total <= COMPACT_THRESHOLD:
        return history, prior_summary

    # Split: older turns to summarize, recent turns to keep
    if len(history) <= RECENT_WINDOW:
        return history, prior_summary

    older = history[:-RECENT_WINDOW]
    recent = history[-RECENT_WINDOW:]

    # Build the text to summarize
    lines = []
    if prior_summary:
        lines.append(f"Previous summary:\n{prior_summary}\n")
    for turn in older:
        role = "User" if turn["role"] == "user" else "Lumen"
        lines.append(f"{role}: {turn['content']}")
    text_to_summarize = "\n".join(lines)

    from kernel.log import dim
    dim("  [kernel] Compacting conversation history...")

    summary = call_llm(
        system=(
            "Summarize this conversation history into a concise summary. "
            "Preserve key facts, decisions, user requests, documents shared, "
            "and important context. Do not lose information that would be "
            "needed to continue the conversation coherently. "
            "Be thorough but concise."
        ),
        user=text_to_summarize,
    )

    return recent, summary


def format_history(history: list[dict], summary: str = "") -> str:
    """Format conversation history with optional compacted summary for prompt injection.

    Args:
        history: Recent turns (post-compaction).
        summary: Compacted summary of older turns, if any.

    Returns:
        Formatted string for inclusion in prompts.
    """
    if not history and not summary:
        return ""

    lines = ["\n**Conversation History:**"]

    if summary:
        lines.append(f"\n*Summary of earlier conversation:*\n{summary}\n")

    for turn in history:
        role = "User" if turn["role"] == "user" else "Lumen"
        lines.append(f"{role}: {turn['content']}")

    return "\n".join(lines)
