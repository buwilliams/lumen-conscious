import os

from kernel.llm.base import LLMProvider


class AnthropicProvider(LLMProvider):

    def __init__(self, config: dict):
        auth_type = config["llm"].get("auth_type", "api_key")
        import anthropic

        if auth_type == "auth_token":
            token = config["llm"].get("auth_token") or os.environ.get(
                config["llm"].get("auth_token_env", "ANTHROPIC_AUTH_TOKEN")
            )
            if not token:
                raise ValueError("Set llm.auth_token in config.json or ANTHROPIC_AUTH_TOKEN env var")
            self.client = anthropic.Anthropic(auth_token=token)
        else:
            api_key = config["llm"].get("api_key") or os.environ.get(
                config["llm"].get("api_key_env", "ANTHROPIC_API_KEY")
            )
            if not api_key:
                raise ValueError("Set llm.api_key in config.json or ANTHROPIC_API_KEY env var")
            self.client = anthropic.Anthropic(api_key=api_key)

    def complete(self, system: str, user: str, model: str) -> str:
        response = self.client.messages.create(
            model=model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text
