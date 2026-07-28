"""Piper implementation for Text-to-Speech."""

import asyncio
import wave
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

from piper import PiperVoice

from src.core.config import get_settings
from src.services.tts.base import TTSAdapter


class PiperTTSAdapter(TTSAdapter):
    """Local TTS using Piper.

    Voice model is loaded once at startup.
    Output is always a complete WAV (16-bit mono PCM) so browsers can play it.
    """

    def __init__(self, voice_path: str | None = None) -> None:
        """Load the Piper voice model.

        Args:
            voice_path: Path to the ``.onnx`` voice file. Falls back to settings
                / default relative path.

        Raises:
            FileNotFoundError: If the voice model file does not exist.
        """
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

    def _sample_rate(self) -> int:
        """Return the voice sample rate (fallback 22050)."""
        config = getattr(self.voice, "config", None)
        if config is not None:
            rate = getattr(config, "sample_rate", None)
            if isinstance(rate, int) and rate > 0:
                return rate
        return 22050

    def _chunk_to_pcm(self, chunk: object) -> bytes:
        """Extract raw 16-bit PCM bytes from a Piper chunk.

        Supports both modern ``AudioChunk`` objects and plain ``bytes``.
        """
        if hasattr(chunk, "audio_int16_bytes"):
            return chunk.audio_int16_bytes  # type: ignore[attr-defined]
        if isinstance(chunk, (bytes, bytearray)):
            return bytes(chunk)
        # Last resort – some builds expose .audio_bytes
        if hasattr(chunk, "audio_bytes"):
            return bytes(chunk.audio_bytes)  # type: ignore[attr-defined]
        raise TypeError(f"Unsupported Piper chunk type: {type(chunk)!r}")

    def _pcm_to_wav(self, pcm: bytes, sample_rate: int) -> bytes:
        """Wrap raw 16-bit mono PCM in a WAV container."""
        buf = BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)  # 16-bit
            wav.setframerate(sample_rate)
            wav.writeframes(pcm)
        return buf.getvalue()

    def _synthesize_sync(self, text: str) -> bytes:
        """Blocking synthesis (runs in thread pool).

        Args:
            text: Text to speak.

        Returns:
            Complete WAV bytes (16-bit mono PCM).
        """
        # piper-tts returns a generator of AudioChunk (not a context manager)
        pcm_parts: list[bytes] = []
        for chunk in self.voice.synthesize(text):
            pcm_parts.append(self._chunk_to_pcm(chunk))

        pcm = b"".join(pcm_parts)
        if not pcm:
            return b""

        return self._pcm_to_wav(pcm, self._sample_rate())

    async def synthesize(self, text: str) -> bytes:
        """Synthesize speech asynchronously via the thread-pool worker.

        Args:
            text: Text to speak.

        Returns:
            WAV audio bytes ready for the client. Empty bytes if ``text`` is blank.
        """
        if not text.strip():
            return b""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._executor,
            self._synthesize_sync,
            text,
        )
