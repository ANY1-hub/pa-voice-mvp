"""Empty Mongo users collection → Voice UI must show SuperUser setup.

Human development is UI :5500 + API :8000 — this file must not bind those
ports. It starts one uvicorn on an ephemeral port (UI+API, like Docker) and
sets ``window.JARVIS_API_BASE = ''`` so the page talks to that server only.
Engine: ``JARVIS_E2E_BROWSER`` (default ``chromium``). If boot() leaves
Sign-in on screen, this test fails.
"""

from __future__ import annotations

import os
import socket
import threading
import time
import urllib.error
import urllib.request
import uuid

import httpx
import pytest
import uvicorn
from playwright.sync_api import Browser, Playwright, expect, sync_playwright
from playwright.sync_api import Error as PlaywrightError

from src.main import app
from tests.conftest import wipe_users

E2E_BROWSER_ENV = "JARVIS_E2E_BROWSER"
E2E_BROWSERS = ("chromium", "firefox", "webkit")


def e2e_browser_name() -> str:
    """Return the configured headless engine name, or raise if unknown."""
    name = os.environ.get(E2E_BROWSER_ENV, "chromium").strip().lower()
    if name not in E2E_BROWSERS:
        raise ValueError(
            f"{E2E_BROWSER_ENV}={name!r} is not a supported headless engine. "
            f"Use one of: {', '.join(E2E_BROWSERS)}"
        )
    return name


def e2e_launch_kwargs(name: str) -> list[dict]:
    """Bundled Playwright build first, then a same-family system browser.

    ``pip install playwright`` does not download an engine. On Windows the
    chromium family is usually already present as Chrome or Edge.
    """
    if name == "chromium":
        return [{}, {"channel": "chrome"}, {"channel": "msedge"}]
    if name == "firefox":
        return [{}, {"channel": "firefox"}]
    return [{}]


def _missing_engine_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return (
        "executable doesn't exist" in text
        or "is not found" in text
        or "wasn't found" in text
        or "could not find" in text
    )


def _launch_headless(playwright: Playwright) -> Browser:
    name = e2e_browser_name()
    browser_type = getattr(playwright, name)
    last_error: BaseException | None = None
    for kwargs in e2e_launch_kwargs(name):
        try:
            browser = browser_type.launch(headless=True, **kwargs)
        except PlaywrightError as exc:
            if not _missing_engine_error(exc):
                raise
            last_error = exc
            continue
        used = kwargs.get("channel") or f"playwright {name}"
        print(f"Voice UI e2e headless engine: {name} ({used})", flush=True)
        return browser
    raise RuntimeError(
        f"No headless engine for {name!r}. "
        f"The Playwright Python package does not include the browser binary. "
        f"Install it with: playwright install {name}"
        + (
            " (or install Google Chrome / Microsoft Edge for the chromium family)"
            if name == "chromium"
            else ""
        )
    ) from last_error


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_healthy(origin: str, timeout_s: float = 20.0) -> None:
    deadline = time.time() + timeout_s
    last_error = "no attempt"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{origin}/health", timeout=1) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)
        time.sleep(0.1)
    raise RuntimeError(f"uvicorn at {origin} did not become healthy: {last_error}")


def test_e2e_browser_name_rejects_unknown_engine(monkeypatch: pytest.MonkeyPatch):
    """A brand alias such as 'chrome' must not silently map to an engine."""
    monkeypatch.setenv(E2E_BROWSER_ENV, "chrome")
    with pytest.raises(ValueError, match="chrome"):
        e2e_browser_name()


def test_chromium_family_tries_system_chrome_and_edge():
    """Missing Playwright Chromium must still be able to use Chrome or Edge."""
    attempts = e2e_launch_kwargs("chromium")
    assert attempts[0] == {}
    assert {"channel": "chrome"} in attempts
    assert {"channel": "msedge"} in attempts


def test_backend_serves_voice_ui(client):
    """The API process must serve index.html so the browser can boot on this origin."""
    response = client.get("/")
    assert response.status_code == 200
    assert "registerForm" in response.text
    assert "Create SuperUser" in response.text


def test_served_js_calls_versioned_bootstrap_and_phrases(client):
    """Stale short paths (/bootstrap-status, /phrases) must not be what the UI fetches."""
    auth_js = client.get("/js/auth.js")
    app_js = client.get("/js/app.js")
    assert auth_js.status_code == 200
    assert app_js.status_code == 200
    assert "/api/v1/auth/bootstrap-status" in auth_js.text
    assert "/api/v1/skills/phrases" in app_js.text
    assert 'fetch("/bootstrap-status"' not in auth_js.text
    assert "fetch(`/bootstrap-status`" not in auth_js.text
    assert 'fetch("/phrases"' not in app_js.text


def test_voice_ui_js_is_not_cached(client):
    """Browsers must revalidate Voice UI JS or they keep both auth forms on screen."""
    response = client.get("/js/auth.js")
    assert response.status_code == 200
    cache = response.headers.get("cache-control", "").lower()
    assert "no-store" in cache


def test_empty_db_shows_superuser_form_and_creates_account():
    """Wipe users, open the Voice UI; Create SuperUser must be the visible form.

    If ``boot()`` never switches off the default Sign-in markup, this fails.
    """
    wipe_users()
    port = _free_port()
    origin = f"http://127.0.0.1:{port}"
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        _wait_healthy(origin)
        with httpx.Client(base_url=origin) as http:
            status = http.get("/api/v1/auth/bootstrap-status")
            assert status.status_code == 200
            assert status.json()["needs_bootstrap"] is True

        email = f"ui-super-{uuid.uuid4().hex[:8]}@example.com"
        password = "SecurePass123!"

        with sync_playwright() as playwright:
            browser = _launch_headless(playwright)
            page = browser.new_page()
            # Do not use human ports 5500/8000. This uvicorn is the API.
            page.add_init_script("window.JARVIS_API_BASE = '';")
            page.goto(origin + "/", wait_until="domcontentloaded")

            expect(page.locator("#registerForm")).to_be_visible(timeout=15_000)
            expect(page.locator("#loginForm")).to_be_hidden()
            expect(page.get_by_role("button", name="Create SuperUser")).to_be_visible()

            page.locator("#regEmail").fill(email)
            page.locator("#regPassword").fill(password)
            page.locator("#regPassword2").fill(password)
            page.get_by_role("button", name="Create SuperUser").click()

            expect(page.locator("#loginForm")).to_be_visible(timeout=15_000)
            expect(page.locator("#registerForm")).to_be_hidden()
            browser.close()

        with httpx.Client(base_url=origin) as http:
            after = http.get("/api/v1/auth/bootstrap-status")
            assert after.json()["needs_bootstrap"] is False
            login = http.post(
                "/api/v1/auth/login",
                json={"email": email, "password": password},
            )
            assert login.status_code == 200, login.text
            me = http.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {login.json()['access_token']}"},
            )
            assert me.status_code == 200
            assert me.json()["is_superuser"] is True
            assert me.json()["email"] == email.lower()
    finally:
        server.should_exit = True
        thread.join(timeout=8)
