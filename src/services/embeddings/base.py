"""Abstract base class for embedding providers."""

from abc import ABC, abstractmethod


class EmbeddingsAdapter(ABC):
    """Abstract base class for Embeddings adapters.

    Ensures easy swapping between OpenAI embeddings and local SentenceTransformers.
    """

    @abstractmethod
    async def get_embedding(self, text: str) -> list[float]:
        """Return the embedding vector for a single text.

        Args:
            text: Input text.

        Returns:
            Embedding vector as a list of floats.
        """
        pass

    @abstractmethod
    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors for multiple texts.

        Args:
            texts: List of input texts.

        Returns:
            List of embedding vectors (same order as ``texts``).
        """
        pass
