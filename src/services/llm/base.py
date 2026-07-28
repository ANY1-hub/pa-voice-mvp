"""Abstract base class for Language Model adapters."""

from abc import ABC, abstractmethod
from typing import Any


class LLMAdapter(ABC):
    """Abstract base class for Language Model adapters.

    Ensures easy swapping between OpenAI, Ollama, etc.
    """

    @abstractmethod
    async def generate_response(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> str:
        """Generate a response from a list of chat messages.

        Args:
            messages: Chat messages as ``{"role": ..., "content": ...}`` dicts.
            **kwargs: Optional provider-specific parameters.

        Returns:
            Generated reply text.
        """
        pass

    @abstractmethod
    async def extract_entities(self, text: str) -> list[str]:
        """Extract named entities from the given text.

        Args:
            text: Input text to analyse.

        Returns:
            List of entity strings (empty list on failure / no entities).
        """
        pass
