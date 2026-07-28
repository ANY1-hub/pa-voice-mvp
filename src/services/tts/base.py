"""Abstract base class for Text-to-Speech adapters."""

from abc import ABC, abstractmethod


class TTSAdapter(ABC):
    """Abstract base class for TTS adapters.

    Ensures easy swapping (Piper → others later).
    """

    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """Convert text to audio bytes.

        Args:
            text: Text to speak.

        Returns:
            Audio bytes (WAV or raw PCM) ready for the client.
            May be empty if ``text`` is blank.
        """
        pass
