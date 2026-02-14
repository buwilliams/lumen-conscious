import os

from kernel.llm.base import LLMProvider


class AnthropicProvider(LLMProvider):

    def __init__(self, config: dict):
        api_key_env = config["llm"].get("api_key_env", "ANTHROPIC_API_KEY")
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise ValueError(f"Set {api_key_env} environment variable for Anthropic provider")
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)

    def complete(self, system: str, user: str, model: str) -> str:
        response = self.client.messages.create(
            model=model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text
