"""Abstract base class for Language Model adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LLMResult:
    """Text plus optional token counts from one model call.

    Attributes:
        text: Assistant message content.
        prompt_tokens: Prompt-side usage, if the provider reports it.
        completion_tokens: Completion-side usage, if the provider reports it.
    """

    text: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None

    @property
    def tokens(self) -> int | None:
        """Total tokens, or ``None`` when the provider reported no usage."""
        if self.prompt_tokens is None and self.completion_tokens is None:
            return None
        return (self.prompt_tokens or 0) + (self.completion_tokens or 0)


def llm_text(raw: object) -> str:
    """Unwrap ``generate_response`` output to plain text.

    Mocks may still return ``str``; adapters return ``LLMResult``.
    """
    if isinstance(raw, LLMResult):
        return raw.text
    if raw is None:
        return ""
    return str(raw)


def as_llm_result(raw: object) -> LLMResult:
    """Normalize ``generate_response`` output to ``LLMResult``."""
    if isinstance(raw, LLMResult):
        return raw
    return LLMResult(text=llm_text(raw))


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
            Generated reply text, or ``LLMResult`` with optional token counts.
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
