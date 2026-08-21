"""Human UI :5500 must call API :8000; tests must not probe the static server."""

from pathlib import Path

_CONFIG = Path(__file__).resolve().parents[1] / "frontend" / "js" / "config.js"
_AUTH = Path(__file__).resolve().parents[1] / "frontend" / "js" / "auth.js"
_BOOTSTRAP = Path(__file__).resolve().parent / "test_voice_ui_bootstrap.py"
_LAYOUT = Path(__file__).resolve().parent / "test_voice_ui_layout.py"


def test_dev_ports_are_fixed_and_tests_opt_in_to_their_own_api():
    """5500/8000 are the human pair. Pytest injects JARVIS_API_BASE instead."""
    config = _CONFIG.read_text(encoding="utf-8")
    auth = _AUTH.read_text(encoding="utf-8")
    bootstrap = _BOOTSTRAP.read_text(encoding="utf-8")

    assert 'DEV_UI_PORT = "5500"' in config
    assert 'DEV_API_PORT = "8000"' in config
    assert "window.JARVIS_API_BASE" in config
    assert "apiBaseCandidates" in config
    assert "return [defaultApiBase(loc)]" in config
    assert 'const bases = [""]' not in config

    assert "apiBaseCandidates()" not in auth
    assert "defaultApiBase()" in auth

    assert "window.JARVIS_API_BASE = ''" in bootstrap
    assert "add_init_script" in bootstrap

    layout = _LAYOUT.read_text(encoding="utf-8")
    assert "window.JARVIS_API_BASE = ''" in layout
    assert "add_init_script" in layout


def test_due_poll_does_not_skip_whole_tick_while_a_text_turn_runs():
    """An open chat that is sending text must still claim due reminders."""
    app = (
        Path(__file__).resolve().parents[1] / "frontend" / "js" / "app.js"
    ).read_text(encoding="utf-8")
    assert "if (isRecording || isProcessing) return;" not in app
    assert "if (isRecording) return;" in app
    assert "if (!on) tickDueReminders();" in app
