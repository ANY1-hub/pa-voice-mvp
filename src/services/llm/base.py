from abc import ABC, abstractmethod
from typing import List, Dict, Any

class LLMAdapter(ABC):
    """
    Abstract base class for Language Model adapters.
    Ensures easy swapping between OpenAI, Ollama, etc.
    """
    @abstractmethod
    async def generate_response(self, messages: List[Dict[str, str]], **kwargs) -> str:
        pass

    @abstractmethod
    async def extract_entities(self, text: str) -> List[str]:
        pass