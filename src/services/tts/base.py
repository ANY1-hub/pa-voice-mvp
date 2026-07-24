"""Abstract base class for Text-to-Speech adapters."""

from abc import ABC, abstractmethod


class TTSAdapter(ABC):
    """
    Abstract base class for TTS adapters.
    Ensures easy swapping (Piper → others later).
    """

    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """
        Convert text to audio bytes (WAV or raw PCM).
        Returns the audio as bytes ready for the client.
        """
        pass
