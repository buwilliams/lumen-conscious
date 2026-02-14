from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolUseRequest:
    """A tool call requested by the LLM."""
    id: str
    name: str
    arguments: dict = field(default_factory=dict)


@dataclass
class LLMResponse:
    """Structured response from an LLM, supporting tool use."""
    text: str = ""
    tool_calls: list[ToolUseRequest] = field(default_factory=list)
    stop_reason: str = "end_turn"


class LLMProvider(ABC):
    """Base class for LLM providers."""

    @abstractmethod
    def complete(self, system: str, user: str, model: str) -> str:
        """Send a completion request. Returns raw text."""
        ...

    def complete_with_tools(self, system: str, messages: list[dict], tools: list[dict], model: str) -> LLMResponse:
        """Send a completion request with tool definitions. Returns structured response."""
        raise NotImplementedError(f"{self.__class__.__name__} does not support tool use")

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        """Get embeddings for texts. Not all providers support this."""
        raise NotImplementedError(f"{self.__class__.__name__} does not support embeddings")
