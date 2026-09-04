"""Unit tests for FasterWhisperSTTAdapter (no real model / ffmpeg required)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.services.stt.faster_whisper import FasterWhisperSTTAdapter


@pytest.fixture
def stt_adapter():
    """Build an STT adapter with Whisper, ffmpeg and settings fully mocked.

    Yields:
        Tuple of (adapter, mocked WhisperModel instance).
    """
    with (
        patch("src.services.stt.faster_whisper.get_settings") as mock_settings,
        patch("src.services.stt.faster_whisper.imageio_ffmpeg") as mock_ffmpeg,
        patch("src.services.stt.faster_whisper.WhisperModel") as mock_whisper,
    ):
        mock_settings.return_value = MagicMock(whisper_model="base")
        mock_ffmpeg.get_ffmpeg_exe.return_value = "/fake/ffmpeg"
        model = MagicMock()
        mock_whisper.return_value = model

        adapter = FasterWhisperSTTAdapter(model_size="base")
        yield adapter, model


def _segment(text: str) -> MagicMock:
    """Tiny helper: fake Whisper segment with a .text attribute."""
    seg = MagicMock()
    seg.text = text
    return seg


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


def test_init_uses_explicit_model_size():
    """When the caller passes a model size, that value must win over settings."""
    with (
        patch("src.services.stt.faster_whisper.get_settings") as mock_settings,
        patch("src.services.stt.faster_whisper.imageio_ffmpeg") as mock_ffmpeg,
        patch("src.services.stt.faster_whisper.WhisperModel") as mock_whisper,
    ):
        mock_settings.return_value = MagicMock(whisper_model="tiny")
        mock_ffmpeg.get_ffmpeg_exe.return_value = "/fake/ffmpeg"

        adapter = FasterWhisperSTTAdapter(model_size="small")

        assert adapter.model_size == "small"
        mock_whisper.assert_called_once_with("small", device="cpu", compute_type="int8")


def test_init_falls_back_to_settings_model_size():
    """Without an explicit model size, the adapter must read it from settings."""
    with (
        patch("src.services.stt.faster_whisper.get_settings") as mock_settings,
        patch("src.services.stt.faster_whisper.imageio_ffmpeg") as mock_ffmpeg,
        patch("src.services.stt.faster_whisper.WhisperModel") as mock_whisper,
    ):
        mock_settings.return_value = MagicMock(whisper_model="tiny")
        mock_ffmpeg.get_ffmpeg_exe.return_value = "/fake/ffmpeg"

        adapter = FasterWhisperSTTAdapter()

        assert adapter.model_size == "tiny"
        mock_whisper.assert_called_once_with("tiny", device="cpu", compute_type="int8")


# ---------------------------------------------------------------------------
# _to_wav_16k_mono
# ---------------------------------------------------------------------------


def test_to_wav_success_returns_wav_path(stt_adapter):
    """Successful conversion must return a .wav path and call ffmpeg with 16 kHz mono settings."""
    adapter, _model = stt_adapter
    with patch("src.services.stt.faster_whisper.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)

        result = adapter._to_wav_16k_mono(b"fake-audio-bytes")

        assert isinstance(result, Path)
        assert result.suffix == ".wav"
        mock_run.assert_called_once()
        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "/fake/ffmpeg"
        assert "-ar" in cmd and "16000" in cmd
        assert "-ac" in cmd and "1" in cmd
        assert mock_run.call_args.kwargs.get("timeout") == 60
        src_arg = Path(cmd[cmd.index("-i") + 1])
        assert not src_arg.exists()


def test_to_wav_called_process_error_raises_value_error(stt_adapter):
    """If ffmpeg exits with an error, callers must get a clear ValueError about conversion."""
    import subprocess

    adapter, _model = stt_adapter
    with patch("src.services.stt.faster_whisper.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, cmd=["ffmpeg"])

        with pytest.raises(ValueError, match="conversion failed"):
            adapter._to_wav_16k_mono(b"bad-audio")


def test_to_wav_os_error_raises_value_error(stt_adapter):
    """If ffmpeg cannot even be started (missing binary etc.), raise a friendly ValueError."""
    adapter, _model = stt_adapter
    with patch("src.services.stt.faster_whisper.subprocess.run") as mock_run:
        mock_run.side_effect = OSError("no such file")

        with pytest.raises(ValueError, match="Could not process audio"):
            adapter._to_wav_16k_mono(b"bad-audio")


def test_to_wav_timeout_raises_value_error(stt_adapter):
    """A hung ffmpeg must fail the conversion instead of blocking the turn."""
    import subprocess

    adapter, _model = stt_adapter
    with patch("src.services.stt.faster_whisper.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["ffmpeg"], timeout=60)

        with pytest.raises(ValueError, match="conversion failed"):
            adapter._to_wav_16k_mono(b"slow-audio")


# ---------------------------------------------------------------------------
# _transcribe_sync
# ---------------------------------------------------------------------------


def test_transcribe_sync_joins_segment_texts(stt_adapter):
    """Multiple Whisper segments must be joined into one clean transcript string."""
    adapter, model = stt_adapter
    model.transcribe.return_value = (
        [_segment(" Hello "), _segment(" world ")],
        None,
    )

    with (
        patch.object(adapter, "_to_wav_16k_mono", return_value=Path("/tmp/fake.wav")),
        patch.object(Path, "unlink"),
    ):
        text, detected = adapter._transcribe_sync(b"audio", language="en")

    assert text == "Hello world"
    assert detected is None
    model.transcribe.assert_called_once()
    _, kwargs = model.transcribe.call_args
    assert kwargs.get("language") == "en"
    assert kwargs.get("beam_size") == 1
    assert kwargs.get("condition_on_previous_text") is False


def test_transcribe_sync_empty_segments_returns_empty_string(stt_adapter):
    """When Whisper finds no speech, the transcript must be an empty string — not an error."""
    adapter, model = stt_adapter
    model.transcribe.return_value = ([], None)

    with (
        patch.object(adapter, "_to_wav_16k_mono", return_value=Path("/tmp/fake.wav")),
        patch.object(Path, "unlink"),
    ):
        text, detected = adapter._transcribe_sync(b"silence", language=None)

    assert text == ""
    assert detected is None


def test_transcribe_sync_model_failure_raises_value_error(stt_adapter):
    """If Whisper crashes during transcription, callers get ValueError instead of a raw library error."""
    adapter, model = stt_adapter
    model.transcribe.side_effect = RuntimeError("cuda OOM")

    with (
        patch.object(adapter, "_to_wav_16k_mono", return_value=Path("/tmp/fake.wav")),
        patch.object(Path, "unlink"),
        pytest.raises(ValueError, match="Could not transcribe audio"),
    ):
        adapter._transcribe_sync(b"audio", language=None)

    model.transcribe.assert_called_once()


def test_transcribe_sync_conversion_failure_propagates(stt_adapter):
    """A conversion ValueError must bubble up unchanged so the API can map it to HTTP 400."""
    adapter, model = stt_adapter
    with (
        patch.object(
            adapter,
            "_to_wav_16k_mono",
            side_effect=ValueError("Could not process audio (conversion failed)"),
        ),
        pytest.raises(ValueError, match="conversion failed"),
    ):
        adapter._transcribe_sync(b"audio", language=None)

    model.transcribe.assert_not_called()


def test_transcribe_sync_deletes_temp_wav_even_on_model_error(stt_adapter):
    """Temporary WAV files must be deleted even when transcription fails (no leftover junk)."""
    adapter, model = stt_adapter
    model.transcribe.side_effect = RuntimeError("boom")
    fake_wav = MagicMock(spec=Path)

    with (
        patch.object(adapter, "_to_wav_16k_mono", return_value=fake_wav),
        pytest.raises(ValueError, match="Could not transcribe audio"),
    ):
        adapter._transcribe_sync(b"audio", language=None)

    fake_wav.unlink.assert_called_once_with(missing_ok=True)


# ---------------------------------------------------------------------------
# transcribe (async public API)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transcribe_async_returns_transcript(stt_adapter):
    """The async public method must return the same text that the sync worker produced."""
    adapter, _model = stt_adapter
    with patch.object(
        adapter, "_transcribe_sync", return_value="hi from whisper"
    ) as mock_sync:
        result = await adapter.transcribe(b"audio-bytes", language="de")

    assert result == "hi from whisper"
    mock_sync.assert_called_once_with(b"audio-bytes", "de")


@pytest.mark.asyncio
async def test_transcribe_async_propagates_value_error(stt_adapter):
    """Errors from the sync worker must reach the caller so routes can turn them into HTTP 400."""
    adapter, _model = stt_adapter
    with (
        patch.object(
            adapter,
            "_transcribe_sync",
            side_effect=ValueError("Could not process audio"),
        ),
        pytest.raises(ValueError, match="Could not process audio"),
    ):
        await adapter.transcribe(b"bad", language=None)
