"""OpenAI implementation for embeddings."""

import os

from openai import AsyncOpenAI

from src.services.embeddings.base import EmbeddingsAdapter


class OpenAIEmbeddingsAdapter(EmbeddingsAdapter):
    """
    OpenAI-based embeddings adapter.
    Uses 'text-embedding-3-small' by default.
    """

    def __init__(
        self, api_key: str | None = None, model: str = "text-embedding-3-small"
    ):
        """Initialize the OpenAI client."""
        self.client = AsyncOpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
        self.model = model

    async def get_embedding(self, text: str) -> list[float]:
        """Return the embedding vector for a single text."""
        response = await self.client.embeddings.create(
            input=[text],
            model=self.model,
        )
        return response.data[0].embedding

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors for multiple texts."""
        response = await self.client.embeddings.create(
            input=texts,
            model=self.model,
        )
        return [item.embedding for item in response.data]
