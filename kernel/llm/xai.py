import os

from kernel.llm.base import LLMProvider


class XAIProvider(LLMProvider):
    """xAI/Grok provider. Uses OpenAI-compatible API."""

    def __init__(self, config: dict):
        api_key_env = config["llm"].get("api_key_env", "XAI_API_KEY")
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise ValueError(f"Set {api_key_env} environment variable for xAI provider")
        import openai
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1",
        )

    def complete(self, system: str, user: str, model: str) -> str:
        response = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content
