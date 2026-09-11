"""Slice-Brief 9 UX: remaining WAV-budget seconds on the Speak button.

16 kHz mono 16-bit PCM → 32000 bytes/s. Floor(MAX_AUDIO_BYTES / 32000) = 327
so an auto-stopped clip stays under the 10 MB upload cap. Idle and early
recording: mic visible, countdown hidden. Digits only in the last 20 seconds.
"""

from __future__ import annotations

import re
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
    assert "export function speakCountdownShouldShow" in src
    assert "SPEAK_COUNTDOWN_VISIBLE_SECONDS = 20" in src


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


def test_speak_countdown_helper_only_last_twenty_seconds():
    """Digits belong in the last 20 s of WAV budget, not at 327 or 21."""
    server, origin = _serve_frontend()
    try:
        with sync_playwright() as playwright:
            browser = _launch_headless(playwright)
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(origin, wait_until="domcontentloaded")
            shown = page.evaluate("""async () => {
                    const m = await import("./js/audio.js?v=2026-09-11-speak-countdown-20");
                    return {
                        vis: m.SPEAK_COUNTDOWN_VISIBLE_SECONDS,
                        full: m.speakCountdownShouldShow(327),
                        early: m.speakCountdownShouldShow(21),
                        late: m.speakCountdownShouldShow(20),
                        one: m.speakCountdownShouldShow(1),
                        zero: m.speakCountdownShouldShow(0),
                    };
                }""")
            assert shown["vis"] == 20
            assert shown["full"] is False
            assert shown["early"] is False
            assert shown["late"] is True
            assert shown["one"] is True
            assert shown["zero"] is True
            browser.close()
    finally:
        server.shutdown()


def test_recording_keeps_mic_until_last_twenty_seconds():
    """Click-to-speak must keep the mic; digits stay hidden at the start of the budget."""
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
            expect(page.locator("#speakBtn")).to_have_class(
                re.compile(r"\brecording\b")
            )
            expect(page.locator("#speakCountdown")).to_be_hidden()
            expect(page.locator("#speakBtn .mic-icon")).to_be_visible()
            browser.close()
    finally:
        server.shutdown()
