"""Abstract base class for Speech-to-Text adapters."""

from abc import ABC, abstractmethod


class STTAdapter(ABC):
    """
    Abstract base class for STT adapters.
    Ensures easy swapping (faster-whisper → others later).
    """

    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, language: str | None = None) -> str:
        """
        Transcribe raw audio bytes to text.
        language=None → auto-detect.
        """
        pass
