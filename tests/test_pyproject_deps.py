"""Declared extras stay on httpx; Docker does not use a second requirements file."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_PYPROJECT = _ROOT / "pyproject.toml"


def test_httpx2_is_not_an_extra():
    """httpx2 was a stray extra; TestClient uses httpx."""
    text = _PYPROJECT.read_text(encoding="utf-8")
    assert '"httpx2"' not in text
    assert '"httpx"' in text


def test_no_committed_requirements_txt():
    """Lockfile is the install source; a second list would drift."""
    assert not (_ROOT / "requirements.txt").exists()


def test_jwt_dependency_is_pyjwt_not_python_jose():
    """python-jose pulls unfixed ecdsa; JWT is PyJWT + cryptography."""
    text = _PYPROJECT.read_text(encoding="utf-8")
    assert "python-jose" not in text
    assert "pyjwt" in text.lower()
