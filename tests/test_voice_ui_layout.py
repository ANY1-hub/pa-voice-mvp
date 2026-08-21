"""Header, mic, and text input stay in the viewport when the chat is long."""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from tests.test_voice_ui_bootstrap import _free_port, _launch_headless

_ROOT = Path(__file__).resolve().parents[1]
_FRONTEND = _ROOT / "frontend"
_FIXTURE_SRC = (
    Path(__file__).resolve().parent / "fixtures" / "voice_ui_layout_check.html"
)
_FIXTURE_DST = _FRONTEND / "_layout_check.html"
_SLACK = 2
_WINDOWS_CHROME = Path("/mnt/c/Program Files/Google/Chrome/Application/chrome.exe")
_WINDOWS_EDGE = Path("/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


def _serve_frontend() -> tuple[ThreadingHTTPServer, str]:
    port = _free_port()
    handler = partial(_QuietHandler, directory=str(_FRONTEND))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}/"


def _windows_browser() -> Path | None:
    for path in (_WINDOWS_CHROME, _WINDOWS_EDGE):
        if path.is_file():
            return path
    return None


def _open_app_with_long_chat(page: Page, origin: str) -> None:
    page.goto(origin, wait_until="domcontentloaded")
    # boot() always ends on auth (this origin has no API). Wait so it cannot
    # hide #appScreen after we reveal the chat chrome.
    page.wait_for_selector("#authError:not(.hidden)", timeout=10_000)
    page.evaluate(
        """() => {
            document.getElementById("authScreen").classList.add("hidden");
            document.getElementById("changePasswordScreen").classList.add("hidden");
            document.getElementById("displayNameScreen").classList.add("hidden");
            document.getElementById("appScreen").classList.remove("hidden");
            const chat = document.getElementById("chatContainer");
            chat.innerHTML = "";
            for (let i = 0; i < 40; i += 1) {
                const el = document.createElement("div");
                el.className = i % 2 === 0 ? "msg user" : "msg jarvis";
                el.innerHTML =
                    '<div class="msg-role"><span>' +
                    (i % 2 === 0 ? "You" : "J.A.R.V.I.S.") +
                    '</span></div><div class="msg-body">Message ' +
                    (i + 1) +
                    " — enough text that a long transcript must scroll inside " +
                    "the chat pane instead of pushing the chrome off screen.</div>";
                chat.appendChild(el);
            }
            chat.scrollTop = chat.scrollHeight;
        }"""
    )


def _assert_chrome_pinned(page: Page) -> None:
    metrics = page.evaluate(
        """() => {
            const viewH = window.innerHeight;
            const viewW = window.innerWidth;
            const box = (el) => {
                const r = el.getBoundingClientRect();
                return {
                    top: r.top, bottom: r.bottom, left: r.left, right: r.right,
                    width: r.width, height: r.height,
                };
            };
            const chat = document.getElementById("chatContainer");
            const last = chat.querySelector(".msg:last-child");
            return {
                viewH, viewW,
                header: box(document.querySelector(".top-bar")),
                footer: box(document.querySelector(".input-area")),
                mic: box(document.getElementById("speakBtn")),
                input: box(document.getElementById("textInput")),
                send: box(document.getElementById("sendBtn")),
                logout: box(document.getElementById("logoutBtn")),
                chat: box(chat),
                last: last ? box(last) : null,
                chatScroll: {
                    scrollHeight: chat.scrollHeight,
                    clientHeight: chat.clientHeight,
                    scrollTop: chat.scrollTop,
                },
                pageScroll: document.documentElement.scrollHeight,
            };
        }"""
    )
    view_h = metrics["viewH"]
    view_w = metrics["viewW"]

    def _fully_in_view(box: dict, name: str) -> None:
        assert box["height"] > 0, f"{name} has no height"
        assert box["top"] >= -_SLACK, f"{name} top {box['top']} is above the viewport"
        assert (
            box["bottom"] <= view_h + _SLACK
        ), f"{name} bottom {box['bottom']} exceeds viewport {view_h}"
        assert box["left"] >= -_SLACK, f"{name} left {box['left']} is off-screen"
        assert (
            box["right"] <= view_w + _SLACK
        ), f"{name} right {box['right']} exceeds viewport {view_w}"

    _fully_in_view(metrics["header"], "header")
    _fully_in_view(metrics["footer"], "input area")
    _fully_in_view(metrics["mic"], "microphone")
    _fully_in_view(metrics["input"], "text input")
    _fully_in_view(metrics["send"], "send")
    _fully_in_view(metrics["logout"], "logout")

    chat = metrics["chatScroll"]
    assert (
        chat["scrollHeight"] > chat["clientHeight"] + 40
    ), "Chat must overflow internally so the page itself does not scroll"
    assert metrics["header"]["bottom"] <= metrics["chat"]["top"] + _SLACK
    assert metrics["chat"]["bottom"] <= metrics["footer"]["top"] + _SLACK
    assert (
        metrics["pageScroll"] <= view_h + 8
    ), f"Document still scrolls ({metrics['pageScroll']} > {view_h})"

    last = metrics["last"]
    assert last is not None
    assert last["bottom"] <= metrics["chat"]["bottom"] + 8
    assert last["top"] < metrics["chat"]["bottom"]


def _assert_with_playwright(origin: str) -> None:
    with sync_playwright() as playwright:
        browser = _launch_headless(playwright)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        # Do not call human :8000. Same contract as the bootstrap e2e test.
        page.add_init_script("window.JARVIS_API_BASE = '';")
        _open_app_with_long_chat(page, origin)
        _assert_chrome_pinned(page)

        page.set_viewport_size({"width": 390, "height": 844})
        page.evaluate(
            "() => { const c = document.getElementById('chatContainer'); "
            "c.scrollTop = c.scrollHeight; }"
        )
        _assert_chrome_pinned(page)
        browser.close()


def _assert_with_windows_browser(browser: Path, origin: str) -> None:
    shutil.copyfile(_FIXTURE_SRC, _FIXTURE_DST)
    url = origin + "_layout_check.html"
    for width, height in ((1280, 800), (390, 844)):
        result = subprocess.run(
            [
                os.fspath(browser),
                "--headless=new",
                "--disable-gpu",
                "--force-device-scale-factor=1",
                f"--window-size={width},{height}",
                "--virtual-time-budget=3000",
                "--dump-dom",
                url,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        assert 'data-layout="ok"' in result.stdout, (
            f"{browser.name} {width}x{height} layout failed: "
            f"{result.stdout[result.stdout.find('data-layout') : result.stdout.find('data-layout') + 80]}"
        )


def test_header_and_input_stay_visible_when_chat_is_long():
    """A long transcript must not push the header or mic/input off screen."""
    server, origin = _serve_frontend()
    try:
        native = _windows_browser()
        if native is not None:
            _assert_with_windows_browser(native, origin)
        else:
            _assert_with_playwright(origin)
    finally:
        _FIXTURE_DST.unlink(missing_ok=True)
        server.shutdown()
