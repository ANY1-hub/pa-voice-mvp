"""OpenAI implementation for embeddings."""

from openai import AsyncOpenAI

from src.core.config import get_settings
from src.services.embeddings.base import EmbeddingsAdapter


class OpenAIEmbeddingsAdapter(EmbeddingsAdapter):
    """OpenAI-based embeddings adapter.

    Uses the model configured in Settings (default: text-embedding-3-small).
    """

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        """Initialize the OpenAI client.

        Args:
            api_key: Optional override for the API key (defaults to settings).
            model: Optional model name override (defaults to settings).
        """
        settings = get_settings()
        self.client = AsyncOpenAI(api_key=api_key or settings.openai_api_key)
        self.model = model or settings.embedding_model

    async def get_embedding(self, text: str) -> list[float]:
        """Return the embedding vector for a single text.

        Args:
            text: Input text.

        Returns:
            Embedding vector as a list of floats.
        """
        response = await self.client.embeddings.create(
            input=[text],
            model=self.model,
        )
        return response.data[0].embedding

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors for multiple texts.

        Args:
            texts: List of input texts.

        Returns:
            List of embedding vectors (same order as ``texts``).
        """
        response = await self.client.embeddings.create(
            input=texts,
            model=self.model,
        )
        return [item.embedding for item in response.data]
