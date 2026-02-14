import json
import re

from kernel.config import load_config


def call_llm(system: str, user: str) -> str:
    """Call the active LLM provider. Returns raw text."""
    config = load_config()
    provider_name = config["llm"]["provider"]
    model = config["llm"]["model"]
    provider = _get_provider(provider_name, config)
    return provider.complete(system, user, model)


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Get embeddings using the configured embedding provider."""
    config = load_config()
    provider_name = config["embedding"]["provider"]
    model = config["embedding"]["model"]
    provider = _get_provider(provider_name, config)
    return provider.embed(texts, model)


def extract_json(text: str) -> dict | list | None:
    """Extract JSON from markdown code fences, or parse raw JSON."""
    pattern = r'```(?:json)?\s*\n(.*?)\n```'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Try parsing the whole text as JSON
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


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
