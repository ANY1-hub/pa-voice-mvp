"""Slice-Brief 11: display-name Continue/Weiter/Tovább + composer refocus + notes list.

(1) Preferred-name form submit must work for EN/DE/HU GUI language without
requiring a language switch (live: DE Weiter dead until switch to HU).
(2) After a text reply finishes, focus returns to #textInput.
(3a) Notes sidebar lists every note from GET /api/v1/notes.
"""

from __future__ import annotations

import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from playwright.sync_api import Route, sync_playwright

from tests.test_voice_ui_bootstrap import _free_port, _launch_headless

_FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


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
    # Let boot() finish so it cannot hide displayNameScreen after we reveal it.
    page.wait_for_timeout(400)


def _auth_local_storage(page, display_name: str | None = None) -> None:
    page.evaluate(
        """(displayName) => {
            localStorage.setItem("jarvis_token", "test-token");
            localStorage.setItem("jarvis_user", JSON.stringify({
                id: "u1",
                email: "a@example.com",
                must_change_password: false,
                display_name: displayName,
                is_superuser: false,
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
            }));
        }""",
        display_name,
    )


def _show_display_name(page) -> None:
    page.evaluate("""() => {
            document.getElementById("authScreen")?.classList.add("hidden");
            document.getElementById("changePasswordScreen")?.classList.add("hidden");
            document.getElementById("appScreen")?.classList.add("hidden");
            document.getElementById("displayNameScreen")?.classList.remove("hidden");
            const form = document.getElementById("displayNameForm");
            if (form) {
                form.dataset.busy = "0";
                const btn = form.querySelector("button[type='submit']");
                if (btn) btn.disabled = false;
            }
        }""")


def _enter_app_with_sidebar(page) -> None:
    """Reveal app chrome and bind sidebar listeners (production showApp path)."""
    page.evaluate("""async () => {
            document.getElementById("authScreen")?.classList.add("hidden");
            document.getElementById("changePasswordScreen")?.classList.add("hidden");
            document.getElementById("displayNameScreen")?.classList.add("hidden");
            document.getElementById("appScreen")?.classList.remove("hidden");
            document.querySelector(".chat-column")?.classList.remove("is-empty");
            const mod = await import("./js/sidebar.js");
            mod.initSidebar();
        }""")


@pytest.mark.parametrize(
    "lang,submit_label",
    [("en", "Continue"), ("de", "Weiter"), ("hu", "Tovább")],
)
def test_display_name_submit_works_for_gui_language(lang: str, submit_label: str):
    """Continue/Weiter/Tovább must POST display-name without switching language."""
    server, origin = _serve_frontend()
    posted: list[dict] = []

    def handle_display_name(route: Route) -> None:
        posted.append(json.loads(route.request.post_data or "{}"))
        page.evaluate("() => { window.__displayNamePosted = true; }")
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "id": "u1",
                    "email": "a@example.com",
                    "display_name": "Ada",
                    "must_change_password": False,
                    "is_superuser": False,
                    "timezone": "UTC",
                }
            ),
        )

    try:
        with sync_playwright() as playwright:
            browser = _launch_headless(playwright)
            page = browser.new_page()
            _open(page, origin)
            page.route("**/api/v1/auth/display-name", handle_display_name)
            page.route(
                "**/api/v1/auth/timezone",
                lambda route: route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "id": "u1",
                            "email": "a@example.com",
                            "display_name": "Ada",
                            "must_change_password": False,
                            "is_superuser": False,
                            "timezone": "UTC",
                        }
                    ),
                ),
            )
            page.route(
                "**/api/v1/auth/me",
                lambda route: route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "id": "u1",
                            "email": "a@example.com",
                            "display_name": "Ada",
                            "must_change_password": False,
                            "is_superuser": False,
                            "timezone": "UTC",
                        }
                    ),
                ),
            )
            _auth_local_storage(page, display_name=None)
            _show_display_name(page)
            page.locator(f"#displayNameScreen .lang-flag[data-lang='{lang}']").click()
            page.wait_for_timeout(150)
            label = (
                page.locator("#displayNameForm button[type='submit']")
                .inner_text()
                .strip()
            )
            assert label == submit_label, f"expected {submit_label!r}, got {label!r}"
            page.fill("#displayNameInput", "Ada")
            page.locator("#displayNameForm button[type='submit']").click()
            page.wait_for_function(
                "() => window.__displayNamePosted === true || document.getElementById('displayNameForm')?.dataset.busy === '1'",
                timeout=3_000,
            )
            page.wait_for_timeout(400)
            browser.close()
    finally:
        server.shutdown()

    assert (
        posted
    ), f"GUI lang={lang} submit ({submit_label}) did not POST /api/v1/auth/display-name"
    assert posted[0].get("display_name") == "Ada"


def test_composer_refocuses_after_text_reply():
    """After Jarvis finishes a text reply, #textInput must receive focus."""
    server, origin = _serve_frontend()
    try:
        with sync_playwright() as playwright:
            browser = _launch_headless(playwright)
            page = browser.new_page()
            _open(page, origin)
            page.route(
                "**/api/v1/chat/text",
                lambda route: route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "transcript": "hello",
                            "response": "hi there",
                            "audio_base64": None,
                        }
                    ),
                ),
            )
            _auth_local_storage(page, display_name="Ada")
            _enter_app_with_sidebar(page)
            page.fill("#textInput", "hello")
            page.click("#sendBtn")
            page.wait_for_selector(".msg.jarvis", timeout=5_000)
            page.wait_for_timeout(300)
            focused = page.evaluate(
                "() => document.activeElement && document.activeElement.id"
            )
            browser.close()
    finally:
        server.shutdown()

    assert (
        focused == "textInput"
    ), f"expected #textInput focused after reply, got {focused!r}"


def test_sidebar_notes_render_every_api_note():
    """Notes sidebar must list every note returned by GET /api/v1/notes."""
    server, origin = _serve_frontend()
    try:
        with sync_playwright() as playwright:
            browser = _launch_headless(playwright)
            page = browser.new_page()
            _open(page, origin)
            page.route(
                "**/api/v1/notes**",
                lambda route: route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "notes": [
                                {
                                    "id": "1",
                                    "title": None,
                                    "content": "alpha note content",
                                    "created_at": "2026-09-16T10:00:00Z",
                                    "tags": [],
                                },
                                {
                                    "id": "2",
                                    "title": "Beta",
                                    "content": "beta body",
                                    "created_at": "2026-09-16T11:00:00Z",
                                    "tags": [],
                                },
                                {
                                    "id": "3",
                                    "title": None,
                                    "content": "gamma note content",
                                    "created_at": "2026-09-16T12:00:00Z",
                                    "tags": [],
                                },
                            ]
                        }
                    ),
                ),
            )
            _auth_local_storage(page, display_name="Ada")
            _enter_app_with_sidebar(page)
            page.click("#notesBtn")
            page.wait_for_selector("#sidebarList li", timeout=5_000)
            items = page.locator("#sidebarList li button.sidebar-item").count()
            browser.close()
    finally:
        server.shutdown()

    assert items == 3, f"sidebar silently dropped notes; got {items} items"
