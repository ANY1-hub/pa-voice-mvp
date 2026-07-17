"""Gemini (Google) placeholder implementation for Language Model."""

from typing import Any

from src.services.llm.base import LLMAdapter


class GeminiLLMAdapter(LLMAdapter):
    """
    Gemini-based LLM adapter.
    This is a placeholder for future implementation.
    """

    def __init__(self, api_key: str | None = None, model: str = "gemini-1.5-flash"):
        """Initialize the Gemini client (Not Implemented)."""
        self.api_key = api_key
        self.model = model

    async def generate_response(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> str:
        """Generate a response from a list of chat messages."""
        raise NotImplementedError(
            "[LLM_CONTEXT: GeminiLLMAdapter generation requires google-genai SDK implementation. Target: Post-MVP Phase 2.]"
        )

    async def extract_entities(self, text: str) -> list[str]:
        """Extract named entities from the given text."""
        raise NotImplementedError(
            "[LLM_CONTEXT: GeminiLLMAdapter extraction requires google-genai SDK implementation. Target: Post-MVP Phase 2.]"
        )
