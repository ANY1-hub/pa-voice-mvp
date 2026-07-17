"""Grok (xAI) implementation for Language Model."""

import json
from typing import Any

from openai import AsyncOpenAI

from src.core.config import get_settings
from src.services.llm.base import LLMAdapter


class GrokLLMAdapter(LLMAdapter):
    """
    Grok-based LLM adapter (xAI).
    Compatible with the OpenAI SDK.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None):
        """Initialize the xAI client using the OpenAI SDK."""
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
        """Generate a response from a list of chat messages."""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            **kwargs,
        )
        return response.choices[0].message.content or ""

    async def extract_entities(self, text: str) -> list[str]:
        """
        Extract named entities from the given text using structured JSON output.
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
