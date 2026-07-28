"""Abstract base class for Speech-to-Text adapters."""

from abc import ABC, abstractmethod


class STTAdapter(ABC):
    """Abstract base class for STT adapters.

    Ensures easy swapping (faster-whisper → others later).
    """

    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, language: str | None = None) -> str:
        """Transcribe raw audio bytes to text.

        Args:
            audio_bytes: Raw audio payload (any common format; adapter may convert).
            language: Optional ISO language code (e.g. ``"de"``, ``"en"``, ``"hu"``).
                ``None`` means auto-detect.

        Returns:
            Transcribed text (may be empty if nothing was recognized).
        """
        pass
