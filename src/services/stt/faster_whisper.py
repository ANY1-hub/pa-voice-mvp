"""Faster-Whisper implementation for Speech-to-Text."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from faster_whisper import WhisperModel

from src.core.config import get_settings
from src.services.stt.base import STTAdapter


class FasterWhisperSTTAdapter(STTAdapter):
    """
    Local STT using faster-whisper (CTranslate2).
    Default: base model + int8 for CPU-friendly latency.
    """

    def __init__(
        self,
        model_size: str | None = None,
        device: str = "cpu",
        compute_type: str = "int8",
    ):
        settings = get_settings()
        self.model_size = model_size or getattr(settings, "whisper_model", "base")
        self.device = device
        self.compute_type = compute_type

        # Load once at startup (blocking is fine here)
        self.model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
        )
        self._executor = ThreadPoolExecutor(max_workers=1)

    def _transcribe_sync(self, audio_bytes: bytes, language: str | None) -> str:
        """Blocking transcription (runs in thread pool)."""
        # faster-whisper accepts file-like or path; we use BytesIO
        from io import BytesIO

        segments, _ = self.model.transcribe(
            BytesIO(audio_bytes),
            language=language,
            beam_size=5,
            vad_filter=True,  # helps with silence
        )
        return " ".join(segment.text.strip() for segment in segments).strip()

    async def transcribe(self, audio_bytes: bytes, language: str | None = None) -> str:
        """Async wrapper around the blocking faster-whisper call."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._executor,
            self._transcribe_sync,
            audio_bytes,
            language,
        )
