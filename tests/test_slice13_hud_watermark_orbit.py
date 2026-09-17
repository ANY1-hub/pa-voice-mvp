"""Slice-Brief 13: chat HUD watermark + mic recording orbit (UI-only).

(1) Faint JARVIS-style concentric HUD ring watermark behind chat bubbles
    (asset ``frontend/assets/hud-ring.png``), pointer-events none, not covering text.
(2) While ``#speakBtn`` is recording (``.recording`` / isRecording flow), a tiny
    orbit ring emerges from behind the mic, rotates for the whole recording,
    then shrinks/hides behind the button when recording ends.

Controls: not recording → no visible orbit; voice send path still posts.
"""

from __future__ import annotations

import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import Route, sync_playwright

from tests.test_voice_ui_bootstrap import _free_port, _launch_headless

_FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
_RING = "hud-ring.png"


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


def _serve_frontend() -> tuple[ThreadingHTTPServer, str]:
    port = _free_port()
    handler = partial(_QuietHandler, directory=str(_FRONTEND))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{port}"


def _open(page, origin: str) -> None:
    page.add_init_script("window.JARVIS_API_BASE = '';")
    page.goto(origin + "/", wait_until="domcontentloaded")
    page.wait_for_selector("#authScreen", timeout=10_000)
    page.wait_for_timeout(400)


def _auth_local_storage(page) -> None:
    page.evaluate("""() => {
            localStorage.setItem("jarvis_token", "test-token");
            localStorage.setItem("jarvis_user", JSON.stringify({
                id: "u1",
                email: "a@example.com",
                must_change_password: false,
                display_name: "Ada",
                is_superuser: false,
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
            }));
        }""")


def _enter_app_with_chat(page) -> None:
    """Reveal app chrome with a short transcript so the chat pane is visible."""
    page.evaluate("""() => {
            document.getElementById("authScreen")?.classList.add("hidden");
            document.getElementById("changePasswordScreen")?.classList.add("hidden");
            document.getElementById("displayNameScreen")?.classList.add("hidden");
            document.getElementById("appScreen")?.classList.remove("hidden");
            document.querySelector(".chat-column")?.classList.remove("is-empty");
            const chat = document.getElementById("chatContainer");
            if (chat) {
                chat.innerHTML =
                    '<div class="msg jarvis"><div class="msg-role"><span>J.A.R.V.I.S.</span></div>' +
                    '<div class="msg-body">Hello Ada</div></div>';
            }
        }""")


def _patch_mic_live(page) -> None:
    """Patch mic APIs after load so speakBtn can enter/leave .recording."""
    page.evaluate("""() => {
            class FakeMediaRecorder {
                constructor(stream, opts) {
                    this.stream = stream;
                    this.state = "inactive";
                    this.ondataavailable = null;
                    this.onstop = null;
                    this.onerror = null;
                    this.mimeType = (opts && opts.mimeType) || "audio/webm";
                }
                static isTypeSupported() { return true; }
                start() { this.state = "recording"; }
                stop() {
                    this.state = "inactive";
                    if (this.ondataavailable) {
                        this.ondataavailable({
                            data: new Blob([new Uint8Array(64)], { type: this.mimeType }),
                        });
                    }
                    // Product assigns async onstop — call and ignore returned promise.
                    if (this.onstop) this.onstop();
                }
            }
            window.MediaRecorder = FakeMediaRecorder;
            const Proto = window.AudioContext || window.webkitAudioContext;
            const decode = async function () {
                return this.createBuffer(1, 1600, 16000);
            };
            Proto.prototype.decodeAudioData = decode;
            navigator.mediaDevices.getUserMedia = async () => {
                const ctx = new Proto();
                return ctx.createMediaStreamDestination().stream;
            };
        }""")


def _watermark_info(page) -> dict:
    return page.evaluate("""() => {
            const chat = document.getElementById("chatContainer");
            const column = document.querySelector(".chat-column");
            const el = document.querySelector(
                "#chatHudWatermark, .chat-hud-watermark, [data-testid='chat-hud-watermark']"
            );
            if (!el) return { present: false };
            const style = getComputedStyle(el);
            const bg = style.backgroundImage || "";
            const img = el.tagName === "IMG" ? el.getAttribute("src") || "" : "";
            const nestedImg = el.querySelector("img")?.getAttribute("src") || "";
            const usesRing =
                bg.includes("hud-ring") ||
                img.includes("hud-ring") ||
                nestedImg.includes("hud-ring");
            const inChat =
                !!(chat && (chat === el || chat.contains(el))) ||
                !!(column && (column === el || column.contains(el)));
            return {
                present: true,
                usesRing,
                pointerEvents: style.pointerEvents,
                opacity: Number(style.opacity),
                visibility: style.visibility,
                display: style.display,
                inChat,
            };
        }""")


def _orbit_info(page) -> dict:
    return page.evaluate("""() => {
            const btn = document.getElementById("speakBtn");
            const el = document.querySelector(
                "#speakOrbit, .speak-orbit, [data-testid='speak-orbit']"
            );
            if (!el) {
                return {
                    present: false,
                    visible: false,
                    recording: !!btn?.classList.contains("recording"),
                };
            }
            const style = getComputedStyle(el);
            const bg = style.backgroundImage || "";
            const img = el.tagName === "IMG" ? el.getAttribute("src") || "" : "";
            const nestedImg = el.querySelector("img")?.getAttribute("src") || "";
            const usesRing =
                bg.includes("hud-ring") ||
                img.includes("hud-ring") ||
                nestedImg.includes("hud-ring");
            const rect = el.getBoundingClientRect();
            const visible =
                style.display !== "none" &&
                style.visibility !== "hidden" &&
                Number(style.opacity) > 0.02 &&
                rect.width > 0 &&
                rect.height > 0;
            const nearMic = !!(
                btn &&
                (btn === el || btn.contains(el) || btn.parentElement?.contains(el))
            );
            return {
                present: true,
                visible,
                usesRing,
                nearMic,
                recording: !!btn?.classList.contains("recording"),
                pointerEvents: style.pointerEvents,
            };
        }""")


def test_chat_hud_watermark_present_behind_bubbles():
    """Chat area must show a faint hud-ring watermark behind messages."""
    server, origin = _serve_frontend()
    try:
        with sync_playwright() as playwright:
            browser = _launch_headless(playwright)
            page = browser.new_page()
            _open(page, origin)
            _auth_local_storage(page)
            _enter_app_with_chat(page)
            info = _watermark_info(page)
            browser.close()
    finally:
        server.shutdown()

    assert (
        info.get("present") is True
    ), "expected #chatHudWatermark / .chat-hud-watermark in the chat chrome"
    assert info.get("inChat") is True, "watermark must live in the chat column/area"
    assert (
        info.get("usesRing") is True
    ), f"watermark must use assets/{_RING}, got {info!r}"
    assert (
        info.get("pointerEvents") == "none"
    ), f"watermark must not capture clicks, got pointer-events={info.get('pointerEvents')!r}"
    assert info.get("display") != "none"
    assert info.get("visibility") != "hidden"
    assert info.get("opacity", 0) > 0, "watermark must be faintly visible"
    assert (
        info.get("opacity", 1) < 0.55
    ), f"watermark must stay faint, opacity={info.get('opacity')!r}"


def test_speak_orbit_hidden_when_not_recording():
    """Control: mic orbit must not be visibly active when not recording."""
    server, origin = _serve_frontend()
    try:
        with sync_playwright() as playwright:
            browser = _launch_headless(playwright)
            page = browser.new_page()
            _open(page, origin)
            _auth_local_storage(page)
            _enter_app_with_chat(page)
            info = _orbit_info(page)
            recording = page.evaluate(
                "() => document.getElementById('speakBtn')?.classList.contains('recording')"
            )
            browser.close()
    finally:
        server.shutdown()

    assert recording is False
    assert (
        info.get("visible") is not True
    ), f"orbit must be hidden when idle, got {info!r}"


def test_speak_orbit_appears_with_recording_class_and_hides_without():
    """``.recording`` on #speakBtn must reveal a hud-ring orbit; removing hides it.

    Product may drive visibility via CSS on ``.composer-mic.recording`` (preferred)
    or by toggling the orbit in JS when isRecording flips.
    """
    server, origin = _serve_frontend()
    try:
        with sync_playwright() as playwright:
            browser = _launch_headless(playwright)
            page = browser.new_page()
            _open(page, origin)
            _auth_local_storage(page)
            _enter_app_with_chat(page)

            idle = _orbit_info(page)
            page.evaluate(
                "() => document.getElementById('speakBtn')?.classList.add('recording')"
            )
            during = _orbit_info(page)
            page.evaluate(
                "() => document.getElementById('speakBtn')?.classList.remove('recording')"
            )
            after = _orbit_info(page)
            browser.close()
    finally:
        server.shutdown()

    assert idle.get("visible") is not True, f"idle orbit leaked: {idle!r}"
    assert (
        during.get("present") is True
    ), "expected #speakOrbit / .speak-orbit near the mic"
    assert (
        during.get("visible") is True
    ), f"orbit must show while #speakBtn.recording: {during!r}"
    assert (
        during.get("usesRing") is True
    ), f"orbit must use assets/{_RING}, got {during!r}"
    assert (
        during.get("nearMic") is True
    ), f"orbit must sit on/near #speakBtn: {during!r}"
    assert (
        during.get("pointerEvents") == "none"
    ), f"orbit must not block mic clicks: {during!r}"
    assert (
        after.get("visible") is not True
    ), f"orbit must hide when recording class is removed: {after!r}"


def test_recording_click_toggles_recording_class_and_voice_posts():
    """Control: speak toggle still enters .recording and voice POST still fires."""
    server, origin = _serve_frontend()
    voice_posts: list[str] = []

    def handle_voice(route: Route) -> None:
        voice_posts.append(route.request.method)
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "transcript": "hello",
                    "response": "hi there",
                    "audio_base64": None,
                }
            ),
        )

    try:
        with sync_playwright() as playwright:
            browser = _launch_headless(playwright)
            page = browser.new_page()
            _open(page, origin)
            page.route("**/api/v1/chat/voice", handle_voice)
            _auth_local_storage(page)
            _enter_app_with_chat(page)
            _patch_mic_live(page)

            page.click("#speakBtn")
            page.wait_for_function(
                "() => document.getElementById('speakBtn')?.classList.contains('recording')",
                timeout=8_000,
            )
            page.click("#speakBtn")
            page.wait_for_function(
                "() => !document.getElementById('speakBtn')?.classList.contains('recording')",
                timeout=8_000,
            )
            page.wait_for_timeout(1500)
            browser.close()
    finally:
        server.shutdown()

    assert (
        voice_posts
    ), "expected POST /api/v1/chat/voice after stop — orbit UI must not break voice send"
