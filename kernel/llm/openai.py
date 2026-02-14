import os

from kernel.llm.base import LLMProvider


class OpenAIProvider(LLMProvider):

    def __init__(self, config: dict):
        api_key_env = config["llm"].get("api_key_env", "OPENAI_API_KEY")
        # For embeddings, use the embedding config's key
        embed_key_env = config.get("embedding", {}).get("api_key_env", api_key_env)

        api_key = os.environ.get(api_key_env) or os.environ.get(embed_key_env)
        if not api_key:
            raise ValueError(f"Set {api_key_env} environment variable for OpenAI provider")
        import openai
        self.client = openai.OpenAI(api_key=api_key)
        # Keep a separate client for embeddings if keys differ
        embed_key = os.environ.get(embed_key_env)
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
