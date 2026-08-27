"""Language heuristics for TTS voice selection and skill replies."""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

# ő/ű are Hungarian-only. áéíóú are not used in German (except rare loans).
# ö/ü are shared with German and must not decide the language on their own.
_HU_CHARS = set("őűŐŰáéíóúÁÉÍÓÚ")
_DE_ONLY_CHARS = set("äßÄ")
_SHARED_UMLAUTS = set("öüÖÜ")
_NAME_ACCENT_CHARS = set("áéíóúöüőűÁÉÍÓÚÖÜŐŰ")
_NAMES_PATH = Path(__file__).resolve().parent / "data" / "hungarian_given_names.json"
_HU_WORDS = re.compile(
    r"\b(hogy|nem|egy|és|vagy|ez|az|igen|köszönöm|szia|tudom|rólam|kérem|"
    r"elmentettem|emlékeztess|jegyzeteld|milyen|holnap|kérlek|köszi|miért)\b",
    re.IGNORECASE,
)
# Short agenda/smalltalk without ő/ű. Do not list bare van/mi/ma (English collisions).
_HU_PHRASES = re.compile(
    r"\b(mi van|mi a|hol van|van ma)\b",
    re.IGNORECASE,
)
_DE_WORDS = re.compile(
    r"\b(und|der|die|das|ich|nicht|ist|ein|eine|mit|für|auf|wir)\b",
    re.IGNORECASE,
)
# Beat a stale English hint. Omit bare die/mit/ist so English is not flipped.
_DE_STRONG = re.compile(
    r"\b(ich|nicht|und|wir|eine|für|bitte|danke|bin|haben|keine?|"
    r"aber|oder|wenn|weil|dass|mein|meine|mir|dir|wie|geht|"
    r"notiz|merke?|heute|steht)\b",
    re.IGNORECASE,
)
_EN_STRONG = re.compile(
    r"\b(the|and|you|what|how|have|this|that|with|your|"
    r"don't|can't|hello|thanks|tell|about|story|please|"
    r"remind|today|are|short|minutes?|once|stretch|me)\b",
    re.IGNORECASE,
)


@lru_cache(maxsize=1)
def load_hungarian_given_names() -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Load male and female given names whose accents must not pick TTS language."""
    payload = json.loads(_NAMES_PATH.read_text(encoding="utf-8"))
    male = tuple(_nfc(n) for n in payload["male"])
    female = tuple(_nfc(n) for n in payload["female"])
    return male, female


def hungarian_names_with_accents() -> tuple[str, ...]:
    """All listed given names (male + female) used as TTS language exclusions."""
    male, female = load_hungarian_given_names()
    return male + female


def _nfc(text: str) -> str:
    """Compose combining accents so ő/ű match the precomposed character set."""
    return unicodedata.normalize("NFC", text or "")


def _hint_code(hint: str | None) -> str | None:
    if not hint:
        return None
    code = hint.lower().strip()[:2]
    return code if code in {"en", "de", "hu"} else None


def normalize_language_code(hint: str | None) -> str | None:
    """Return ``en`` / ``de`` / ``hu``, or ``None`` for auto-detect."""
    return _hint_code(hint)


def heuristic_language(text: str) -> str | None:
    """Return a language code from function words, or None."""
    text = _nfc(text)
    if _HU_PHRASES.search(text) or _HU_WORDS.search(text):
        return "hu"
    if _DE_WORDS.search(text):
        return "de"
    return None


def _names_to_strip(ignore: str | None) -> tuple[str, ...]:
    extra = _nfc(ignore or "").strip()
    names = list(hungarian_names_with_accents())
    if len(extra) >= 2 and extra.casefold() not in {n.casefold() for n in names}:
        names.append(extra)
    names.sort(key=len, reverse=True)
    return tuple(names)


def _without_ignored(text: str, ignore: str | None) -> str:
    """Remove listed / display names so their accents cannot pick the TTS voice."""
    text = _nfc(text)
    for name in _names_to_strip(ignore):
        text = re.sub(rf"(?i)(?<!\w){re.escape(name)}(?!\w)", " ", text)
    return text


def detect_response_language(
    text: str,
    hint: str | None = None,
    *,
    ignore: str | None = None,
) -> str:
    """Guess language for TTS / skill replies.

    Hungarian letters including áéíóú beat a stale hint. Shared ö/ü do not.
    Short Hungarian phrases (``mi van``, ``van ma``) and strong German or
    English function words beat a Help-panel / STT hint so this utterance
    wins. Accents inside a listed Hungarian given name or ``ignore``
    (display name) are stripped first so they do not pick the voice.

    Args:
        text: User or assistant text to inspect.
        hint: Optional language code from STT (``"en"``, ``"de"``, ``"hu"``).
        ignore: Optional display name whose letters must not affect the guess.

    Returns:
        One of ``"en"``, ``"de"``, ``"hu"``.
    """
    text = _without_ignored(text, ignore)
    hint_code = _hint_code(hint)

    if any(c in _HU_CHARS for c in text):
        return "hu"
    if any(c in _DE_ONLY_CHARS for c in text):
        return "de"
    if _HU_PHRASES.search(text) or _HU_WORDS.search(text):
        return "hu"
    if _DE_STRONG.search(text):
        return "de"
    if _EN_STRONG.search(text):
        return "en"

    if hint_code in {"de", "hu"}:
        return hint_code

    if any(c in _SHARED_UMLAUTS for c in text):
        return "de"
    if hint_code:
        return hint_code

    return heuristic_language(text) or "en"
