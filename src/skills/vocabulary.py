"""Canonical spoken trigger phrases for each skill (EN / DE / HU).

Ten everyday phrases per skill per language, taken from how people actually
talk to Siri / Google Assistant / Alexa and from common DE/HU equivalents.
Skills compile these into matchers; the help panel lists the same set for
the selected language only.
"""

from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------

NOTES_CREATE: dict[str, list[str]] = {
    "en": [
        "remember this",
        "save a note",
        "make a note",
        "take a note",
        "jot this down",
        "write this down",
        "add a note",
    ],
    "de": [
        "merk dir das",
        "merk dir",
        "schreib auf",
        "notiere das",
        "speichere eine notiz",
        "halte fest",
        "neue notiz",
    ],
    "hu": [
        "jegyzeteld",
        "jegyezd meg",
        "írd fel",
        "mentsd el",
        "új jegyzet",
        "jegyzeteld le",
        "írd le",
    ],
}

NOTES_LIST: dict[str, list[str]] = {
    "en": [
        "list my notes",
        "show my notes",
        "what notes do I have",
    ],
    "de": [
        "meine notizen",
        "notizen zeigen",
        "welche notizen habe ich",
    ],
    "hu": [
        "listázd a jegyzeteket",
        "mutasd a jegyzeteimet",
        "milyen jegyzeteim vannak",
    ],
}

# Short legacy keywords still accepted (not shown on the help page).
NOTES_CREATE_EXTRA = ["note", "notiz", "jegyzet", "save note", "notiere"]
NOTES_LIST_EXTRA = ["list notes", "show notes", "what notes"]

# ---------------------------------------------------------------------------
# Reminders
# ---------------------------------------------------------------------------

REMINDERS_CREATE: dict[str, list[str]] = {
    "en": [
        "remind me",
        "set a reminder",
        "add a reminder",
        "don't let me forget",
    ],
    "de": [
        "erinner mich",
        "erinnere mich",
        "stell eine erinnerung",
        "vergiss nicht",
    ],
    "hu": [
        "emlékeztess",
        "állíts be emlékeztetőt",
        "ne felejtsem el",
        "új emlékeztető",
    ],
}

REMINDERS_LIST: dict[str, list[str]] = {
    "en": [
        "show my reminders",
        "list reminders",
    ],
    "de": [
        "meine erinnerungen",
        "zeig mir die erinnerungen",
    ],
    "hu": [
        "listázd az emlékeztetőket",
        "mutasd az emlékeztetőket",
    ],
}

REMINDERS_AGENDA: dict[str, list[str]] = {
    "en": [
        "what's on today",
        "what's on this week",
        "what's my agenda",
    ],
    "de": [
        "was steht heute an",
        "was steht diese woche an",
        "mein kalender",
    ],
    "hu": [
        "mi van ma a naptáramban",
        "mi van a héten",
        "a naptáram",
    ],
}

REMINDERS_LOOKUP: dict[str, list[str]] = {
    "en": [
        "when is my",
    ],
    "de": [
        "wann habe ich",
    ],
    "hu": [
        "mikor van a",
    ],
}

REMINDERS_CREATE_EXTRA = [
    "reminder",
    "erinnerung",
    "set a reminder",
]
REMINDERS_LIST_EXTRA = [
    "show reminders",
    "what reminders",
    "erinnerungen zeigen",
]
REMINDERS_AGENDA_EXTRA = [
    "was steht",
    "what's on",
    "what is on",
    "what is next week",
    "what's on next week",
    "what's on this month",
    "was steht diesen monat",
    "was steht nächste woche",
    "agenda",
    "jövő héten",
    "ebben a hónapban",
    "ezen a héten",
]
REMINDERS_LOOKUP_EXTRA = [
    "when is",
    "when do i",
    "when was",
    "when did",
    "when should",
    "when do i have",
    "wann muss ich",
    "wann ist",
    "wann war",
    "wann soll",
]

# ---------------------------------------------------------------------------
# Web search
# ---------------------------------------------------------------------------

WEB_SEARCH: dict[str, list[str]] = {
    "en": [
        "search for",
        "look up",
        "look that up",
        "google",
        "find out",
        "what is",
        "who is",
        "search the web",
        "can you search",
        "search the internet",
    ],
    "de": [
        "suche nach",
        "suche im internet",
        "schlag nach",
        "finde heraus",
        "google",
        "was ist",
        "wer ist",
        "recherchiere",
        "such mal",
        "im web suchen",
    ],
    "hu": [
        "keress rá",
        "keresd meg",
        "googlezd",
        "nézz utána",
        "mi az",
        "ki az",
        "keress az interneten",
        "tudakold meg",
        "keresés",
        "utánanéznél",
    ],
}

WEB_SEARCH_EXTRA = ["search", "lookup", "suche", "finde", "nachschlagen", "keress"]

# ---------------------------------------------------------------------------
# Active recall
# ---------------------------------------------------------------------------

ACTIVE_RECALL: dict[str, list[str]] = {
    "en": [
        "what do you know about me",
        "what do you know about",
        "what do you remember about",
        "what did I tell you about",
        "remind me what I said about",
        "remind me what I told you about",
        "my preferences",
        "what do you remember",
        "what have I told you",
        "recall what you know about",
    ],
    "de": [
        "was weißt du über mich",
        "was weißt du über",
        "was erinnerst du dich an",
        "was habe ich dir gesagt",
        "meine vorlieben",
        "was weißt du noch",
        "was merkst du dir über mich",
        "was weißt du von mir",
        "meine präferenzen",
        "was weißt du",
    ],
    "hu": [
        "mit tudsz rólam",
        "mit tudsz erről",
        "mire emlékszel",
        "mit mondtam neked",
        "a preferenciáim",
        "mit jegyeztél meg",
        "mit tudsz még rólam",
        "mire emlékszel, mit mondtam",
        "mit tudsz",
        "milyen vagyok",
    ],
}

ACTIVE_RECALL_EXTRA = [
    "what do you know",
    "was weißt du noch über",
    "was weißt du noch von",
]

# ---------------------------------------------------------------------------
# Personal facts (Conversation → Semantic Memory, not a routed skill)
# How people tell Siri / Google / Alexa something to remember about them.
# Must not collide with Notes / Reminders trigger phrases.
# ---------------------------------------------------------------------------

PERSONAL_FACTS: dict[str, list[str]] = {
    "en": [
        "my name is",
        "I live in",
        "I work as",
        "I like",
        "I prefer",
        "I'm allergic to",
        "my favourite",
        "remember that I",
        "I am from",
        "my birthday is",
        "I was born in",
        "I was born on the",
    ],
    "de": [
        "ich heiße",
        "ich wohne in",
        "ich arbeite als",
        "ich mag",
        "ich bevorzuge",
        "ich bin allergisch",
        "mein lieblings",
        "ich komme aus",
        "nenn mich",
        "mein geburtstag ist",
    ],
    "hu": [
        "a nevem",
        "lakom",
        "dolgozom",
        "szeretek",
        "a kedvencem",
        "allergiás vagyok",
        "származom",
        "hívj",
        "a születésnapom",
        "születtem",
        "imádom",
        "nagyon szeretem",
    ],
}


def _flatten(
    *groups: dict[str, list[str]], extra: list[str] | None = None
) -> list[str]:
    phrases: list[str] = []
    for group in groups:
        for items in group.values():
            phrases.extend(items)
    if extra:
        phrases.extend(extra)
    # Longest first so "what do you know about me" wins over "what do you know".
    uniq = sorted(set(phrases), key=len, reverse=True)
    return uniq


def _fold_char(ch: str) -> str:
    """Casefold one character and strip combining marks (ő→o, ß→ss)."""
    nfd = unicodedata.normalize("NFD", ch.casefold())
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def fold_text(text: str) -> str:
    """Accent-insensitive, case-insensitive form for matching."""
    return "".join(_fold_char(ch) for ch in text)


def _fold_with_map(text: str) -> tuple[str, list[int]]:
    """Folded string plus map from folded index to original index."""
    folded: list[str] = []
    mapping: list[int] = []
    for i, ch in enumerate(text):
        for piece in _fold_char(ch):
            folded.append(piece)
            mapping.append(i)
    return "".join(folded), mapping


def _token_pattern(token: str) -> str:
    """Allow an inflection tail on long or non-ASCII (HU/DE) tokens.

    ASCII keywords such as ``reminder`` stay exact so ``show reminders``
    is not stolen by the create extra ``reminder``.
    """
    inflect = len(token) >= 11 or (len(token) >= 6 and not token.isascii())
    if inflect:
        stem_len = max(6, len(token) - 3)
        return re.escape(token[:stem_len]) + r"\w*"
    return re.escape(token)


def _max_gap(lang: str | None, phrase: str) -> int:
    """Hungarian allows three fillers (kérlek egy új …)."""
    if lang == "hu":
        return 3
    if lang is None and any(ord(c) > 127 for c in phrase):
        return 3
    return 2


def _phrase_pattern(phrase: str, max_gap: int = 2) -> str:
    """Tokens in order with up to ``max_gap`` filler words between them."""
    tokens = phrase.split()
    if not tokens:
        return ""
    gap = rf"(?:\s+\S+){{0,{max_gap}}}\s+"
    parts = [_token_pattern(tokens[0])]
    for tok in tokens[1:]:
        parts.append(gap)
        parts.append(_token_pattern(tok))
    return "".join(parts)


class PhraseMatcher:
    """Search/sub on accent-folded text; spans map back to the original."""

    def __init__(self, pattern: re.Pattern[str]) -> None:
        self._pattern = pattern

    def search(self, text: str) -> re.Match[str] | None:
        """Return a match against the folded utterance, or None."""
        folded, _ = _fold_with_map(text)
        return self._pattern.search(folded)

    def sub(self, repl: str, text: str, count: int = 0) -> str:
        """Replace matches in the original string (folded matching)."""
        folded, mapping = _fold_with_map(text)
        limit = 0 if count == 0 else count
        out = text
        offset = 0
        for n, m in enumerate(self._pattern.finditer(folded), start=1):
            orig_start = mapping[m.start()] if m.start() < len(mapping) else len(text)
            orig_end = mapping[m.end()] if m.end() < len(mapping) else len(text)
            orig_start += offset
            orig_end += offset
            out = out[:orig_start] + repl + out[orig_end:]
            offset += len(repl) - (orig_end - orig_start)
            if limit and n >= limit:
                break
        return out


def compile_phrase_regex(
    *groups: dict[str, list[str]], extra: list[str] | None = None
) -> PhraseMatcher:
    """Matcher for spoken phrases: order-preserving, gappy, stem-tolerant.

    Accents are folded so STT without diacritics still hits. Tokens of
    length 6+ allow an inflection tail. Up to two filler words (three in
    Hungarian) may appear between tokens (please / kérlek egy új).
    """
    scored: list[tuple[int, str]] = []
    for group in groups:
        for lang, items in group.items():
            gap = _max_gap(lang, "")
            for raw in items:
                phrase = raw.strip()
                if not phrase:
                    continue
                scored.append((len(phrase), _phrase_pattern(fold_text(phrase), gap)))
    for raw in extra or []:
        phrase = raw.strip()
        if not phrase:
            continue
        gap = _max_gap(None, phrase)
        scored.append((len(phrase), _phrase_pattern(fold_text(phrase), gap)))
    scored.sort(key=lambda item: item[0], reverse=True)
    parts = [pattern for _, pattern in scored]
    combined = r"(?i)(?<!\w)(?:" + "|".join(parts) + r")(?!\w)"
    return PhraseMatcher(re.compile(combined))


def help_catalog(lang: str) -> dict[str, list[str]]:
    """Ten display phrases per skill for one UI language."""
    if lang not in {"en", "de", "hu"}:
        lang = "en"
    return {
        "notes": NOTES_CREATE[lang] + NOTES_LIST[lang],
        "reminders": (
            REMINDERS_CREATE[lang]
            + REMINDERS_LIST[lang]
            + REMINDERS_AGENDA[lang]
            + REMINDERS_LOOKUP[lang]
        ),
        "web_search": WEB_SEARCH[lang],
        "active_recall": ACTIVE_RECALL[lang],
        "personal_facts": PERSONAL_FACTS[lang],
    }
