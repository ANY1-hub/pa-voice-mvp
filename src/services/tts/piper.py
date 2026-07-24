"""Piper implementation for Text-to-Speech."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

from piper import PiperVoice

from src.core.config import get_settings
from src.services.tts.base import TTSAdapter


class PiperTTSAdapter(TTSAdapter):
    """
    Local TTS using Piper.
    Voice model is loaded once at startup.
    """

    def __init__(self, voice_path: str | None = None):
        settings = get_settings()
        # Default path – user can override via config / env
        self.voice_path = voice_path or getattr(
            settings, "piper_voice_path", "voice_models/piper/en_US-lessac-medium.onnx"
        )

        voice_file = Path(self.voice_path)
        if not voice_file.exists():
            raise FileNotFoundError(
                f"Piper voice model not found at: {self.voice_path}. "
                "Download a voice from https://rhasspy.github.io/piper-samples/ "
                "and place the .onnx (+ .json) file there."
            )

        self.voice = PiperVoice.load(self.voice_path)
        self._executor = ThreadPoolExecutor(max_workers=1)

    def _synthesize_sync(self, text: str) -> bytes:
        """Blocking synthesis (runs in thread pool)."""
        audio_buffer = BytesIO()
        with self.voice.synthesize(text) as stream:
            for audio_bytes in stream:
                audio_buffer.write(audio_bytes)
        return audio_buffer.getvalue()

    async def synthesize(self, text: str) -> bytes:
        """Async wrapper around the blocking Piper call."""
        if not text.strip():
            return b""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._executor,
            self._synthesize_sync,
            text,
        )
