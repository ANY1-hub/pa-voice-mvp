"""Unit tests for PiperTTSAdapter (multi-voice, no real models required)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.services.tts.piper import PiperTTSAdapter


def _fake_voice(sample_rate: int = 22050, pcm: bytes = b"\x00\x01" * 80):
    """Build a minimal PiperVoice-like mock."""
    voice = MagicMock()
    voice.config = SimpleNamespace(sample_rate=sample_rate)
    chunk = SimpleNamespace(audio_int16_bytes=pcm)
    voice.synthesize.return_value = iter([chunk])
    return voice


@pytest.fixture
def adapter_en_de():
    """Adapter with mocked en + de voices (no filesystem / onnx)."""
    en_voice = _fake_voice(sample_rate=22050)
    de_voice = _fake_voice(sample_rate=16000)

    with (
        patch("src.services.tts.piper.get_settings") as mock_settings,
        patch("src.services.tts.piper.Path") as mock_path_cls,
        patch("src.services.tts.piper.PiperVoice") as mock_piper,
    ):
        settings = MagicMock()
        settings.piper_voice_en = "fake/en.onnx"
        settings.piper_voice_de = "fake/de.onnx"
        settings.piper_voice_hu = "fake/hu.onnx"
        mock_settings.return_value = settings

        # All configured paths "exist"
        path_instance = MagicMock()
        path_instance.exists.return_value = True
        mock_path_cls.return_value = path_instance

        def load_side_effect(path: str):
            if "en" in path or path.endswith("en.onnx"):
                return en_voice
            if "de" in path or path.endswith("de.onnx"):
                return de_voice
            if "hu" in path or path.endswith("hu.onnx"):
                return _fake_voice()
            return en_voice

        mock_piper.load.side_effect = load_side_effect

        adapter = PiperTTSAdapter(
            voice_paths={
                "en": "fake/en.onnx",
                "de": "fake/de.onnx",
                "hu": "fake/hu.onnx",
            }
        )
        # Expose mocks for assertions
        adapter._test_en = en_voice
        adapter._test_de = de_voice
        yield adapter


def test_no_voices_raises():
    with (
        patch("src.services.tts.piper.get_settings") as mock_settings,
        patch("src.services.tts.piper.Path") as mock_path_cls,
    ):
        settings = MagicMock()
        settings.piper_voice_en = "missing/en.onnx"
        settings.piper_voice_de = "missing/de.onnx"
        settings.piper_voice_hu = "missing/hu.onnx"
        mock_settings.return_value = settings

        path_instance = MagicMock()
        path_instance.exists.return_value = False
        mock_path_cls.return_value = path_instance

        with pytest.raises(FileNotFoundError, match="No Piper voice"):
            PiperTTSAdapter()


def test_resolve_voice_exact(adapter_en_de):
    lang, voice = adapter_en_de._resolve_voice("de")
    assert lang == "de"
    assert voice is adapter_en_de._test_de


def test_resolve_voice_iso_variant(adapter_en_de):
    lang, voice = adapter_en_de._resolve_voice("de-DE")
    assert lang == "de"
    assert voice is adapter_en_de._test_de


def test_resolve_voice_fallback_to_default(adapter_en_de):
    lang, voice = adapter_en_de._resolve_voice("fr")
    assert lang == "en"
    assert voice is adapter_en_de._test_en


def test_resolve_voice_none_uses_default(adapter_en_de):
    lang, voice = adapter_en_de._resolve_voice(None)
    assert lang == "en"


@pytest.mark.asyncio
async def test_synthesize_empty_text_returns_empty(adapter_en_de):
    assert await adapter_en_de.synthesize("   ") == b""
    assert await adapter_en_de.synthesize("") == b""


@pytest.mark.asyncio
async def test_synthesize_returns_wav_header(adapter_en_de):
    data = await adapter_en_de.synthesize("Hello", language="en")
    assert data[:4] == b"RIFF"
    assert b"WAVE" in data[:16]
    adapter_en_de._test_en.synthesize.assert_called()


@pytest.mark.asyncio
async def test_synthesize_uses_requested_language(adapter_en_de):
    await adapter_en_de.synthesize("Guten Tag", language="de")
    adapter_en_de._test_de.synthesize.assert_called()
    adapter_en_de._test_en.synthesize.assert_not_called()


def test_chunk_to_pcm_bytes(adapter_en_de):
    assert adapter_en_de._chunk_to_pcm(b"abc") == b"abc"


def test_chunk_to_pcm_audio_int16(adapter_en_de):
    chunk = SimpleNamespace(audio_int16_bytes=b"\x01\x02")
    assert adapter_en_de._chunk_to_pcm(chunk) == b"\x01\x02"


def test_chunk_to_pcm_unsupported_raises(adapter_en_de):
    with pytest.raises(TypeError, match="Unsupported"):
        adapter_en_de._chunk_to_pcm(12345)
