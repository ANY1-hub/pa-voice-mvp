"""Faster-Whisper implementation for Speech-to-Text."""

import asyncio
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import imageio_ffmpeg
from faster_whisper import WhisperModel

from src.core.config import get_settings
from src.services.stt.base import STTAdapter


class FasterWhisperSTTAdapter(STTAdapter):
    """Local STT using faster-whisper (CTranslate2).

    Incoming browser audio (often webm/opus) is converted to
    16 kHz mono WAV via a bundled ffmpeg binary (imageio-ffmpeg).
    No system-wide ffmpeg install required.
    """

    def __init__(
        self,
        model_size: str | None = None,
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        """Load the Whisper model once.

        Args:
            model_size: Whisper model size (e.g. ``"base"``, ``"small"``).
                Falls back to settings / ``"base"``.
            device: Inference device (``"cpu"`` or ``"cuda"``).
            compute_type: Quantization type (e.g. ``"int8"``, ``"float16"``).
        """
        settings = get_settings()
        self.model_size = model_size or getattr(settings, "whisper_model", "base")
        self.device = device
        self.compute_type = compute_type
        self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

        self.model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
        )
        self._executor = ThreadPoolExecutor(max_workers=1)

    def _to_wav_16k_mono(self, audio_bytes: bytes) -> Path:
        """Convert arbitrary audio bytes to 16 kHz mono WAV.

        Args:
            audio_bytes: Raw input audio.

        Returns:
            Path to a temporary WAV file (caller must delete it).
        """
        with tempfile.NamedTemporaryFile(suffix=".input", delete=False) as src:
            src.write(audio_bytes)
            src_path = Path(src.name)

        dst_path = src_path.with_suffix(".wav")

        cmd = [
            self.ffmpeg_exe,
            "-y",
            "-i",
            str(src_path),
            "-ar",
            "16000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(dst_path),
        ]
        try:
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
            )
        finally:
            src_path.unlink(missing_ok=True)

        return dst_path

    def _transcribe_sync(self, audio_bytes: bytes, language: str | None) -> str:
        """Blocking transcription (runs in thread pool).

        Args:
            audio_bytes: Raw audio payload.
            language: Optional language code; ``None`` = auto-detect.

        Returns:
            Transcribed text.
        """
        wav_path = self._to_wav_16k_mono(audio_bytes)
        try:
            segments, _ = self.model.transcribe(
                str(wav_path),
                language=language,
                beam_size=5,
                vad_filter=True,
            )
            return " ".join(segment.text.strip() for segment in segments).strip()
        finally:
            wav_path.unlink(missing_ok=True)

    async def transcribe(self, audio_bytes: bytes, language: str | None = None) -> str:
        """Transcribe audio asynchronously via the thread-pool worker.

        Args:
            audio_bytes: Raw audio payload (any common format).
            language: Optional ISO language code; ``None`` = auto-detect.

        Returns:
            Transcribed text.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._executor,
            self._transcribe_sync,
            audio_bytes,
            language,
        )
