"""Abstract base class for Language Model adapters."""

from abc import ABC, abstractmethod
from typing import Any


class LLMAdapter(ABC):
    """
    Abstract base class for Language Model adapters.

    Ensures easy swapping between OpenAI, Ollama, etc.
    """

    @abstractmethod
    async def generate_response(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> str:
        """Generate a response from a list of chat messages."""
        pass

    @abstractmethod
    async def extract_entities(self, text: str) -> list[str]:
        """Extract named entities from the given text."""
        pass
