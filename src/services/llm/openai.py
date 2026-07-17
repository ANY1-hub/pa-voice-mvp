"""OpenAI implementation for Language Model."""

import json
import os
from typing import Any

from openai import AsyncOpenAI

from src.services.llm.base import LLMAdapter


class OpenAILLMAdapter(LLMAdapter):
    """
    OpenAI-based LLM adapter.
    Uses 'gpt-4o-mini' by default for MVP.
    """

    def __init__(self, api_key: str | None = None, model: str = "gpt-4o-mini"):
        """Initialize the OpenAI client."""
        self.client = AsyncOpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
        self.model = model

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
        Extract named entities from the given text using function calling
        or structured outputs (JSON mode).
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
