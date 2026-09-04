"""Grok (xAI) implementation for Language Model."""

import json
from typing import Any

from openai import AsyncOpenAI

from src.core.config import get_settings
from src.services.llm.base import LLMAdapter, LLMResult


class GrokLLMAdapter(LLMAdapter):
    """Grok-based LLM adapter (xAI).

    Compatible with the OpenAI SDK via the xAI base URL.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        """Initialize the xAI client using the OpenAI SDK.

        Args:
            api_key: Optional override for the xAI API key (defaults to settings).
            model: Optional model name override (defaults to settings).
        """
        settings = get_settings()
        self.client = AsyncOpenAI(
            api_key=api_key or settings.xai_api_key or "dummy_key",
            base_url="https://api.x.ai/v1",
        )
        self.model = model or settings.grok_model

    async def generate_response(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> str:
        """Generate a response from a list of chat messages.

        Args:
            messages: Chat messages as ``{"role": ..., "content": ...}`` dicts.
            **kwargs: Extra arguments forwarded to the API.

        Returns:
            ``LLMResult`` with reply text and usage when the API sends it.
        """
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            **kwargs,
        )
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
        completion_tokens = getattr(usage, "completion_tokens", None) if usage else None
        return LLMResult(
            text=response.choices[0].message.content or "",
            prompt_tokens=prompt_tokens if isinstance(prompt_tokens, int) else None,
            completion_tokens=(
                completion_tokens if isinstance(completion_tokens, int) else None
            ),
        )

    async def extract_entities(self, text: str) -> list[str]:
        """Extract named entities using structured JSON output.

        Args:
            text: Input text to analyse.

        Returns:
            List of entity strings, or an empty list on parse failure.
        """
        messages = [
            {
                "role": "system",
                "content": (
                    "Extract the key entities (people, places, concepts, objects) "
                    "from the user's text. Return a JSON object with a single key 'entities' "
                    'containing a list of strings. E.g., {"entities": ["Python", "John"]}'
                ),
            },
            {"role": "user", "content": text},
        ]

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        content = response.choices[0].message.content or "{}"
        try:
            data = json.loads(content)
            return data.get("entities", [])
        except json.JSONDecodeError:
            return []
