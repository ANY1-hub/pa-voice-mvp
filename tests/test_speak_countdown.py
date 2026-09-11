"""Slice-Brief 9 UX: remaining WAV-budget seconds on the Speak button.

16 kHz mono 16-bit PCM → 32000 bytes/s. Floor(MAX_AUDIO_BYTES / 32000) = 327
so an auto-stopped clip stays under the 10 MB upload cap. Idle: mic visible,
countdown hidden. Recording: digits visible, mic hidden.
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from src.services.orchestrator import MAX_AUDIO_BYTES
from tests.test_voice_ui_layout import (
    _launch_headless,
    _open_app_with_long_chat,
    _serve_frontend,
)

_FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
_WAV_BYTES_PER_SEC = 16000 * 2
_WAV_BUDGET_SECONDS = MAX_AUDIO_BYTES // _WAV_BYTES_PER_SEC

_FAKE_MIC = """
(() => {
    window.MediaRecorder = class {
        constructor() {
            this.state = "inactive";
            this.ondataavailable = null;
            this.onstop = null;
            this.onerror = null;
        }
        static isTypeSupported() { return false; }
        start() { this.state = "recording"; }
        stop() {
            this.state = "inactive";
            if (this.onstop) this.onstop();
        }
    };
    const fakeGetUserMedia = async () => new MediaStream();
    const proto = window.MediaDevices && MediaDevices.prototype;
    if (proto) {
        Object.defineProperty(proto, "getUserMedia", {
            configurable: true,
            enumerable: true,
            writable: true,
            value: fakeGetUserMedia,
        });
    }
    if (navigator.mediaDevices) {
        try {
            navigator.mediaDevices.getUserMedia = fakeGetUserMedia;
        } catch (err) { /* prototype patch is enough */ }
    }
})();
"""


def test_wav_budget_seconds_fits_ten_mb_wav():
    """327 s of 16 kHz mono 16-bit WAV is the largest integer under 10 MiB."""
    assert _WAV_BUDGET_SECONDS == 327
    assert _WAV_BUDGET_SECONDS * _WAV_BYTES_PER_SEC <= MAX_AUDIO_BYTES
    assert (_WAV_BUDGET_SECONDS + 1) * _WAV_BYTES_PER_SEC > MAX_AUDIO_BYTES


def test_speak_button_markup_has_countdown_slot():
    """#speakBtn must contain #speakCountdown (hidden until recording)."""
    html = (_FRONTEND / "index.html").read_text(encoding="utf-8")
    assert 'id="speakBtn"' in html
    assert 'id="speakCountdown"' in html


def test_audio_js_exports_wav_budget_seconds():
    """Frontend must export the same floor(bytes/rate) the button counts down."""
    src = (_FRONTEND / "js" / "audio.js").read_text(encoding="utf-8")
    assert "export function wavBudgetSeconds" in src


def test_idle_speak_button_hides_countdown_shows_mic():
    """Idle Speak control shows the mic, not the remaining-seconds digit."""
    server, origin = _serve_frontend()
    try:
        with sync_playwright() as playwright:
            browser = _launch_headless(playwright)
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.add_init_script("window.JARVIS_API_BASE = '';")
            _open_app_with_long_chat(page, origin)
            expect(page.locator("#speakCountdown")).to_have_count(1)
            expect(page.locator("#speakCountdown")).to_be_hidden()
            expect(page.locator("#speakBtn .mic-icon")).to_be_visible()
            browser.close()
    finally:
        server.shutdown()


def test_recording_shows_wav_budget_seconds_on_speak_button():
    """Click-to-speak must show remaining whole seconds and hide the mic icon."""
    server, origin = _serve_frontend()
    try:
        with sync_playwright() as playwright:
            browser = _launch_headless(playwright)
            context = browser.new_context(
                permissions=["microphone"],
                viewport={"width": 1280, "height": 800},
            )
            page = context.new_page()
            page.add_init_script("window.JARVIS_API_BASE = '';")
            page.add_init_script(_FAKE_MIC)
            _open_app_with_long_chat(page, origin)
            page.evaluate(_FAKE_MIC)
            page.locator("#speakBtn").click()
            countdown = page.locator("#speakCountdown")
            expect(countdown).to_be_visible()
            text = countdown.inner_text().strip()
            assert text.isdigit(), f"countdown must be remaining seconds, got {text!r}"
            assert int(text) == _WAV_BUDGET_SECONDS
            expect(page.locator("#speakBtn .mic-icon")).to_be_hidden()
            browser.close()
    finally:
        server.shutdown()
