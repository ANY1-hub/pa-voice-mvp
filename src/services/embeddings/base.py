from abc import ABC, abstractmethod
from typing import List

class EmbeddingsAdapter(ABC):
    """
    Abstract base class for Embeddings adapters.
    Ensures easy swapping between OpenAI embeddings and local SentenceTransformers.
    """
    @abstractmethod
    async def get_embedding(self, text: str) -> List[float]:
        pass

    @abstractmethod
    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        pass