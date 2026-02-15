import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

from kernel.config import load_config
from kernel.llm.base import ToolUseRequest, LLMResponse


@contextmanager
def _timer(label: str = ""):
    """Show an elapsed-seconds counter on stderr while waiting for the LLM."""
    stop = threading.Event()
    prefix = f"  [{label}] " if label else "  "

    def _tick():
        start = time.monotonic()
        while not stop.wait(1.0):
            elapsed = int(time.monotonic() - start)
            print(f"\r{prefix}{elapsed}s", end="", file=sys.stderr, flush=True)

    start = time.monotonic()
    t = threading.Thread(target=_tick, daemon=True)
    t.start()
    try:
        yield
    finally:
        stop.set()
        t.join(timeout=2.0)
        elapsed = time.monotonic() - start
        # Clear the counter line and print final time
        print(f"\r{prefix}{elapsed:.1f}s", file=sys.stderr, flush=True)


@dataclass
class AgenticResult:
    """Result from an agentic tool-use loop."""
    text: str = ""
    tool_calls_made: list[dict] = field(default_factory=list)
    iterations: int = 0


def call_llm(system: str, user: str) -> str:
    """Call the active LLM provider. Returns raw text."""
    config = load_config()
    provider_name = config["llm"]["provider"]
    model = config["llm"]["model"]
    provider = _get_provider(provider_name, config)
    with _timer("llm"):
        return provider.complete(system, user, model)


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Get embeddings using the configured embedding provider."""
    config = load_config()
    provider_name = config["embedding"]["provider"]
    model = config["embedding"]["model"]
    provider = _get_provider(provider_name, config)
    return provider.embed(texts, model)


def run_agentic(system: str, user: str, tools: list, max_iterations: int = 10) -> AgenticResult:
    """Run an agentic tool-use loop.

    Sends the system/user prompts with tool definitions to the LLM.
    If the LLM returns tool calls, executes each one, appends results
    to the conversation, and loops until the LLM stops calling tools
    or max_iterations is reached.

    Args:
        system: System prompt.
        user: User prompt.
        tools: List of Tool objects (from kernel.tools).
        max_iterations: Maximum number of LLM round-trips.

    Returns:
        AgenticResult with final text, tool call audit trail, and iteration count.
    """
    config = load_config()
    provider_name = config["llm"]["provider"]
    model = config["llm"]["model"]
    provider = _get_provider(provider_name, config)

    # Build tool schemas and handler lookup
    tool_schemas = [t.schema() for t in tools]
    tool_handlers = {t.name: t for t in tools}

    messages = [{"role": "user", "content": user}]
    all_tool_calls = []
    all_text = []

    for iteration in range(1, max_iterations + 1):
        with _timer("llm"):
            response = provider.complete_with_tools(system, messages, tool_schemas, model)

        # Accumulate text from every iteration
        if response.text:
            all_text.append(response.text)

        if not response.tool_calls:
            return AgenticResult(
                text="\n\n".join(all_text),
                tool_calls_made=all_tool_calls,
                iterations=iteration,
            )

        # Build the assistant message content blocks
        assistant_content = []
        if response.text:
            assistant_content.append({"type": "text", "text": response.text})
        for tc in response.tool_calls:
            assistant_content.append({
                "type": "tool_use",
                "id": tc.id,
                "name": tc.name,
                "input": tc.arguments,
            })
        messages.append({"role": "assistant", "content": assistant_content})

        # Execute each tool call and collect results
        tool_results = []
        for tc in response.tool_calls:
            handler = tool_handlers.get(tc.name)
            if not handler:
                result_str = f"Error: unknown tool '{tc.name}'"
            else:
                try:
                    result_str = handler.execute(tc.arguments)
                except Exception as e:
                    result_str = f"Error: {e}"

            all_tool_calls.append({
                "name": tc.name,
                "arguments": tc.arguments,
                "result": result_str[:2000],
            })
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": result_str,
            })

            print(f"  [tool] {tc.name}({_summarize_args(tc.arguments)})", file=sys.stderr, flush=True)

        messages.append({"role": "user", "content": tool_results})

    # Max iterations reached — return whatever we have
    return AgenticResult(
        text="\n\n".join(all_text),
        tool_calls_made=all_tool_calls,
        iterations=max_iterations,
    )


def _summarize_args(args: dict) -> str:
    """Create a short summary of tool arguments for logging."""
    parts = []
    for k, v in args.items():
        v_str = str(v)
        if len(v_str) > 60:
            v_str = v_str[:57] + "..."
        parts.append(f"{k}={v_str}")
    return ", ".join(parts)


def _get_provider(name: str, config: dict):
    if name == "anthropic":
        from kernel.llm.anthropic import AnthropicProvider
        return AnthropicProvider(config)
    elif name == "openai":
        from kernel.llm.openai import OpenAIProvider
        return OpenAIProvider(config)
    elif name == "xai":
        from kernel.llm.xai import XAIProvider
        return XAIProvider(config)
    else:
        raise ValueError(f"Unknown LLM provider: {name}")
