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

import hashlib
import math
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


# --------------------------------------------------------------------------
# Slice-Brief 17: CHANGELOG [0.4.0] release-reading cleanup
# --------------------------------------------------------------------------

# sha256 of the [0.3.0] section (heading through the blank line before
# "## [0.2.0]") as released; read with universal newlines, utf-8-sig.
_CHANGELOG_0_3_0_SHA256 = (
    "c190d3eabf1636d2088fda1aa7c3c227dc263123e1d1b0840fd30586d731970d"
)
_BARE_BUDGET_NUMBER = re.compile(r"\(\s*327\s*\)")


def _changelog_section(version: str) -> str:
    """Return one release section: its '## [x.y.z]' heading up to the next one."""
    text = _read("CHANGELOG.md")
    match = re.search(
        rf"^## \[{re.escape(version)}\].*?(?=^## \[|\Z)", text, re.S | re.M
    )
    assert match, f"CHANGELOG has no [{version}] section"
    return match.group(0)


def _subsection(section: str, title: str) -> str:
    """Return a '### Title' block of a release section up to the next heading."""
    match = re.search(
        rf"^### {re.escape(title)}\s*$(.*?)(?=^##|\Z)", section, re.S | re.M
    )
    assert match, f"section has no '### {title}'"
    return match.group(1)


def _has_bare_budget_number(text: str) -> bool:
    return bool(_BARE_BUDGET_NUMBER.search(text))


def _frontend_wav_budget_seconds() -> int:
    """Recompute ``wavBudgetSeconds()`` from the constants in ``audio.js``."""
    js = (_FRONTEND / "js" / "audio.js").read_text(encoding="utf-8")
    rate = re.search(r"WAV_SAMPLE_RATE\s*=\s*(\d+)\s*;", js)
    cap = re.search(r"MAX_AUDIO_UPLOAD_BYTES\s*=\s*([\d\s*]+);", js)
    assert rate and cap, "audio.js budget constants not found"
    cap_bytes = math.prod(int(part) for part in cap.group(1).split("*"))
    return cap_bytes // (int(rate.group(1)) * 2)


def test_changelog_0_4_0_has_no_in_progress_phase_note():
    """A finished release must not say Phase 5 is still in progress."""
    section = _changelog_section("0.4.0")
    assert "Phase 5 (Polish & Demo) in progress" not in section
    assert not re.search(r"Phase 5\b.*\bin progress", section, re.I), re.search(
        r".*Phase 5\b.*\bin progress.*", section, re.I
    )


def test_changelog_0_4_0_shell_entry_has_no_internal_wording():
    """The shell-layout entry drops internal wording but keeps its facts."""
    section = _changelog_section("0.4.0")
    lowered = section.lower()
    for phrase in ("annotated", "claude screenshot", "maintainer's"):
        assert phrase not in lowered, f"internal wording {phrase!r} still present"
    for fact in ("`+ New`", "Notes", "Reminders", "Chats", "document upload"):
        assert fact in section, f"shell entry lost the fact {fact!r}"


def test_changelog_0_4_0_changed_lists_watermark_top_right():
    """[0.4.0] ### Changed has a bullet for the watermark moving to the top right."""
    changed = _subsection(_changelog_section("0.4.0"), "Changed")
    bullets = [line for line in changed.splitlines() if line.lstrip().startswith("-")]
    assert any(
        "watermark" in line.lower() and re.search(r"top[\s-]right", line, re.I)
        for line in bullets
    ), "no '### Changed' bullet mentions the watermark moving to the top right"


def test_changelog_0_4_0_budget_seconds_are_explained():
    """No bare '(327)'; if the number stays it is explained and matches audio.js."""
    section = _changelog_section("0.4.0")
    assert not _has_bare_budget_number(section), "bare '(327)' still present"
    for line in section.splitlines():
        if not re.search(r"\b327\b", line):
            continue
        assert re.search(r"16\s*kHz", line), line
        assert "mono" in line and "16-bit" in line, line
        assert re.search(r"10\s*Mi?B", line), line
        assert _frontend_wav_budget_seconds() == 327, "code budget is not 327 s"


def test_bare_budget_number_detector_control_twin():
    """Control: the bare-number check bites on '(327)' but not on the explained form."""
    assert _has_bare_budget_number("remaining WAV-budget seconds (327) while")
    assert _has_bare_budget_number("seconds ( 327 )")
    assert not _has_bare_budget_number(
        "about 327 s (10 MB at 16 kHz mono 16-bit) while recording"
    )


def test_changelog_0_3_0_section_is_byte_identical():
    """Control twin: the cleanup touches [0.4.0] only; [0.3.0] stays as released."""
    section = _changelog_section("0.3.0")
    digest = hashlib.sha256(section.encode("utf-8")).hexdigest()
    assert digest == _CHANGELOG_0_3_0_SHA256, "[0.3.0] section changed"


# --------------------------------------------------------------------------
# Slice-Brief 18: README Screenshots (help.png + admin.png)
# --------------------------------------------------------------------------

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_SCREENSHOT_IMAGES = ("docs/images/help.png", "docs/images/admin.png")
_FORBIDDEN_README_IMAGE_BASENAMES = frozenset({"chat.png", "help_screen.png"})

# Markdown ![alt](path) and HTML <img src="..." alt="..."> (either attr order).
_MD_IMG = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
# Collect src and alt from each <img ...> tag.
_HTML_IMG_TAG = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_HTML_ATTR = re.compile(r"""\b(src|alt)\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE)


def _readme_lines() -> list[str]:
    """README as newline-split lines (CRLF-safe via splitlines)."""
    return _read("README.md").splitlines()


def _h2_titles(lines: list[str]) -> list[tuple[int, str]]:
    """Return (0-based line index, title text) for every exact ``## `` heading."""
    out: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        if line.startswith("## ") and not line.startswith("###"):
            out.append((i, line[3:].strip()))
    return out


def _ci_badge_last_line(lines: list[str]) -> int:
    """Index of the last CI/shields badge line near the top of the README."""
    badge_idxs = [
        i
        for i, line in enumerate(lines)
        if re.search(r"badge\.svg|shields\.io|actions/workflows/", line, re.I)
    ]
    assert badge_idxs, "README has no CI/shields badge line"
    return badge_idxs[-1]


def _iter_readme_images(text: str) -> list[tuple[str, str]]:
    """Return (alt, path) for every markdown or HTML image in ``text``."""
    found: list[tuple[str, str]] = []
    for match in _MD_IMG.finditer(text):
        found.append((match.group(1), match.group(2).strip()))
    for tag in _HTML_IMG_TAG.finditer(text):
        attrs = {
            m.group(1).lower(): (m.group(2) if m.group(2) is not None else m.group(3))
            for m in _HTML_ATTR.finditer(tag.group(0))
        }
        src = attrs.get("src")
        if src is None:
            continue
        found.append((attrs.get("alt") or "", src.strip()))
    return found


def _is_remote_or_data_url(path: str) -> bool:
    lower = path.strip().lower()
    return lower.startswith(("http://", "https://", "data:"))


def _local_readme_image_problems(readme_text: str, repo_root: Path) -> list[str]:
    """Problems for local README images: missing, not under docs/images/, or non-lowercase basename."""
    problems: list[str] = []
    for _alt, path in _iter_readme_images(readme_text):
        if _is_remote_or_data_url(path):
            continue
        norm = path.replace("\\", "/").lstrip("./")
        if not norm.startswith("docs/images/"):
            problems.append(f"not under docs/images/: {path}")
            continue
        basename = Path(norm).name
        if basename != basename.lower():
            problems.append(f"basename not lowercase: {path}")
        if not (repo_root / norm).is_file():
            problems.append(f"missing: {path}")
    return problems


def _forbidden_readme_image_refs(readme_text: str) -> list[str]:
    """Return image paths whose basename is a slice-18 forbidden screenshot name."""
    hits: list[str] = []
    for _alt, path in _iter_readme_images(readme_text):
        if _is_remote_or_data_url(path):
            continue
        base = Path(path.replace("\\", "/")).name.lower()
        if base in _FORBIDDEN_README_IMAGE_BASENAMES:
            hits.append(path)
    return hits


def _screenshots_section_body(lines: list[str]) -> str:
    """Body of the ``## Screenshots`` section up to (not including) the next H2."""
    h2s = _h2_titles(lines)
    starts = [i for i, title in h2s if title == "Screenshots"]
    assert len(starts) == 1, f"expected one Screenshots H2, got {len(starts)}"
    start = starts[0]
    end = len(lines)
    for i, _title in h2s:
        if i > start:
            end = i
            break
    return "\n".join(lines[start + 1 : end])


def _image_blocks_with_captions(section_body: str) -> list[tuple[str, str, str]]:
    """Parse section body into (alt, path, caption) for each local image + following caption line."""
    lines = section_body.splitlines()
    blocks: list[tuple[str, str, str]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        imgs = _iter_readme_images(line)
        if not imgs:
            i += 1
            continue
        alt, path = imgs[0]
        caption = ""
        j = i + 1
        while j < len(lines):
            candidate = lines[j].strip()
            if not candidate:
                j += 1
                continue
            if candidate.startswith("#") or _iter_readme_images(lines[j]):
                break
            caption = candidate
            break
        blocks.append((alt, path.replace("\\", "/"), caption))
        i = (j + 1) if caption else (i + 1)
    return blocks


def test_readme_screenshots_h2_placement():
    """Exactly one ## Screenshots sits after the CI badge and immediately before ## Architecture."""
    lines = _readme_lines()
    badge_last = _ci_badge_last_line(lines)
    h2s = _h2_titles(lines)
    screenshots = [(i, t) for i, t in h2s if t == "Screenshots"]
    assert len(screenshots) == 1, f"expected one Screenshots H2, found {screenshots}"
    shot_idx, _ = screenshots[0]
    assert shot_idx > badge_last, "Screenshots must come after the CI badge block"
    between = [(i, t) for i, t in h2s if badge_last < i < shot_idx]
    assert between == [], f"H2 between badge and Screenshots: {between}"
    after = [(i, t) for i, t in h2s if i > shot_idx]
    assert after, "no H2 after Screenshots"
    assert (
        after[0][1] == "Architecture"
    ), f"next H2 is {after[0][1]!r}, not Architecture"


def test_readme_screenshots_section_images_and_captions():
    """Screenshots shows help.png then admin.png, each with alt text, caption, and content anchors."""
    body = _screenshots_section_body(_readme_lines())
    blocks = _image_blocks_with_captions(body)
    paths = [path for _alt, path, _cap in blocks]
    assert paths == list(_SCREENSHOT_IMAGES), f"image paths: {paths}"
    for alt, path, caption in blocks:
        assert alt.strip(), f"empty alt for {path}"
        assert caption.strip(), f"missing caption after {path}"
        assert not caption.lstrip().startswith(
            "#"
        ), f"caption looks like a heading: {caption!r}"
        assert not _iter_readme_images(caption), f"caption is an image: {caption!r}"
    help_blob = (blocks[0][0] + " " + blocks[0][2]).lower()
    admin_blob = (blocks[1][0] + " " + blocks[1][2]).lower()
    assert (
        "trigger" in help_blob
    ), f"help alt/caption must mention trigger: {help_blob!r}"
    assert (
        "user" in admin_blob and "demo" in admin_blob
    ), f"admin alt/caption must mention user and demo: {admin_blob!r}"


def test_local_readme_image_problems_on_real_readme():
    """Live README local image refs are under docs/images/, lowercase, and on disk."""
    assert _local_readme_image_problems(_read("README.md"), _ROOT) == []


def test_local_readme_image_problems_control_twin(tmp_path: Path):
    """Detector reports not-under-docs/images, non-lowercase basename, and missing file."""
    images = tmp_path / "docs" / "images"
    images.mkdir(parents=True)
    (images / "Help_screen.png").write_bytes(_PNG_SIGNATURE + b"x")
    synthetic = "\n".join(
        [
            "![Help](docs/images/Help_screen.png)",
            "![X](images/x.png)",
            '<img src="docs/images/missing.png" alt="gone">',
        ]
    )
    problems = _local_readme_image_problems(synthetic, tmp_path)
    kinds = "\n".join(problems)
    assert any("basename not lowercase" in p for p in problems), kinds
    assert any("not under docs/images/" in p for p in problems), kinds
    assert any("missing:" in p for p in problems), kinds
    assert len(problems) == 3, problems


def test_readme_has_no_forbidden_screenshot_refs():
    """README must not reference Chat.png / chat.png or the pre-rename Help_screen.png."""
    assert _forbidden_readme_image_refs(_read("README.md")) == []


def test_forbidden_screenshot_refs_control_twin():
    """Control: the forbidden-ref detector catches docs/images/Chat.png."""
    planted = "See ![chat](docs/images/Chat.png) later."
    hits = _forbidden_readme_image_refs(planted)
    assert hits == ["docs/images/Chat.png"], hits


def test_screenshot_png_files_exist_with_signature():
    """help.png and admin.png exist as PNGs; the pre-rename Help_screen.png is gone."""
    for rel in _SCREENSHOT_IMAGES:
        path = _ROOT / rel
        assert path.is_file(), f"{rel} is missing"
        assert path.read_bytes()[:8] == _PNG_SIGNATURE, f"{rel} is not a PNG"
    assert not (
        _ROOT / "docs/images/Help_screen.png"
    ).exists(), "docs/images/Help_screen.png must be renamed away"


def test_screenshot_pngs_are_not_gitignored():
    """help.png and admin.png must not be ignored (untracked-before-commit is fine)."""
    for rel in _SCREENSHOT_IMAGES:
        result = _git("check-ignore", "-q", rel)
        assert result.returncode == 1, f"{rel} is gitignored (exit {result.returncode})"


# --------------------------------------------------------------------------
# Slice-Brief 19: helpIntro count wording + user-guide + CHANGELOG
# --------------------------------------------------------------------------

# Number words 2..20 (exclude one/ein/eine/egy — articles / ambiguous).
_COUNT_WORDS: dict[str, tuple[str, ...]] = {
    "en": (
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "ten",
        "eleven",
        "twelve",
        "thirteen",
        "fourteen",
        "fifteen",
        "sixteen",
        "seventeen",
        "eighteen",
        "nineteen",
        "twenty",
    ),
    "de": (
        "zwei",
        "drei",
        "vier",
        "fünf",
        "sechs",
        "sieben",
        "acht",
        "neun",
        "zehn",
        "elf",
        "zwölf",
        "dreizehn",
        "vierzehn",
        "fünfzehn",
        "sechzehn",
        "siebzehn",
        "achtzehn",
        "neunzehn",
        "zwanzig",
    ),
    "hu": (
        "két",
        "kettő",
        "három",
        "négy",
        "öt",
        "hat",
        "hét",
        "nyolc",
        "kilenc",
        "tíz",
        "tizenegy",
        "tizenkettő",
        "tizenkét",
        "tizenhárom",
        "tizennégy",
        "tizenöt",
        "tizenhat",
        "tizenhét",
        "tizennyolc",
        "tizenkilenc",
        "húsz",
    ),
}

# Old helpIntro literals (base 0bd1caa); assembled so source is explicit.
_OLD_HELP_INTRO = {
    "en": (
        "Ten everyday phrases per skill in the GUI language. "
        "First match wins; otherwise the general assistant answers."
    ),
    "de": (
        "Zehn Alltagssätze pro Skill in der GUI-Sprache. "
        "Der erste Treffer gewinnt; sonst antwortet der allgemeine Assistent."
    ),
    "hu": (
        "Tíz mindennapi kifejezés készségenként a felület nyelvén. "
        "Az első találat nyer; különben az általános asszisztens válaszol."
    ),
}
_SUGGESTED_EN_HELP_INTRO = (
    "Everyday trigger phrases per skill in the GUI language. "
    "First match wins; otherwise the general assistant answers."
)
_OLD_USER_GUIDE_HELP_SENTENCE = (
    "The Help panel (`?`) lists **ten everyday phrases per skill** "
    "for the language you pick with the flag (🇬🇧 / 🇩🇪 / 🇭🇺)."
)


def _count_claim_hits(text: str, lang: str) -> list[str]:
    """Return digit / number-word hits (2..20) in ``text`` for ``lang``."""
    assert lang in _COUNT_WORDS, lang
    hits: list[str] = []
    for match in re.finditer(r"(?<!\w)\d+(?!\w)", text):
        hits.append(match.group(0))
    # Sort longer words first so tizenegy beats egy-suffix noise; use word bounds.
    words = sorted(_COUNT_WORDS[lang], key=len, reverse=True)
    pattern = re.compile(
        r"(?<!\w)(?:" + "|".join(re.escape(w) for w in words) + r")(?!\w)",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        hits.append(match.group(0))
    return hits


def _i18n_value(lang: str, key: str) -> str:
    """Return one quoted string value from ``frontend/js/i18n.js`` for a language."""
    source = _read("frontend/js/i18n.js")
    block = re.search(
        rf"(?ms)^\s*{re.escape(lang)}:\s*\{{(.*?)(?=^\s*(?:en|de|hu):\s*\{{|^\}}\s*;)",
        source,
    )
    assert block, f"i18n.js has no {lang!r} block"
    match = re.search(
        rf'(?m)^\s*{re.escape(key)}:\s*"((?:\\.|[^"\\])*)"',
        block.group(1),
    )
    assert match, f"i18n.js {lang}.{key} missing"
    return match.group(1)


def _guide_phrase_count_claims(guide_text: str) -> list[str]:
    """EN count claims that share a sentence with 'phrase' or 'trigger'."""
    chunks = re.split(r"(?<=[.!?])\s+|\n+", guide_text)
    hits: list[str] = []
    for chunk in chunks:
        if not re.search(r"phrase|trigger", chunk, re.IGNORECASE):
            continue
        found = _count_claim_hits(chunk, "en")
        if found:
            hits.append(f"{found!r} in {chunk.strip()[:120]!r}")
    return hits


def test_help_intro_has_no_count_claim_per_language():
    """helpIntro must not claim a fixed phrase count in EN, DE or HU."""
    for lang in ("en", "de", "hu"):
        intro = _i18n_value(lang, "helpIntro")
        assert intro.strip(), f"{lang} helpIntro empty"
        hits = _count_claim_hits(intro, lang)
        assert (
            hits == []
        ), f"{lang} helpIntro still claims a count: {hits!r} in {intro!r}"


def test_help_intro_count_detector_control_twin():
    """Detector flags the old Ten/Zehn/Tíz intros and accepts the suggested EN line."""
    for lang, old in _OLD_HELP_INTRO.items():
        hits = _count_claim_hits(old, lang)
        assert hits, f"detector missed old {lang} helpIntro: {old!r}"
    assert _count_claim_hits(_SUGGESTED_EN_HELP_INTRO, "en") == []


def test_help_intro_mentions_phrases_or_triggers():
    """Each helpIntro still talks about phrases/triggers (light content anchor)."""
    en = _i18n_value("en", "helpIntro")
    assert re.search(r"phrase|trigger", en, re.IGNORECASE), en
    de = _i18n_value("de", "helpIntro")
    assert re.search(r"s[aä]tz|phras|ausl[oö]ser|trigger", de, re.IGNORECASE), de
    hu = _i18n_value("hu", "helpIntro")
    assert re.search(r"kifejez|mondat|kulcssz|trigger", hu, re.IGNORECASE), hu


def test_changelog_unreleased_fixed_help_intro_count_wording():
    """Unreleased ### Fixed notes the helpIntro / help-overlay phrase-count wording."""
    fixed = _subsection(_changelog_section("Unreleased"), "Fixed")
    bullets = [line for line in fixed.splitlines() if line.lstrip().startswith("-")]
    assert bullets, "### Fixed has no bullets"
    assert any(
        re.search(r"help", line, re.I) and re.search(r"phrase", line, re.I)
        for line in bullets
    ), f"no Fixed bullet about help phrase wording: {bullets}"


def test_user_guide_has_no_fixed_phrase_count_claim():
    """User guide must not claim a fixed EN phrase/trigger count per skill."""
    hits = _guide_phrase_count_claims(_read("docs/user-guide.md"))
    assert hits == [], "user-guide still claims a fixed phrase count:\n" + "\n".join(
        hits
    )


def test_user_guide_phrase_count_detector_control_twin():
    """Control: the old user-guide Help-panel 'ten … phrases' sentence is flagged."""
    hits = _guide_phrase_count_claims(_OLD_USER_GUIDE_HELP_SENTENCE)
    assert hits, "detector missed the old user-guide ten-phrases sentence"
