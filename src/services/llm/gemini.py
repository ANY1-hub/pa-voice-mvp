"""Gemini (Google) placeholder implementation for Language Model."""

from typing import Any

from src.services.llm.base import LLMAdapter


class GeminiLLMAdapter(LLMAdapter):
    """Gemini-based LLM adapter.

    Placeholder for future implementation (post-MVP).
    """

    def __init__(self, api_key: str | None = None, model: str = "gemini-1.5-flash") -> None:
        """Initialize the Gemini client (not implemented yet).

        Args:
            api_key: Optional Google API key.
            model: Gemini model name (default ``"gemini-1.5-flash"``).
        """
        self.api_key = api_key
        self.model = model

    async def generate_response(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> str:
        """Generate a response from a list of chat messages.

        Args:
            messages: Chat messages as ``{"role": ..., "content": ...}`` dicts.
            **kwargs: Provider-specific options (unused).

        Returns:
            Never returns; always raises.

        Raises:
            NotImplementedError: Always – adapter is a post-MVP placeholder.
        """
        raise NotImplementedError(
            "[LLM_CONTEXT: GeminiLLMAdapter generation requires google-genai SDK implementation. Target: Post-MVP Phase 2.]"
        )

    async def extract_entities(self, text: str) -> list[str]:
        """Extract named entities from the given text.

        Args:
            text: Input text to analyse.

        Returns:
            Never returns; always raises.

        Raises:
            NotImplementedError: Always – adapter is a post-MVP placeholder.
        """
        raise NotImplementedError(
            "[LLM_CONTEXT: GeminiLLMAdapter extraction requires google-genai SDK implementation. Target: Post-MVP Phase 2.]"
        )
