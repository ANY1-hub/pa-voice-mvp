"""Slice-Brief 16: MVP close-out / public showcase (target v0.4.0).

A recruiter opening the repository must see a finished, honest MVP:

* MIT ``LICENSE``, README license section says MIT, real (non-placeholder) author.
* README carries the MVP status and demo date, a CI badge, a Mermaid diagram, a
  ``uv run pytest`` recipe and the 90% coverage floor. API tables live in
  ``docs/api.md``. The stale phase marker is gone.
* ``AGENTS.md`` keeps the public technical rules (incl. the EU AI Act section)
  and points to a gitignored ``AGENTS.local.md`` for private workflow notes.
* The UI greeting never falls back to a hard-coded personal name (EN/DE/HU),
  and a set display name still appears (control twin).
* ``docs/memory-design.md`` is English, CHANGELOG has ``[0.4.0]``, decision 004
  is tracked and neutral, the NAS doc uses a placeholder IP.

Leak scanning of the whole tree lives in ``tests/test_repo_hygiene.py``.
"""

from __future__ import annotations

import re
import subprocess
import threading
import tomllib
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from tests.test_repo_hygiene import find_internal_terms, find_windows_user_paths
from tests.test_voice_ui_bootstrap import _free_port, _launch_headless

_ROOT = Path(__file__).resolve().parents[1]
_FRONTEND = _ROOT / "frontend"
_DECISION_004 = "docs/decisions/004-grounding-and-guards.md"
_OLD_FALLBACK_NAME = "\u00c1kos"

_PLACEHOLDER_NAMES = frozenset(
    {"", "your name", "author", "name", "todo", "tbd", "firstname lastname", "fullname"}
)
_API_ROW = re.compile(
    r"^\|\s*(?:GET|POST|PUT|PATCH|DELETE)\s*\|.*/api/v1/", re.MULTILINE
)


def _read(rel: str) -> str:
    path = _ROOT / rel
    assert path.is_file(), f"{rel} is missing"
    return path.read_text(encoding="utf-8-sig")


def _git(*args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *args], cwd=_ROOT, capture_output=True)


def _is_placeholder(name: str) -> bool:
    clean = name.strip().lower()
    return (
        clean in _PLACEHOLDER_NAMES
        or clean.startswith(("<", "[", "{"))
        or "your " in clean
    )


def _section(markdown: str, heading_word: str) -> str:
    match = re.search(
        rf"^#{{1,3}}[^\n]*{heading_word}[^\n]*\n(.*?)(?=^#{{1,3}} |\Z)",
        markdown,
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    assert match, f"README has no heading containing {heading_word!r}"
    return match.group(1)


# --------------------------------------------------------------------------
# (1) License and author
# --------------------------------------------------------------------------


def test_license_file_is_mit_with_real_holder():
    """LICENSE is the MIT text with a year and a non-placeholder copyright holder."""
    text = _read("LICENSE")
    assert "MIT License" in text
    assert "Permission is hereby granted, free of charge" in text
    match = re.search(
        r"^Copyright \(c\) (\d{4})(?:[-\u2013]\d{4})?\s+(.+)$", text, re.MULTILINE
    )
    assert match, "LICENSE has no 'Copyright (c) <year> <holder>' line"
    assert int(match.group(1)) >= 2025
    assert not _is_placeholder(
        match.group(2)
    ), f"placeholder holder: {match.group(2)!r}"


def test_readme_license_section_says_mit():
    """README license section names MIT and no longer says it is undecided."""
    section = _section(_read("README.md"), "License")
    assert "MIT" in section
    assert "to be defined" not in section.lower()


def test_pyproject_authors_are_not_placeholders():
    """pyproject authors exist and none is a template placeholder like 'Your Name'."""
    data = tomllib.loads(_read("pyproject.toml"))
    authors = data["project"].get("authors") or []
    assert authors, "pyproject has no authors"
    for author in authors:
        assert not _is_placeholder(
            author.get("name", "")
        ), f"placeholder author: {author!r}"


def test_placeholder_check_control_twin():
    """The placeholder check rejects template names and accepts a real-looking name."""
    assert _is_placeholder("Your Name")
    assert _is_placeholder("<copyright holder>")
    assert not _is_placeholder("Jane Doe")


# --------------------------------------------------------------------------
# (2) README
# --------------------------------------------------------------------------


def test_readme_status_line_has_mvp_complete_and_demo_date():
    """Status says 'MVP complete, demo 18.09.2026' (the demo date, not the close-out date)."""
    readme = _read("README.md")
    assert re.search(r"MVP complete,\s*demo 18\.09\.2026", readme)
    assert not re.search(r"demo\s+24\.09\.2026", readme)


def test_readme_has_no_stale_phase_marker():
    """The old roadmap table marker 'Phase 5 <- current' is gone."""
    readme = _read("README.md")
    assert "\u2190 current" not in readme
    assert not re.search(r"phase\s*5[^\n]*current", readme, re.IGNORECASE)


def test_api_tables_moved_to_docs_api():
    """Endpoint tables live in docs/api.md, not in the slim README."""
    assert _API_ROW.findall(
        _read("docs/api.md")
    ), "docs/api.md has no endpoint table rows"
    assert "/api/v1/auth/me" in _read("docs/api.md")
    assert _API_ROW.findall(_read("README.md")) == [], "README still has API table rows"


def test_readme_showcase_essentials():
    """README has the CI badge, a Mermaid diagram, the pytest recipe and the 90% floor."""
    readme = _read("README.md")
    assert re.search(r"actions/workflows/ci\.yml/badge\.svg", readme), "no CI badge"
    assert "```mermaid" in readme, "no Mermaid architecture diagram"
    assert "uv run pytest" in readme, "no uv run pytest recipe"
    assert re.search(r"90\s*%", readme), "90% coverage floor not stated"


@pytest.mark.parametrize(
    "heading_word",
    ["Security", "Limitations", "Roadmap", "Capstone", "How this was built"],
)
def test_readme_has_honesty_sections(heading_word: str):
    """README has the public-facing honesty sections as headings."""
    _section(_read("README.md"), heading_word)


# --------------------------------------------------------------------------
# (3) + (4) AGENTS.md, local notes, personal paths
# --------------------------------------------------------------------------


def test_agents_md_is_public_safe():
    """AGENTS.md carries no internal terms, review jargon or user paths."""
    agents = _read("AGENTS.md")
    assert find_internal_terms(agents) == []
    assert "REVIEWEXTERN" not in agents
    assert find_windows_user_paths(agents) == []


def test_agents_md_keeps_public_rules_and_points_to_local_notes():
    """Technical rules and EU AI Act stay; a pointer to AGENTS.local.md is added."""
    agents = _read("AGENTS.md")
    assert "AGENTS.local.md" in agents
    assert "EU AI Act" in agents
    assert "Tenant isolation" in agents


def test_agents_local_md_is_gitignored():
    """AGENTS.local.md is ignored by git; AGENTS.md itself is not (control twin)."""
    assert _git("check-ignore", "-q", "AGENTS.local.md").returncode == 0
    assert _git("check-ignore", "-q", "AGENTS.md").returncode == 1


def test_nas_doc_uses_placeholder_ip():
    """The NAS setup doc uses <NAS_LAN_IP> instead of a real LAN address."""
    assert "<NAS_LAN_IP>" in _read("docs/nas-mongodb-setup.md")


# --------------------------------------------------------------------------
# (5) Greeting has no hard-coded personal fallback name
# --------------------------------------------------------------------------


def test_frontend_has_no_hard_coded_display_name_fallback():
    """No frontend file falls back to a literal name when display_name is empty."""
    literal_fallback = re.compile(r"display_name\s*\|\|\s*([\"'`])[^\"'`]+\1")
    for path in list(_FRONTEND.rglob("*.js")) + list(_FRONTEND.rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(_ROOT).as_posix()
        assert _OLD_FALLBACK_NAME not in text, f"{rel} still contains the personal name"
        assert not literal_fallback.search(
            text
        ), f"{rel} has a literal display_name fallback"


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


def _greeting_for(lang: str, display_name: str | None) -> str:
    """Load the UI, store a user, switch GUI language, return the greeting text."""
    port = _free_port()
    server = ThreadingHTTPServer(
        ("127.0.0.1", port), partial(_QuietHandler, directory=str(_FRONTEND))
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    user = {
        "id": "u1",
        "email": "a@example.com",
        "must_change_password": False,
        "display_name": display_name,
        "is_superuser": False,
        "timezone": "UTC",
    }
    try:
        with sync_playwright() as playwright:
            browser = _launch_headless(playwright)
            page = browser.new_page()
            page.add_init_script("window.JARVIS_API_BASE = '';")
            page.goto(f"http://127.0.0.1:{port}/", wait_until="domcontentloaded")
            page.wait_for_selector("#authScreen", timeout=10_000)
            page.wait_for_timeout(400)
            page.evaluate(
                """([user, lang]) => {
                    localStorage.setItem("jarvis_token", "test-token");
                    localStorage.setItem("jarvis_user", JSON.stringify(user));
                    document.querySelector(`.lang-flag[data-lang='${lang}']`).click();
                }""",
                [user, lang],
            )
            page.wait_for_timeout(200)
            text = page.locator("#emptyGreetingText").text_content() or ""
            browser.close()
    finally:
        server.shutdown()
    return text.strip()


_GREETING_WORD = {"en": "Hello", "de": "Hallo", "hu": "Szia"}


@pytest.mark.parametrize("lang", ["en", "de", "hu"])
def test_greeting_without_display_name_contains_no_name(lang: str):
    """Without a display name the greeting still greets but names nobody."""
    text = _greeting_for(lang, None)
    assert text.startswith(_GREETING_WORD[lang]), f"{lang}: {text!r}"
    assert _OLD_FALLBACK_NAME not in text, f"{lang}: {text!r}"
    assert "{name}" not in text, f"{lang}: {text!r}"
    assert "a@example.com" not in text, f"{lang}: {text!r}"
    assert not re.search(r",\s*[!.]?$", text), f"{lang}: dangling comma in {text!r}"


@pytest.mark.parametrize("lang", ["en", "de", "hu"])
def test_greeting_with_display_name_shows_that_name(lang: str):
    """Control twin: a set display name still appears in the greeting."""
    text = _greeting_for(lang, "Ada")
    assert text.startswith(_GREETING_WORD[lang]), f"{lang}: {text!r}"
    assert "Ada" in text, f"{lang}: {text!r}"
    assert _OLD_FALLBACK_NAME not in text


# --------------------------------------------------------------------------
# (6) memory design in English
# --------------------------------------------------------------------------

_GERMAN_MARKERS = frozenset(
    {
        "und",
        "der",
        "nicht",
        "ist",
        "f\u00fcr",
        "wird",
        "eine",
        "einen",
        "auf",
        "bei",
        "oder",
        "sind",
        "werden",
        "auch",
        "wenn",
        "zwei",
        "aktuelle",
        "ziel",
        "kurzfristig",
        "langfristig",
        "\u00fcber",
    }
)
_ENGLISH_MARKERS = frozenset({"the", "and", "is", "of", "to", "with"})


def _prose_words(markdown: str) -> list[str]:
    without_code = re.sub(r"```.*?```", " ", markdown, flags=re.DOTALL)
    without_code = re.sub(r"`[^`]*`", " ", without_code)
    return re.findall(r"[a-z\u00e4\u00f6\u00fc\u00df]+", without_code.lower())


def _german_marker_count(markdown: str) -> int:
    return sum(1 for word in _prose_words(markdown) if word in _GERMAN_MARKERS)


def test_memory_design_doc_is_english():
    """docs/memory-design.md prose is English (almost no German function words)."""
    doc = _read("docs/memory-design.md")
    german = _german_marker_count(doc)
    english = sum(1 for word in _prose_words(doc) if word in _ENGLISH_MARKERS)
    assert german <= 2, f"{german} German marker words remain"
    assert english >= 20, "doc does not read as English prose"


def test_german_detector_control_twin():
    """The language check flags a German sample and passes its English twin."""
    german = "Der Agent sammelt aktiv Erkenntnisse und pflegt das Archiv, wenn es nicht leer ist."
    english = "The agent actively collects insights and maintains the archive when it is not empty."
    assert _german_marker_count(german) > 2
    assert _german_marker_count(english) == 0


# --------------------------------------------------------------------------
# (7) + (8) CHANGELOG and decision 004
# --------------------------------------------------------------------------


def test_changelog_has_0_4_0_section():
    """CHANGELOG has a Keep-a-Changelog '[0.4.0]' release heading."""
    assert re.search(r"^## \[0\.4\.0\]", _read("CHANGELOG.md"), re.MULTILINE)


def test_decision_004_is_tracked():
    """Decision 004 is in the git index so the hygiene scan covers it."""
    result = _git("ls-files", "--error-unmatch", _DECISION_004)
    assert result.returncode == 0, f"{_DECISION_004} is not tracked"


def test_decision_004_wording_is_neutral():
    """Decision 004 keeps its content but names no external source or private tool."""
    doc = _read(_DECISION_004)
    assert "grounding" in doc.lower()
    assert len(doc) > 500
    assert find_internal_terms(doc) == [], find_internal_terms(doc)
