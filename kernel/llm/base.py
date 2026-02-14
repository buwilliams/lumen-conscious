from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Base class for LLM providers."""

    @abstractmethod
    def complete(self, system: str, user: str, model: str) -> str:
        """Send a completion request. Returns raw text."""
        ...

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        """Get embeddings for texts. Not all providers support this."""
        raise NotImplementedError(f"{self.__class__.__name__} does not support embeddings")
