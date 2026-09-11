"""REVIEWEXTERN P1-7: CI and the image install the same lock.

Slice-Brief 10: CI must ``uv sync --frozen`` (not floating ``uv pip install``).
Docker already uses ``uv sync --frozen --no-dev``. cryptography in uv.lock
must be >= 50.0.0 (PYSEC-2026-3552 is 49.0.0).

Mutation M1: CI install without --frozen must make test_ci_installs_from_lock
go red. Control: Dockerfile still has uv sync --frozen --no-dev.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_CI = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
_DOCKER = (_ROOT / "Dockerfile").read_text(encoding="utf-8")
_LOCK = (_ROOT / "uv.lock").read_text(encoding="utf-8")
_README = (_ROOT / "README.md").read_text(encoding="utf-8")


def test_ci_installs_from_lock():
    """CI must sync the committed lock, not resolve floating deps.

    Mutation M1: dropping --frozen so CI floats must go red.
    """
    assert "uv sync --frozen" in _CI
    assert "uv pip install" not in _CI


def test_dockerfile_installs_from_lock():
    """Control twin: the image still installs with a frozen lock and no dev extra."""
    assert "uv sync --frozen --no-dev" in _DOCKER


def test_lock_cryptography_is_patched():
    """uv.lock must not ship cryptography 49.0.0 (PYSEC-2026-3552)."""
    match = re.search(
        r'^name = "cryptography"\nversion = "([^"]+)"',
        _LOCK,
        re.MULTILINE,
    )
    assert match, "cryptography package missing from uv.lock"
    version = match.group(1)
    major_s, minor_s, *_rest = version.split(".")
    major, minor = int(major_s), int(minor_s)
    assert (major, minor) >= (
        50,
        0,
    ), f"cryptography {version} is below 50.0.0 (PYSEC-2026-3552)"


def test_readme_does_not_teach_floating_uv_pip_install():
    """Getting Started must not tell clones to ignore the lock."""
    assert 'uv pip install -e ".[dev]"' not in _README
    assert "uv sync" in _README
