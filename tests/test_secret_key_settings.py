"""Slice-Brief 5 / REVIEWEXTERN P0-1: reject weak SECRET_KEY at Settings load.

Settings must fail fast when ``secret_key`` is empty, shorter than 64
characters, or an explicit placeholder (including the documented
``.env.example`` value ``change-me-to-a-long-random-string`` and similar
change-me placeholders). A strong ≥64 random/non-placeholder key loads
normally. Missing ``secret_key`` must still fail (control twin — same
fail-fast class as today).

Mutation: accepting the public placeholder or a short key must go red.
No real secrets in this file — only synthetic test strings.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.core.config import Settings

# Synthetic ≥64 key for controls / happy path (not a production secret).
_STRONG_TEST_KEY = "unit-test-only-secret-key-" + ("x" * 40)
assert len(_STRONG_TEST_KEY) >= 64

# Documented .env.example placeholder and close variants (denylist).
_PLACEHOLDER = "change-me-to-a-long-random-string"
_PLACEHOLDER_VARIANTS = (
    _PLACEHOLDER,
    _PLACEHOLDER.upper(),
    f"  {_PLACEHOLDER}  ",
    "change-me",
)


def _settings(**kwargs) -> Settings:
    """Build Settings from kwargs only (ignore process .env)."""
    return Settings(_env_file=None, **kwargs)


def test_secret_key_placeholder_from_env_example_is_rejected(monkeypatch):
    """Documented .env.example placeholder must not load Settings."""
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        _settings(secret_key=_PLACEHOLDER)


@pytest.mark.parametrize("placeholder", _PLACEHOLDER_VARIANTS)
def test_secret_key_change_me_placeholders_are_rejected(monkeypatch, placeholder):
    """change-me style placeholders (incl. case/whitespace variants) fail load."""
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        _settings(secret_key=placeholder)


def test_secret_key_shorter_than_64_is_rejected(monkeypatch):
    """Keys shorter than 64 characters must fail Settings validation."""
    monkeypatch.delenv("SECRET_KEY", raising=False)
    short = "unit-test-secret-key-for-ci-only-32chars!"  # legacy conftest length
    assert len(short) < 64
    with pytest.raises(ValidationError):
        _settings(secret_key=short)


def test_secret_key_empty_is_rejected(monkeypatch):
    """Empty secret_key must fail Settings validation."""
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        _settings(secret_key="")


def test_secret_key_whitespace_only_is_rejected(monkeypatch):
    """Whitespace-only secret_key must fail Settings validation."""
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        _settings(secret_key="   ")


def test_secret_key_missing_still_fails_control(monkeypatch):
    """Control twin: omitting secret_key still fails fail-fast (required field)."""
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        _settings()


def test_secret_key_strong_non_placeholder_loads_control(monkeypatch):
    """Control twin: ≥64 non-placeholder key constructs Settings normally."""
    monkeypatch.delenv("SECRET_KEY", raising=False)
    settings = _settings(secret_key=_STRONG_TEST_KEY)
    assert settings.secret_key == _STRONG_TEST_KEY
    assert len(settings.secret_key) >= 64


def test_placeholder_padded_to_64_still_rejected(monkeypatch):
    """Padding the documented placeholder to ≥64 must not bypass the denylist."""
    monkeypatch.delenv("SECRET_KEY", raising=False)
    padded = _PLACEHOLDER + ("x" * (64 - len(_PLACEHOLDER)))
    assert len(padded) >= 64
    with pytest.raises(ValidationError):
        _settings(secret_key=padded)
