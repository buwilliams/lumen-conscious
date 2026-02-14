import os

from kernel.llm.base import LLMProvider


class OpenAIProvider(LLMProvider):

    def __init__(self, config: dict):
        api_key = config["llm"].get("api_key") or os.environ.get(
            config["llm"].get("api_key_env", "OPENAI_API_KEY")
        )
        if not api_key:
            raise ValueError("Set llm.api_key in config.json or OPENAI_API_KEY env var")

        embed_cfg = config.get("embedding", {})
        embed_key = embed_cfg.get("api_key") or os.environ.get(
            embed_cfg.get("api_key_env", "OPENAI_API_KEY")
        )

        import openai
        self.client = openai.OpenAI(api_key=api_key)
        if embed_key and embed_key != api_key:
            self.embed_client = openai.OpenAI(api_key=embed_key)
        else:
            self.embed_client = self.client

    def complete(self, system: str, user: str, model: str) -> str:
        response = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        response = self.embed_client.embeddings.create(
            model=model,
            input=texts,
        )
        return [item.embedding for item in response.data]
