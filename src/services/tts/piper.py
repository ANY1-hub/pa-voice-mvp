"""Piper implementation for Text-to-Speech (multi-voice)."""

from __future__ import annotations

import asyncio
import logging
import wave
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

from piper import PiperVoice

from src.core.config import get_settings
from src.services.tts.base import TTSAdapter

logger = logging.getLogger(__name__)

# Default relative paths under voice_models/piper/
DEFAULT_VOICE_PATHS: dict[str, str] = {
    "en": "voice_models/piper/en_GB-alan-medium.onnx",
    "de": "voice_models/piper/de_DE-thorsten-medium.onnx",
    "hu": "voice_models/piper/hu_HU-anna-medium.onnx",
}


class PiperTTSAdapter(TTSAdapter):
    """Local multi-voice TTS using Piper.

    Loads available voices for ``en`` (British), ``de`` and ``hu`` at startup.
    Missing models are skipped with a warning; synthesis falls back to any
    loaded voice so the rest of the system keeps working.
    Output is always a complete WAV (16-bit mono PCM).
    """

    def __init__(self, voice_paths: dict[str, str] | None = None) -> None:
        """Load all configured Piper voice models that exist on disk.

        Args:
            voice_paths: Optional map ``language_code → .onnx path``.
                Defaults come from settings / built-in paths.

        Raises:
            FileNotFoundError: If *no* voice model could be loaded at all.
        """
        settings = get_settings()
        paths = dict(DEFAULT_VOICE_PATHS)
        # Allow settings overrides (optional per-language env paths)
        if getattr(settings, "piper_voice_en", None):
            paths["en"] = settings.piper_voice_en
        if getattr(settings, "piper_voice_de", None):
            paths["de"] = settings.piper_voice_de
        if getattr(settings, "piper_voice_hu", None):
            paths["hu"] = settings.piper_voice_hu
        if voice_paths:
            paths.update(voice_paths)

        self._voices: dict[str, PiperVoice] = {}
        for lang, path in paths.items():
            voice_file = Path(path)
            if not voice_file.exists():
                logger.warning(
                    "Piper voice for '%s' not found at %s – skipping",
                    lang,
                    path,
                )
                continue
            try:
                self._voices[lang] = PiperVoice.load(path)
                logger.info("Loaded Piper voice '%s' from %s", lang, path)
            except Exception:
                logger.exception("Failed to load Piper voice '%s' from %s", lang, path)

        if not self._voices:
            raise FileNotFoundError(
                "No Piper voice models found. Download at least one of: "
                + ", ".join(DEFAULT_VOICE_PATHS.values())
                + " – see docs/piper-voice-setup.md"
            )

        self._default_lang = "en" if "en" in self._voices else next(iter(self._voices))
        self._executor = ThreadPoolExecutor(max_workers=1)

    def _resolve_voice(self, language: str | None) -> tuple[str, PiperVoice]:
        """Pick the best available voice for the requested language."""
        lang = (language or "").lower().strip()
        if lang in self._voices:
            return lang, self._voices[lang]
        # ISO variants like en-GB / de-DE
        if lang and lang[:2] in self._voices:
            return lang[:2], self._voices[lang[:2]]
        return self._default_lang, self._voices[self._default_lang]

    def _sample_rate(self, voice: PiperVoice) -> int:
        """Return the voice sample rate (fallback 22050)."""
        config = getattr(voice, "config", None)
        if config is not None:
            rate = getattr(config, "sample_rate", None)
            if isinstance(rate, int) and rate > 0:
                return rate
        return 22050

    def _chunk_to_pcm(self, chunk: object) -> bytes:
        """Extract raw 16-bit PCM bytes from a Piper chunk."""
        if hasattr(chunk, "audio_int16_bytes"):
            return chunk.audio_int16_bytes  # type: ignore[attr-defined]
        if isinstance(chunk, bytes | bytearray):
            return bytes(chunk)
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

    def _synthesize_sync(self, text: str, language: str | None) -> bytes:
        """Blocking synthesis (runs in thread pool)."""
        lang, voice = self._resolve_voice(language)
        logger.debug("TTS using voice '%s'", lang)

        pcm_parts: list[bytes] = []
        for chunk in voice.synthesize(text):
            pcm_parts.append(self._chunk_to_pcm(chunk))

        pcm = b"".join(pcm_parts)
        if not pcm:
            return b""

        return self._pcm_to_wav(pcm, self._sample_rate(voice))

    async def synthesize(self, text: str, language: str | None = None) -> bytes:
        """Synthesize speech asynchronously via the thread-pool worker.

        Args:
            text: Text to speak.
            language: Optional language code (``"en"``, ``"de"``, ``"hu"``).

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
            language,
        )
