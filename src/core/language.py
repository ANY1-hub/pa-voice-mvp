"""Language heuristics for TTS voice selection and skill replies."""

from __future__ import annotations

import re
import unicodedata

# ő/ű are Hungarian-only. áéíóú are not used in German (except rare loans).
# ö/ü are shared with German and must not decide the language on their own.
_HU_CHARS = set("őűŐŰáéíóúÁÉÍÓÚ")
_DE_ONLY_CHARS = set("äßÄ")
_SHARED_UMLAUTS = set("öüÖÜ")
_HU_WORDS = re.compile(
    r"\b(hogy|nem|egy|és|vagy|ez|az|igen|köszönöm|szia|tudom|rólam|kérem|"
    r"elmentettem|emlékeztess|jegyzeteld)\b",
    re.IGNORECASE,
)
_DE_WORDS = re.compile(
    r"\b(und|der|die|das|ich|nicht|ist|ein|eine|mit|für|auf|wir)\b",
    re.IGNORECASE,
)


def _nfc(text: str) -> str:
    """Compose combining accents so ő/ű match the precomposed character set."""
    return unicodedata.normalize("NFC", text or "")


def _hint_code(hint: str | None) -> str | None:
    if not hint:
        return None
    code = hint.lower().strip()[:2]
    return code if code in {"en", "de", "hu"} else None


def heuristic_language(text: str) -> str | None:
    """Return a language code from function words, or None."""
    text = _nfc(text)
    if _HU_WORDS.search(text):
        return "hu"
    if _DE_WORDS.search(text):
        return "de"
    return None


def detect_response_language(text: str, hint: str | None = None) -> str:
    """Guess language for TTS / skill replies.

    Hungarian-only letters beat a stale hint. Shared ö/ü do not, so
    ``Köszönöm`` stays Hungarian when the UI/STT hint is ``hu``.

    Args:
        text: User or assistant text to inspect.
        hint: Optional language code from STT (``"en"``, ``"de"``, ``"hu"``).

    Returns:
        One of ``"en"``, ``"de"``, ``"hu"``.
    """
    text = _nfc(text)
    hint_code = _hint_code(hint)

    if any(c in _HU_CHARS for c in text):
        return "hu"
    if any(c in _DE_ONLY_CHARS for c in text):
        return "de"
    if _HU_WORDS.search(text):
        return "hu"

    if hint_code in {"de", "hu"}:
        return hint_code

    if any(c in _SHARED_UMLAUTS for c in text):
        return "de"
    if hint_code:
        return hint_code

    return heuristic_language(text) or "en"
