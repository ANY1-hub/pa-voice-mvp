"""Slice-Brief 14: recording rec-dot must not shove the mic icon.

While recording, ``#recIndicator.rec-dot`` must sit on the mic circuit
(absolute, e.g. top-right) and ``.mic-icon`` must stay centered — not shift
because ``.composer-mic > .rec-dot { position: relative }`` puts the dot in
the flex/flow row.

Controls: idle mic center baseline; Slice 13 orbit idle/recording contract
still holds (smoke via orbit selectors).
"""

from __future__ import annotations

import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

from tests.test_voice_ui_bootstrap import _free_port, _launch_headless

_FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
# Mic is 36px; allowing ~1.5px drift for subpixel rounding.
_CENTER_TOLERANCE_PX = 1.5


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


def _enter_app(page) -> None:
    page.evaluate("""() => {
            document.getElementById("authScreen")?.classList.add("hidden");
            document.getElementById("changePasswordScreen")?.classList.add("hidden");
            document.getElementById("displayNameScreen")?.classList.add("hidden");
            document.getElementById("appScreen")?.classList.remove("hidden");
            document.querySelector(".chat-column")?.classList.remove("is-empty");
        }""")


def _mic_layout(page) -> dict:
    return page.evaluate("""() => {
            const btn = document.getElementById("speakBtn");
            const icon = btn?.querySelector(".mic-icon");
            const dot = document.getElementById("recIndicator");
            if (!btn || !icon || !dot) {
                return { ok: false };
            }
            const b = btn.getBoundingClientRect();
            const i = icon.getBoundingClientRect();
            const d = dot.getBoundingClientRect();
            const ds = getComputedStyle(dot);
            return {
                ok: true,
                recording: btn.classList.contains("recording"),
                dotHidden: dot.classList.contains("hidden"),
                iconCenterX: i.left + i.width / 2,
                iconCenterY: i.top + i.height / 2,
                btnCenterX: b.left + b.width / 2,
                btnCenterY: b.top + b.height / 2,
                btnLeft: b.left,
                btnTop: b.top,
                btnRight: b.right,
                btnBottom: b.bottom,
                dotPosition: ds.position,
                dotTop: ds.top,
                dotRight: ds.right,
                dotOpacity: Number(ds.opacity),
                dotDisplay: ds.display,
                dotVisibility: ds.visibility,
                dotLeft: d.left,
                dotRightEdge: d.right,
                dotTopEdge: d.top,
                transition: ds.transitionProperty + "|" + ds.transitionDuration,
            };
        }""")


def test_idle_mic_icon_stays_centered_control():
    """Control: idle mic-icon is centered in #speakBtn (baseline)."""
    server, origin = _serve_frontend()
    try:
        with sync_playwright() as playwright:
            browser = _launch_headless(playwright)
            page = browser.new_page()
            _open(page, origin)
            _auth_local_storage(page)
            _enter_app(page)
            info = _mic_layout(page)
            browser.close()
    finally:
        server.shutdown()

    assert info.get("ok") is True
    assert info.get("recording") is False
    assert abs(info["iconCenterX"] - info["btnCenterX"]) <= _CENTER_TOLERANCE_PX, info
    assert abs(info["iconCenterY"] - info["btnCenterY"]) <= _CENTER_TOLERANCE_PX, info


def test_recording_rec_dot_does_not_shift_mic_icon():
    """Visible rec-dot must not push .mic-icon off the button center."""
    server, origin = _serve_frontend()
    try:
        with sync_playwright() as playwright:
            browser = _launch_headless(playwright)
            page = browser.new_page()
            _open(page, origin)
            _auth_local_storage(page)
            _enter_app(page)

            idle = _mic_layout(page)
            page.evaluate("""() => {
                    const btn = document.getElementById("speakBtn");
                    const dot = document.getElementById("recIndicator");
                    btn?.classList.add("recording");
                    dot?.classList.remove("hidden");
                }""")
            page.wait_for_timeout(50)
            recording = _mic_layout(page)
            browser.close()
    finally:
        server.shutdown()

    assert idle.get("ok") and recording.get("ok")
    assert recording.get("dotHidden") is False
    assert recording.get("recording") is True

    assert (
        abs(recording["iconCenterX"] - recording["btnCenterX"]) <= _CENTER_TOLERANCE_PX
    ), f"mic icon not centered while recording: {recording!r}"
    assert (
        abs(recording["iconCenterY"] - recording["btnCenterY"]) <= _CENTER_TOLERANCE_PX
    ), f"mic icon vertical center drifted: {recording!r}"
    assert (
        abs(recording["iconCenterX"] - idle["iconCenterX"]) <= _CENTER_TOLERANCE_PX
    ), (
        f"mic icon X jumped when rec-dot appeared "
        f"(idle={idle['iconCenterX']}, recording={recording['iconCenterX']})"
    )
    assert (
        abs(recording["iconCenterY"] - idle["iconCenterY"]) <= _CENTER_TOLERANCE_PX
    ), (
        f"mic icon Y jumped when rec-dot appeared "
        f"(idle={idle['iconCenterY']}, recording={recording['iconCenterY']})"
    )


def test_recording_rec_dot_is_absolute_on_circuit():
    """rec-dot must be position:absolute on the mic circuit (not in flow)."""
    server, origin = _serve_frontend()
    try:
        with sync_playwright() as playwright:
            browser = _launch_headless(playwright)
            page = browser.new_page()
            _open(page, origin)
            _auth_local_storage(page)
            _enter_app(page)
            page.evaluate("""() => {
                    document.getElementById("speakBtn")?.classList.add("recording");
                    document.getElementById("recIndicator")?.classList.remove("hidden");
                }""")
            page.wait_for_timeout(50)
            info = _mic_layout(page)
            browser.close()
    finally:
        server.shutdown()

    assert info.get("ok") is True
    assert info.get("dotPosition") == "absolute", (
        f"expected absolute rec-dot on circuit, got position={info.get('dotPosition')!r} "
        f"(relative overrides shove the mic). full={info!r}"
    )
    assert info.get("dotDisplay") != "none"
    assert info.get("dotVisibility") != "hidden"
    # Dot should sit in the upper-right of the button circuit.
    assert info["dotRightEdge"] <= info["btnRight"] + 2, info
    assert info["dotTopEdge"] >= info["btnTop"] - 2, info
    assert info["dotLeft"] >= info["btnLeft"] - 2, info
    assert (
        info["dotLeft"] > info["btnCenterX"] - 2
    ), f"rec-dot should sit toward the right of the circuit: {info!r}"


def test_slice13_orbit_still_toggles_with_recording_control():
    """Control: Slice 13 speak-orbit still appears with .recording and hides without."""
    server, origin = _serve_frontend()
    try:
        with sync_playwright() as playwright:
            browser = _launch_headless(playwright)
            page = browser.new_page()
            _open(page, origin)
            _auth_local_storage(page)
            _enter_app(page)

            def orbit_visible() -> bool:
                return page.evaluate("""() => {
                        const el = document.querySelector(
                            "#speakOrbit, .speak-orbit, [data-testid='speak-orbit']"
                        );
                        if (!el) return false;
                        const s = getComputedStyle(el);
                        const r = el.getBoundingClientRect();
                        return (
                            s.display !== "none" &&
                            s.visibility !== "hidden" &&
                            Number(s.opacity) > 0.02 &&
                            r.width > 0 &&
                            r.height > 0
                        );
                    }""")

            idle = orbit_visible()
            page.evaluate(
                "() => document.getElementById('speakBtn')?.classList.add('recording')"
            )
            during = orbit_visible()
            page.evaluate(
                "() => document.getElementById('speakBtn')?.classList.remove('recording')"
            )
            after = orbit_visible()
            browser.close()
    finally:
        server.shutdown()

    assert idle is False
    assert during is True
    assert after is False
