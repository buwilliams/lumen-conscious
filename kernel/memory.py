from kernel.data import read_recent_memories, Memory


def summarize_description(description: str) -> str:
    """Summarize a memory description into key bullet points."""
    if len(description) < 100:
        return description

    from kernel.llm import call_llm_summary
    from kernel.prompts import load_prompt
    system, user = load_prompt("memory_summarize", {"description": description})
    return call_llm_summary(system, user)


def retrieve_memories(n: int = 20) -> list[Memory]:
    """Retrieve the most relevant memories.

    Currently recency-only. Semantic retrieval (embedding search)
    will be added as a fast-follow once loops are working.
    """
    return read_recent_memories(n)


def retrieve_non_kernel_memories(n: int = 40) -> list[Memory]:
    """Retrieve recent memories excluding kernel-authored ones.

    Used by the reflection loop — kernel memories are below consciousness.
    """
    memories = read_recent_memories(n * 2)
    filtered = [m for m in memories if m.author != "kernel"]
    return filtered[:n]
