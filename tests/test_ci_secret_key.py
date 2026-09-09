"""Slice-Brief 5b: CI Pytest env SECRET_KEY must meet Settings strength bar.

After Slice 5, Settings rejects keys shorter than 64 characters or on the
placeholder denylist. GitHub Actions ``.github/workflows/ci.yml`` must set
``env.SECRET_KEY`` for the Pytest step to a synthetic ≥64 non-placeholder
value (same bar as local ``conftest``), or CI dies at Settings import.

Mutation: leaving the short ``ci-test-secret-key-do-not-use-in-prod!`` must
go red. Control twin: local conftest/test_config synthetic keys stay ≥64.
No live GitHub calls; parse the workflow YAML only.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from src.core.config import _MIN_SECRET_KEY_LEN, _SECRET_KEY_PLACEHOLDERS

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CI_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_CONFTEST = Path(__file__).resolve().parent / "conftest.py"


def _pytest_secret_key_from_ci() -> str:
    """Return SECRET_KEY from the CI Pytest step env (fail if missing)."""
    raw = _CI_WORKFLOW.read_text(encoding="utf-8")
    doc = yaml.safe_load(raw)
    steps = doc["jobs"]["test"]["steps"]
    pytest_steps = [
        step
        for step in steps
        if isinstance(step, dict) and step.get("name") == "Pytest"
    ]
    assert len(pytest_steps) == 1, "expected exactly one Pytest step in ci.yml"
    env = pytest_steps[0].get("env") or {}
    key = env.get("SECRET_KEY")
    assert isinstance(key, str) and key, "Pytest step must set SECRET_KEY"
    return key


def test_ci_pytest_secret_key_is_at_least_64_chars():
    """CI Pytest env SECRET_KEY must be ≥64 so Settings import succeeds."""
    key = _pytest_secret_key_from_ci()
    assert len(key) >= _MIN_SECRET_KEY_LEN, (
        f"ci.yml Pytest SECRET_KEY length {len(key)} < {_MIN_SECRET_KEY_LEN}; "
        f"got {key!r}"
    )


def test_ci_pytest_secret_key_is_not_placeholder():
    """CI Pytest SECRET_KEY must not be a documented change-me placeholder."""
    key = _pytest_secret_key_from_ci()
    cleaned = key.strip().casefold()
    assert cleaned not in {p.casefold() for p in _SECRET_KEY_PLACEHOLDERS}
    assert not any(
        cleaned == bad or cleaned.startswith(bad + "-") or cleaned.startswith(bad + "x")
        for bad in ("change-me", "change-me-to-a-long-random-string")
    )


def test_ci_pytest_secret_key_passes_settings_validator():
    """Control path: constructing Settings with the CI key must succeed."""
    from src.core.config import Settings

    key = _pytest_secret_key_from_ci()
    settings = Settings(secret_key=key, _env_file=None)
    assert settings.secret_key == key.strip()


def test_conftest_secret_key_still_meets_strength_control():
    """Control twin: local conftest synthetic SECRET_KEY remains ≥64."""
    import re

    text = _CONFTEST.read_text(encoding="utf-8")
    match = re.search(
        r'os\.environ\.setdefault\(\s*"SECRET_KEY"\s*,\s*"([^"]+)"\s*\)',
        text,
    )
    assert match is not None, "conftest must setdefault SECRET_KEY before app import"
    key = match.group(1)
    assert len(key) >= _MIN_SECRET_KEY_LEN
    assert key.strip().casefold() not in {
        p.casefold() for p in _SECRET_KEY_PLACEHOLDERS
    }
