"""Slice-Brief 16: public repo hygiene for the MVP showcase.

Every git-tracked text file is scanned for three leak classes that must not
reach the public repository:

* Windows user-profile paths (a drive letter, ``Users`` and a real name segment).
* Private-network IPv4 addresses (192.168/16, 10/8, 100.64/10) used as real
  addresses, not version strings.
* Internal workflow terms: the private collaborator-memory name, the external
  capstone source name, and the bot-team role names.

Each detector has a counter-test that plants a leak and must go red, so a green
tree scan proves absence instead of a detector that never fires. Each detector
also has a control twin (placeholders, version strings, ordinary words) so the
allowlist can stay empty.

Scope choice: the review-process tag used as a docstring prefix in older tests
is out of scope and is NOT in the term list. ``tests/test_mvp_closeout.py``
checks instead that ``AGENTS.md`` no longer carries it.

This file must pass its own scan without a self-exclusion, so leak-shaped
literals are assembled from fragments at runtime.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable, Iterable
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_SELF = "tests/test_repo_hygiene.py"

_BINARY_SUFFIXES = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".webp",
        ".onnx",
        ".pptx",
        ".pdf",
        ".woff",
        ".woff2",
        ".ttf",
        ".zip",
        ".wav",
        ".mp3",
        ".ogg",
        ".webm",
    }
)

# Narrow, explicit allowlist of (tracked path, detector name) pairs. Keep it
# empty unless a hit is a reviewed, deliberate exception, and give every entry
# a reason comment. There is deliberately no directory-wide exclusion.
_ALLOWLIST: frozenset[tuple[str, str]] = frozenset()
_ALLOWLIST_MAX = 5

_WIN_USER_PATH = re.compile(
    r"\b[A-Za-z]:(?:\\{1,2}|/)Users(?:\\{1,2}|/)[A-Za-z0-9_][^\\/\s'\"`<>]*",
    re.IGNORECASE,
)

_PRIVATE_IPV4 = re.compile(
    r"(?<![\w.])"
    r"(?:192\.168|10\.\d{1,3}|100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7]))"
    r"\.\d{1,3}\.\d{1,3}"
    r"(?!\.?\w)"
)
# A dotted quad right after a pin operator or a version key is a version string.
_VERSION_CONTEXT = re.compile(
    r"(?:[=<>~!]=\s*|version\s*[=:]\s*[\"']?)$",
    re.IGNORECASE,
)

_INTERNAL_TERMS: tuple[str, ...] = (
    "NEX" + "US",
    "FORE" + "MAN",
    "Coordinator" + "-Bot",
    "Test" + "-Manager",
    "Code" + "-Writer1",
    "Code" + "-Write-Manager",
)
_INTERNAL_TERM_RE = re.compile(
    r"(?<!\w)(?:" + "|".join(map(re.escape, _INTERNAL_TERMS)) + r")(?!\w)",
    re.IGNORECASE,
)


def find_windows_user_paths(text: str) -> list[str]:
    """Return Windows user-profile paths that carry a real name segment."""
    return [m.group(0) for m in _WIN_USER_PATH.finditer(text)]


def find_private_ips(text: str) -> list[str]:
    """Return private-range IPv4 addresses, skipping version strings."""
    hits: list[str] = []
    for match in _PRIVATE_IPV4.finditer(text):
        if any(int(octet) > 255 for octet in match.group(0).split(".")):
            continue
        prefix = text[max(0, match.start() - 16) : match.start()]
        if _VERSION_CONTEXT.search(prefix):
            continue
        hits.append(match.group(0))
    return hits


def find_internal_terms(text: str) -> list[str]:
    """Return internal workflow terms (case-insensitive, whole token)."""
    return [m.group(0) for m in _INTERNAL_TERM_RE.finditer(text)]


_DETECTORS: dict[str, Callable[[str], list[str]]] = {
    "windows_user_path": find_windows_user_paths,
    "private_ip": find_private_ips,
    "internal_term": find_internal_terms,
}


def _tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=_ROOT,
        capture_output=True,
        check=True,
    ).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def _read_text(path: Path) -> str | None:
    if path.suffix.lower() in _BINARY_SUFFIXES or not path.is_file():
        return None
    data = path.read_bytes()
    if b"\0" in data[:8192]:
        return None
    # Replace instead of skip: an odd encoding must not hide a leak.
    return data.decode("utf-8", errors="replace")


def scan(root: Path, rel_paths: Iterable[str], detector: str) -> list[str]:
    """Return ``path:line: hit`` for every detector hit outside the allowlist."""
    find = _DETECTORS[detector]
    hits: list[str] = []
    for rel in rel_paths:
        if (rel, detector) in _ALLOWLIST:
            continue
        text = _read_text(root / rel)
        if text is None:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for hit in find(line):
                hits.append(f"{rel}:{lineno}: {hit}")
    return hits


def _win_path(*parts: str, sep: str = "\\") -> str:
    return "C:" + sep + sep.join(parts)


def _ip(*octets: str) -> str:
    return ".".join(octets)


# --------------------------------------------------------------------------
# Tree scans
# --------------------------------------------------------------------------


def test_tracked_tree_scan_is_not_vacuous():
    """The scan must actually see the public files, or a green result means nothing."""
    tracked = _tracked_files()
    assert {"README.md", "AGENTS.md"} <= set(
        tracked
    ), "git ls-files did not list the core public files"
    readable = [rel for rel in tracked if _read_text(_ROOT / rel) is not None]
    assert len(readable) >= 50, f"only {len(readable)} readable tracked text files"


@pytest.mark.parametrize("detector", sorted(_DETECTORS))
def test_tracked_files_have_no_leaks(detector: str):
    """No git-tracked text file may contain a leak of this class."""
    hits = scan(_ROOT, _tracked_files(), detector)
    assert hits == [], f"{detector} leaks in tracked files:\n" + "\n".join(hits)


@pytest.mark.parametrize("detector", sorted(_DETECTORS))
def test_hygiene_file_passes_its_own_scan(detector: str):
    """This file is scanned like any other; it must not trip its own detectors."""
    assert (_SELF, detector) not in _ALLOWLIST
    assert scan(_ROOT, [_SELF], detector) == []


def test_allowlist_stays_narrow_and_explicit():
    """Allowlist entries name one tracked file and one known detector, and stay few."""
    assert len(_ALLOWLIST) <= _ALLOWLIST_MAX
    tracked = set(_tracked_files())
    for rel, detector in _ALLOWLIST:
        assert detector in _DETECTORS, f"unknown detector {detector!r}"
        assert rel in tracked, f"allowlisted path {rel!r} is not tracked"


# --------------------------------------------------------------------------
# Counter-tests: planted leaks must be caught (detector bites)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "planted",
    [
        "cd " + _win_path("Users", "jdoe", "DEV", "repo"),
        "path: " + _win_path("Users", "jdoe", "AppData", sep="/"),
        '"cwd": "' + _win_path("Users", "jdoe", "DEV", sep="\\\\") + '"',
        "d:" + "\\".join(["", "users", "Jane_Doe", "notes.txt"]),
    ],
)
def test_windows_path_detector_bites(planted: str):
    """A real user-profile path must be flagged in every common spelling."""
    assert find_windows_user_paths(planted), f"missed: {planted!r}"


@pytest.mark.parametrize(
    "benign",
    [
        _win_path("Users", "<name>", "DEV"),
        _win_path("Users", "...", "pa-voice-mvp"),
        "%USERPROFILE%\\DEV\\pa-voice-mvp",
        "/home/users/jdoe",
        "C:\\Program Files\\Git",
    ],
)
def test_windows_path_detector_control_twin(benign: str):
    """Placeholders and non-profile paths are not leaks."""
    assert find_windows_user_paths(benign) == [], f"false positive: {benign!r}"


@pytest.mark.parametrize(
    "planted",
    [
        "MONGO_URL=mongodb://" + _ip("192", "168", "1", "50") + ":27017",
        "host " + _ip("10", "0", "0", "12") + ".",
        "tailnet " + _ip("100", "64", "0", "1"),
        "tailnet " + _ip("100", "127", "255", "254"),
    ],
)
def test_private_ip_detector_bites(planted: str):
    """Real private-range addresses must be flagged, including CGNAT."""
    assert find_private_ips(planted), f"missed: {planted!r}"


@pytest.mark.parametrize(
    "benign",
    [
        "tailnet " + _ip("100", "63", "0", "1"),
        "tailnet " + _ip("100", "128", "0", "1"),
        "bind " + _ip("127", "0", "0", "1"),
        "pkg==" + _ip("10", "0", "0", "1"),
        'version = "' + _ip("10", "2", "0", "1") + '"',
        "v" + _ip("10", "1", "2", "3"),
        "build " + _ip("1", "10", "0", "0", "1"),
        "bad " + _ip("10", "0", "0", "300"),
        "<NAS_LAN_IP>",
    ],
)
def test_private_ip_detector_control_twin(benign: str):
    """Public ranges, loopback, version strings and placeholders are not leaks."""
    assert find_private_ips(benign) == [], f"false positive: {benign!r}"


@pytest.mark.parametrize("term", _INTERNAL_TERMS)
def test_internal_term_detector_bites(term: str):
    """Every internal term is flagged in any case, inside ordinary prose."""
    assert find_internal_terms(f"Ask the {term} first.")
    assert find_internal_terms(f"({term.lower()})")
    assert find_internal_terms(f"no {term}-in-product")


@pytest.mark.parametrize(
    "benign",
    [
        "the test manager role",
        "contest" + "-manager",
        "Code" + "-Writer2",
        "nexuses of routes",
    ],
)
def test_internal_term_detector_control_twin(benign: str):
    """Ordinary words and near-misses are not internal terms."""
    assert find_internal_terms(benign) == [], f"false positive: {benign!r}"


_PLANTED_FILES: dict[str, tuple[str, str]] = {
    "windows_user_path": (
        "docs/leak.md",
        "Setup\n\n    cd " + _win_path("Users", "jdoe", "DEV") + "\n",
    ),
    "private_ip": (
        "notes.txt",
        "first line\nNAS at " + _ip("192", "168", "2", "7") + "\n",
    ),
    "internal_term": (
        "tests/test_planted.py",
        '"""Ask ' + "NEX" + 'US about it."""\n',
    ),
}


@pytest.mark.parametrize("detector", sorted(_DETECTORS))
def test_scan_pipeline_bites_on_planted_file(tmp_path: Path, detector: str):
    """A leak planted in a real file (tests/ included) makes the file scan go red."""
    rel, content = _PLANTED_FILES[detector]
    target = tmp_path / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    hits = scan(tmp_path, [rel], detector)
    assert hits, f"{detector} scan missed a planted leak in {rel}"
    assert hits[0].startswith(f"{rel}:"), hits


def test_scan_pipeline_skips_binary_but_not_odd_encodings(tmp_path: Path):
    """Binary files are skipped, but a non-UTF-8 text file is still scanned."""
    (tmp_path / "blob.bin").write_bytes(b"\0\0" + ("NEX" + "US").encode())
    (tmp_path / "latin.md").write_bytes(("caf\xe9 " + "NEX" + "US").encode("latin-1"))
    assert scan(tmp_path, ["blob.bin"], "internal_term") == []
    assert scan(tmp_path, ["latin.md"], "internal_term")
