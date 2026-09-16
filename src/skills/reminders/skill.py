"""RemindersSkill – create, list, agenda and lookup with optional due_at."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta, tzinfo
from difflib import SequenceMatcher
from typing import Any

from src.core.timezones import to_utc, zoneinfo_or_utc
from src.memory.semantic_memory import SemanticMemory
from src.models.reminder import Reminder
from src.services.llm.base import LLMAdapter
from src.skills.base import Skill, SkillResult
from src.skills.reminders.repository import ReminderRepository
from src.skills.reminders.slots import extract_reminder_slots
from src.skills.replies import reply_language
from src.skills.vocabulary import (
    REMINDERS_AGENDA,
    REMINDERS_AGENDA_EXTRA,
    REMINDERS_CREATE,
    REMINDERS_CREATE_EXTRA,
    REMINDERS_DELETE,
    REMINDERS_DELETE_EXTRA,
    REMINDERS_LIST,
    REMINDERS_LIST_EXTRA,
    REMINDERS_LOOKUP,
    REMINDERS_LOOKUP_EXTRA,
    compile_phrase_regex,
)

REMINDER_FACT_PREFIX = "User set a reminder:"

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Intent patterns
# ---------------------------------------------------------------------------

_CREATE_PATTERNS = compile_phrase_regex(REMINDERS_CREATE, extra=REMINDERS_CREATE_EXTRA)
_LIST_PATTERNS = compile_phrase_regex(REMINDERS_LIST, extra=REMINDERS_LIST_EXTRA)
_AGENDA_PATTERNS = compile_phrase_regex(REMINDERS_AGENDA, extra=REMINDERS_AGENDA_EXTRA)
_LOOKUP_PATTERNS = compile_phrase_regex(REMINDERS_LOOKUP, extra=REMINDERS_LOOKUP_EXTRA)
_DELETE_PATTERNS = compile_phrase_regex(REMINDERS_DELETE, extra=REMINDERS_DELETE_EXTRA)

# Relative date tokens
_TOMORROW = re.compile(r"\b(tomorrow|morgen|holnap)\b", re.IGNORECASE)
_TODAY = re.compile(r"\b(today|heute|ma)\b", re.IGNORECASE)
_NUMERIC_DATE = re.compile(r"\b(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?\b")
_DAY_AFTER = re.compile(r"\b(übermorgen|day after tomorrow)\b", re.IGNORECASE)

_MONTH_INDEX: dict[str, int] = {
    "january": 1,
    "januar": 1,
    "január": 1,
    "february": 2,
    "februar": 2,
    "február": 2,
    "march": 3,
    "märz": 3,
    "marz": 3,
    "március": 3,
    "marcius": 3,
    "april": 4,
    "április": 4,
    "aprilis": 4,
    "may": 5,
    "mai": 5,
    "május": 5,
    "majus": 5,
    "june": 6,
    "juni": 6,
    "június": 6,
    "junius": 6,
    "july": 7,
    "juli": 7,
    "július": 7,
    "julius": 7,
    "august": 8,
    "augusztus": 8,
    "september": 9,
    "october": 10,
    "oktober": 10,
    "október": 10,
    "november": 11,
    "december": 12,
    "dezember": 12,
}
_MONTH_ALT = "|".join(
    sorted((re.escape(n) for n in _MONTH_INDEX), key=len, reverse=True)
)
_NAMED_DAY_MONTH = re.compile(
    rf"\b(\d{{1,2}})\.?\s+({_MONTH_ALT})\b",
    re.IGNORECASE,
)
_NAMED_MONTH_DAY = re.compile(
    rf"\b({_MONTH_ALT})\s+(\d{{1,2}})\b",
    re.IGNORECASE,
)
_WEEK_BEFORE = re.compile(
    r"\b(?:(?:eine?|1)\s+)?woche\s+vorher\b|"
    r"\ba\s+week\s+before\b|"
    r"\b(?:egy\s+)?héttel\s+(?:korábban|el[oöő]bb)\b",
    re.IGNORECASE,
)

_WEEKDAYS = {
    "monday": 0,
    "montag": 0,
    "tuesday": 1,
    "dienstag": 1,
    "wednesday": 2,
    "mittwoch": 2,
    "thursday": 3,
    "donnerstag": 3,
    "friday": 4,
    "freitag": 4,
    "saturday": 5,
    "samstag": 5,
    "sunday": 6,
    "sonntag": 6,
}
_WEEKDAY_RE = re.compile(r"\b(" + "|".join(_WEEKDAYS.keys()) + r")\b", re.IGNORECASE)

# Time: "um 14 Uhr", "at 14:00", "14:30", "um 9"
_TIME_RE = re.compile(
    r"(?:um|at)\s*(\d{1,2})(?:[:.](\d{2}))?\s*(?:uhr)?" r"|\b(\d{1,2})[:.](\d{2})\b",
    re.IGNORECASE,
)

# Relative wait: "in 2 minutes", "in two/zwei Minuten", "két perc múlva"
_WORD_TO_INT: dict[str, int] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eins": 1,
    "zwei": 2,
    "drei": 3,
    "vier": 4,
    "fünf": 5,
    "fuenf": 5,
    "sechs": 6,
    "sieben": 7,
    "acht": 8,
    "neun": 9,
    "zehn": 10,
    "egy": 1,
    "két": 2,
    "ket": 2,
    "kettő": 2,
    "ketto": 2,
    "három": 3,
    "harom": 3,
    "négy": 4,
    "negy": 4,
    "öt": 5,
    "ot": 5,
    "hat": 6,
    "hét": 7,
    "het": 7,
    "nyolc": 8,
    "kilenc": 9,
    "tíz": 10,
    "tiz": 10,
}
_WORD_ALT = "|".join(
    sorted((re.escape(w) for w in _WORD_TO_INT), key=len, reverse=True)
)
_RELATIVE_IN = re.compile(
    r"\bin\s+(?:einer|einem|one|a)\s+"
    r"(minutes?|mins?|minuten|minute|hours?|hrs?|stunden|stunde)\b",
    re.IGNORECASE,
)
_RELATIVE_N = re.compile(
    rf"\bin\s+(\d+|{_WORD_ALT})\s*"
    r"(minutes?|mins?|minuten|minute|hours?|hrs?|stunden|stunde)\b",
    re.IGNORECASE,
)
_RELATIVE_HU = re.compile(
    rf"\b(\d+|{_WORD_ALT})\s*(perc|óra)\s*múlva\b",
    re.IGNORECASE,
)


def _parse_count(raw: str) -> int:
    """Parse a digit or EN/DE/HU number word (~1–10) to int."""
    cleaned = raw.strip().casefold()
    if cleaned.isdigit():
        return int(cleaned)
    return _WORD_TO_INT[cleaned]


def _now_utc() -> datetime:
    """Return current UTC time (patchable in tests)."""
    return datetime.now(UTC)


def _parse_time(text: str) -> tuple[int, int] | None:
    """Extract (hour, minute) from text or return None."""
    m = _TIME_RE.search(text)
    if not m:
        return None
    if m.group(1) is not None:
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
    else:
        hour = int(m.group(3))
        minute = int(m.group(4))
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return hour, minute
    return None


def _unit_to_delta(n: int, unit: str) -> timedelta:
    """Map a spoken duration unit to a timedelta."""
    key = unit.lower()
    if key.startswith("perc") or key.startswith("min"):
        return timedelta(minutes=n)
    return timedelta(hours=n)


def _parse_relative_duration(text: str, now: datetime) -> datetime | None:
    """Parse 'in N minutes' / 'in two minutes' / 'in einer Stunde' / 'N perc múlva'."""
    m = _RELATIVE_HU.search(text)
    if m:
        return now + _unit_to_delta(_parse_count(m.group(1)), m.group(2))
    m = _RELATIVE_N.search(text)
    if m:
        return now + _unit_to_delta(_parse_count(m.group(1)), m.group(2))
    m = _RELATIVE_IN.search(text)
    if m:
        return now + _unit_to_delta(1, m.group(1))
    return None


def _named_month_date(text: str, year: int, tz: tzinfo) -> datetime | None:
    """Parse '29. August' / 'August 29' in ``year``, or None."""
    named = _NAMED_DAY_MONTH.search(text)
    if named:
        day = int(named.group(1))
        month = _MONTH_INDEX[named.group(2).casefold()]
    else:
        named = _NAMED_MONTH_DAY.search(text)
        if not named:
            return None
        month = _MONTH_INDEX[named.group(1).casefold()]
        day = int(named.group(2))
    try:
        return datetime(year, month, day, tzinfo=tz)
    except ValueError:
        return None


def _roll_future(base: datetime, now_local: datetime) -> datetime:
    """If ``base`` is already past, use the same calendar day next year."""
    if base > now_local:
        return base
    try:
        return base.replace(year=base.year + 1)
    except ValueError:
        return base + timedelta(days=365)


def _parse_due(text: str, timezone: str | None = None) -> datetime | None:  # noqa: C901
    """Parse a simple relative date (+ optional time) from free text.

    Clock times are the user's local wall clock (IANA ``timezone``). Relative
    waits (in N minutes) are offsets from now. Stored value is always UTC.
    """
    now_utc = _now_utc()
    relative = _parse_relative_duration(text, now_utc)
    if relative is not None:
        return to_utc(relative)

    tz = zoneinfo_or_utc(timezone)
    now_local = now_utc.astimezone(tz)
    base: datetime | None = None
    roll_year = False

    numeric = _NUMERIC_DATE.search(text)
    if numeric:
        day = int(numeric.group(1))
        month = int(numeric.group(2))
        year_raw = numeric.group(3)
        if year_raw:
            year = int(year_raw)
            if year < 100:
                year += 2000
        else:
            year = now_local.year
        try:
            base = datetime(year, month, day, tzinfo=tz)
        except ValueError:
            base = None

    if base is None:
        base = _named_month_date(text, now_local.year, tz)
        if base is not None:
            roll_year = True

    if base is None and _DAY_AFTER.search(text):
        base = (now_local + timedelta(days=2)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    elif base is None and _TOMORROW.search(text):
        base = (now_local + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    elif base is None and _TODAY.search(text):
        base = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    elif base is None:
        wd = _WEEKDAY_RE.search(text)
        if wd:
            target = _WEEKDAYS[wd.group(1).lower()]
            days_ahead = (target - now_local.weekday()) % 7
            t_preview = _parse_time(text)
            if days_ahead == 0 and t_preview:
                hour, minute = t_preview
                same_day = now_local.replace(
                    hour=hour, minute=minute, second=0, microsecond=0
                )
                days_ahead = 0 if same_day > now_local else 7
            elif days_ahead == 0:
                days_ahead = 7  # next occurrence, not today
            base = (now_local + timedelta(days=days_ahead)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

    t = _parse_time(text)
    if base is None:
        # Time of day without a date token → today, or tomorrow if already past.
        if t is None:
            return None
        hour, minute = t
        candidate = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now_local:
            candidate += timedelta(days=1)
        return to_utc(candidate)

    if t:
        hour, minute = t
        base = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if _WEEK_BEFORE.search(text):
        base = base - timedelta(days=7)
        roll_year = True
    if roll_year:
        base = _roll_future(base, now_local)
    return to_utc(base)


def _strip_date_tokens(text: str) -> str:
    """Remove date/time tokens so the remaining text is clean content."""
    cleaned = _CREATE_PATTERNS.sub("", text)
    cleaned = _TOMORROW.sub("", cleaned)
    cleaned = _TODAY.sub("", cleaned)
    cleaned = _DAY_AFTER.sub("", cleaned)
    cleaned = _WEEKDAY_RE.sub("", cleaned)
    cleaned = _TIME_RE.sub("", cleaned)
    cleaned = _NUMERIC_DATE.sub("", cleaned)
    cleaned = _NAMED_DAY_MONTH.sub("", cleaned)
    cleaned = _NAMED_MONTH_DAY.sub("", cleaned)
    cleaned = _WEEK_BEFORE.sub("", cleaned)
    cleaned = _RELATIVE_HU.sub("", cleaned)
    cleaned = _RELATIVE_N.sub("", cleaned)
    cleaned = _RELATIVE_IN.sub("", cleaned)
    cleaned = re.sub(
        r"\b(an den|an die|an das|an|to|um|at|on|für|dem|den|die|das|"
        r"eine|einen|einer|einem|zum|zur|bitte|for)\b",
        "",
        cleaned,
        flags=re.I,
    )
    return re.sub(r"\s+", " ", cleaned).strip(" :,-.").strip()


def _format_due(due: datetime | None, timezone: str | None = None) -> str:
    """Human-readable due string in the user's local wall clock."""
    if due is None:
        return ""
    local = due.astimezone(zoneinfo_or_utc(timezone))
    date_part = local.strftime("%Y-%m-%d")
    if local.hour or local.minute:
        return f"{date_part} {local.strftime('%H:%M')}"
    return date_part


def _agenda_range(
    text: str, timezone: str | None = None
) -> tuple[datetime, datetime] | None:
    """Return UTC (due_from, due_to) for known agenda phrases, else None.

    Day/week/month boundaries follow the user's local calendar.
    """
    tz = zoneinfo_or_utc(timezone)
    now_local = _now_utc().astimezone(tz)
    today_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    lower = text.lower()

    def _utc_window(start: datetime, end: datetime) -> tuple[datetime, datetime]:
        return to_utc(start), to_utc(end)

    # Next-week before this-week: "jövő héten" also contains "héten".
    if re.search(r"\b(nächste woche|next week|jövő héten|jövő hét)\b", lower):
        start = today_start - timedelta(days=today_start.weekday()) + timedelta(days=7)
        end = start + timedelta(days=7) - timedelta(microseconds=1)
        return _utc_window(start, end)

    if re.search(r"\b(diese woche|this week|a héten|ezen a héten)\b", lower):
        start = today_start - timedelta(days=today_start.weekday())
        end = start + timedelta(days=7) - timedelta(microseconds=1)
        return _utc_window(start, end)

    if re.search(r"\b(diesen monat|dieser monat|this month|ebben a hónapban)\b", lower):
        start = today_start.replace(day=1)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        end = end - timedelta(microseconds=1)
        return _utc_window(start, end)

    if re.search(r"\b(heute|today|ma)\b", lower):
        end = today_start + timedelta(days=1) - timedelta(microseconds=1)
        return _utc_window(today_start, end)

    return None


def _lookup_keyword(text: str) -> str:
    """Extract a reasonable search keyword from a lookup question."""
    # Remove the question prefix, keep the rest
    cleaned = _LOOKUP_PATTERNS.sub("", text)
    cleaned = re.sub(
        r"\b(habe ich|muss ich|do i have|is my|my|den|die|das|termin|appointment|"
        r"anrufen|call|bei|at|the)\b",
        "",
        cleaned,
        flags=re.I,
    )
    cleaned = cleaned.strip(" ?!.,").strip()
    # Prefer the longest remaining token group
    return cleaned if len(cleaned) >= 2 else text.strip()


def _delete_keyword(text: str) -> str:
    """Extract the reminder content the user wants cancelled."""
    cleaned = _DELETE_PATTERNS.sub("", text)
    cleaned = re.sub(
        r"\b(please|then|the|a|an|my|titled|called|named|bitte|dann|"
        r"kérlek|az|egy|für|for|to)\b",
        "",
        cleaned,
        flags=re.I,
    )
    return cleaned.strip(" ?!.,").strip()


_FUZZY_MIN_RATIO = 0.75
_FUZZY_MIN_MARGIN = 0.12


def _norm_match(text: str) -> str:
    """Collapse punctuation so 'habe' can be compared to 'have a ?'."""
    return re.sub(r"[^\w]+", " ", text.casefold(), flags=re.UNICODE).strip()


def _best_fuzzy_match(keyword: str, labelled: list[tuple[str, Any]]) -> Any | None:
    """Return the unique close match for a mistyped delete target, or None."""
    key = _norm_match(keyword)
    if len(key) < 6:
        return None
    scored: list[tuple[float, Any]] = []
    for label, item in labelled:
        label_n = _norm_match(label)
        if not label_n:
            continue
        if key in label_n or label_n in key:
            return item
        scored.append((SequenceMatcher(None, key, label_n).ratio(), item))
    if not scored:
        return None
    scored.sort(key=lambda row: row[0], reverse=True)
    best_ratio, best = scored[0]
    if best_ratio < _FUZZY_MIN_RATIO:
        return None
    if len(scored) > 1 and scored[1][0] >= best_ratio - _FUZZY_MIN_MARGIN:
        return None
    return best


_REPLIES: dict[str, dict[str, str]] = {
    "en": {
        "need_content": "I need a bit more content for the reminder.",
        "save_fail": "Sorry, I could not save the reminder.",
        "created": "Got it. Reminder noted: {content}",
        "created_due": "Got it. I'll remind you on {due}: {content}",
        "list_fail": "Sorry, I could not retrieve your reminders.",
        "list_empty": "You have no pending reminders.",
        "list_header": "Here are your pending reminders:",
        "agenda_fail": "Sorry, I could not load your agenda.",
        "agenda_empty": "Nothing scheduled in that period.",
        "agenda_header": "Here's what's on:",
        "lookup_fail": "Sorry, I could not search your reminders.",
        "lookup_empty": "I couldn't find a reminder matching '{keyword}'.",
        "lookup_header": "Here's what I found:",
        "no_date": "no date set",
        "due_now": "Reminder: {content}",
        "delete_need_which": "Which reminder should I delete?",
        "delete_fail": "Sorry, I could not delete that reminder.",
        "deleted": "Removed the reminder: {content}",
        "deleted_many": "Removed {n} reminders: {content}",
        "delete_empty": "I couldn't find a pending reminder matching '{keyword}'.",
        "delete_cleared_memory": (
            "I didn't have a pending reminder matching '{keyword}', "
            "but I forgot the leftover note about it."
        ),
    },
    "de": {
        "need_content": "Ich brauche etwas mehr Inhalt für die Erinnerung.",
        "save_fail": "Sorry, ich konnte die Erinnerung nicht speichern.",
        "created": "Alles klar. Erinnerung notiert: {content}",
        "created_due": "Alles klar. Ich erinnere dich am {due}: {content}",
        "list_fail": "Sorry, ich konnte deine Erinnerungen nicht laden.",
        "list_empty": "Du hast keine offenen Erinnerungen.",
        "list_header": "Hier sind deine offenen Erinnerungen:",
        "agenda_fail": "Sorry, ich konnte deinen Kalender nicht laden.",
        "agenda_empty": "In dem Zeitraum steht nichts an.",
        "agenda_header": "Das steht an:",
        "lookup_fail": "Sorry, ich konnte nicht in deinen Erinnerungen suchen.",
        "lookup_empty": "Ich habe keine Erinnerung zu '{keyword}' gefunden.",
        "lookup_header": "Das habe ich gefunden:",
        "no_date": "kein Datum",
        "due_now": "Erinnerung: {content}",
        "delete_need_which": "Welche Erinnerung soll ich löschen?",
        "delete_fail": "Sorry, ich konnte die Erinnerung nicht löschen.",
        "deleted": "Erinnerung gelöscht: {content}",
        "deleted_many": "{n} Erinnerungen gelöscht: {content}",
        "delete_empty": "Ich habe keine offene Erinnerung zu '{keyword}' gefunden.",
        "delete_cleared_memory": (
            "Ich hatte keine offene Erinnerung zu '{keyword}', "
            "aber ich habe die übrig gebliebene Notiz dazu vergessen."
        ),
    },
    "hu": {
        "need_content": "Kicsit több tartalom kell az emlékeztetőhöz.",
        "save_fail": "Sajnos nem tudtam menteni az emlékeztetőt.",
        "created": "Rendben. Emlékeztető feljegyezve: {content}",
        "created_due": "Rendben. Emlékeztetlek ekkor: {due}: {content}",
        "list_fail": "Sajnos nem tudtam lekérni az emlékeztetőket.",
        "list_empty": "Nincs függő emlékeztetőd.",
        "list_header": "Ezek a függő emlékeztetőid:",
        "agenda_fail": "Sajnos nem tudtam betölteni a naptárad.",
        "agenda_empty": "Ebben az időszakban nincs semmi.",
        "agenda_header": "Ez van a naptárban:",
        "lookup_fail": "Sajnos nem tudtam keresni az emlékeztetők között.",
        "lookup_empty": "Nem találtam emlékeztetőt erre: '{keyword}'.",
        "lookup_header": "Ezt találtam:",
        "no_date": "nincs dátum",
        "due_now": "Emlékeztető: {content}",
        "delete_need_which": "Melyik emlékeztetőt töröljem?",
        "delete_fail": "Sajnos nem tudtam törölni az emlékeztetőt.",
        "deleted": "Töröltem az emlékeztetőt: {content}",
        "deleted_many": "{n} emlékeztetőt töröltem: {content}",
        "delete_empty": "Nem találtam függő emlékeztetőt erre: '{keyword}'.",
        "delete_cleared_memory": (
            "Nem volt függő emlékeztető erre: '{keyword}', "
            "de a maradék feljegyzést elfelejtettem."
        ),
    },
}


def _t(lang: str, key: str, **kwargs: str) -> str:
    """Look up a reply template in the detected language (fallback English)."""
    table = _REPLIES.get(lang) or _REPLIES["en"]
    template = table.get(key) or _REPLIES["en"][key]
    return template.format(**kwargs) if kwargs else template


def fire_speech(content: str, language: str | None) -> str:
    """Spoken line when a reminder becomes due."""
    return _t(language or "en", "due_now", content=content)


class RemindersSkill(Skill):
    """Create, list, agenda, look up, and cancel structured reminders.

    On create, also writes a short summary fact into Semantic Memory.
    Cancel drops that summary so Active Recall does not keep a ghost reminder.
    Replies use the same language as the user so TTS is not English-on-German.
    """

    name = "reminders"

    def __init__(
        self,
        repository: ReminderRepository,
        semantic_memory: SemanticMemory | None = None,
        llm: LLMAdapter | None = None,
        timezone: str | None = None,
    ) -> None:
        self.repository = repository
        self.semantic_memory = semantic_memory
        self.llm = llm
        self.timezone = timezone

    def can_handle(self, user_text: str, context: dict[str, Any] | None = None) -> bool:
        text = user_text.strip()
        if not text:
            return False
        return bool(
            _CREATE_PATTERNS.search(text)
            or _LIST_PATTERNS.search(text)
            or _AGENDA_PATTERNS.search(text)
            or _LOOKUP_PATTERNS.search(text)
            or _DELETE_PATTERNS.search(text)
        )

    async def execute(
        self,
        user_text: str,
        user_id: str,
        **deps: Any,
    ) -> SkillResult:
        text = user_text.strip()
        lang = reply_language(text, deps)
        is_create = bool(_CREATE_PATTERNS.search(text))

        # Question intents before create when both could match (a lookup
        # that contains the noun "reminder" must not become a new reminder).
        # Create still wins over agenda for "remind me today to call mom".
        if _LOOKUP_PATTERNS.search(text):
            return await self._lookup(text, lang)

        if _LIST_PATTERNS.search(text):
            return await self._list_reminders(text, lang)

        if _DELETE_PATTERNS.search(text):
            return await self._delete_reminder(text, lang)

        if _AGENDA_PATTERNS.search(text) and not is_create:
            return await self._run_agenda(text, lang)

        if is_create:
            return await self._create_reminder(text, lang)

        # Phrase-matched leftover: list, never invent a create from a question.
        return await self._list_reminders(text, lang)

    async def _run_agenda(self, text: str, lang: str) -> SkillResult:
        """Agenda for the matched window, defaulting to local today."""
        agenda = _agenda_range(text, self.timezone)
        if agenda is None:
            tz = zoneinfo_or_utc(self.timezone)
            today_start = (
                _now_utc()
                .astimezone(tz)
                .replace(hour=0, minute=0, second=0, microsecond=0)
            )
            agenda = (
                to_utc(today_start),
                to_utc(today_start + timedelta(days=1) - timedelta(microseconds=1)),
            )
        return await self._agenda(text, agenda[0], agenda[1], lang)

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def _merge_llm_create_slots(
        self,
        user_text: str,
        content: str,
        due_at: datetime | None,
    ) -> tuple[str, datetime | None]:
        """Optionally enrich content/due from the LLM slot extractor."""
        if self.llm is None:
            return content, due_at
        llm_content, llm_due = await extract_reminder_slots(
            self.llm, user_text, _now_utc(), timezone=self.timezone
        )
        if llm_content:
            content = llm_content
        if llm_due is not None:
            due_at = llm_due
        return content, due_at

    def _reminder_fact_summary(self, content: str, due_at: datetime | None) -> str:
        """Build the Semantic Memory one-liner for a new reminder."""
        summary = f"{REMINDER_FACT_PREFIX} {content[:200]}"
        if due_at is not None:
            summary += f" (due {_format_due(due_at, self.timezone)})"
        return summary

    async def _maybe_store_reminder_fact(self, summary: str) -> None:
        """Best-effort SM write for a reminder summary. Never raises."""
        if self.semantic_memory is None:
            return
        try:
            await self.semantic_memory.add_fact(
                fact=summary,
                importance=0.6,
                entities=["reminder"],
            )
        except Exception:
            logger.exception("Failed to write reminder summary to semantic memory")

    def _created_confirm_text(
        self, lang: str, content: str, due_at: datetime | None
    ) -> str:
        """Confirm create; due-claim phrasing only when ``due_at`` is set."""
        content_snip = content[:120]
        if due_at is not None:
            return _t(
                lang,
                "created_due",
                due=_format_due(due_at, self.timezone),
                content=content_snip,
            )
        return _t(lang, "created", content=content_snip)

    async def _create_reminder(self, user_text: str, lang: str) -> SkillResult:
        due_at = _parse_due(user_text, self.timezone)
        content = _strip_date_tokens(user_text) or user_text.strip()
        content, due_at = await self._merge_llm_create_slots(user_text, content, due_at)

        if len(content) < 2:
            return SkillResult(
                response_text=_t(lang, "need_content"),
                handled=True,
            )

        try:
            reminder = await self.repository.create(
                content=content, due_at=due_at, language=lang
            )
        except Exception:
            logger.exception("Failed to create reminder")
            return SkillResult(
                response_text=_t(lang, "save_fail"),
                handled=True,
            )

        summary = self._reminder_fact_summary(reminder.content, due_at)
        await self._maybe_store_reminder_fact(summary)
        return SkillResult(
            response_text=self._created_confirm_text(lang, reminder.content, due_at),
            handled=True,
            memory_writes=[{"content": summary, "importance": 0.6}],
        )

    # ------------------------------------------------------------------
    # Delete / cancel
    # ------------------------------------------------------------------

    async def _delete_reminder(self, user_text: str, lang: str) -> SkillResult:
        keyword = _delete_keyword(user_text)
        if len(keyword) < 2:
            return SkillResult(
                response_text=_t(lang, "delete_need_which"),
                handled=True,
            )

        matches = await self._search_delete_targets(keyword)
        if matches is None:
            return SkillResult(
                response_text=_t(lang, "delete_fail"),
                handled=True,
            )

        cancelled = await self._cancel_matches(matches)
        if cancelled is None:
            return SkillResult(
                response_text=_t(lang, "delete_fail"),
                handled=True,
            )
        if cancelled:
            names = ", ".join(item.content[:80] for item in cancelled)
            key = "deleted" if len(cancelled) == 1 else "deleted_many"
            return SkillResult(
                response_text=_t(lang, key, n=str(len(cancelled)), content=names),
                handled=True,
            )

        sm_n = await self._drop_reminder_summary(keyword)
        if not sm_n:
            sm_n = await self._drop_fuzzy_summary(keyword)
        if sm_n:
            return SkillResult(
                response_text=_t(lang, "delete_cleared_memory", keyword=keyword),
                handled=True,
            )
        return SkillResult(
            response_text=_t(lang, "delete_empty", keyword=keyword),
            handled=True,
        )

    async def _search_delete_targets(self, keyword: str) -> list[Reminder] | None:
        """Exact content search, then unique fuzzy match among pending."""
        try:
            matches = await self.repository.search_by_content(keyword, limit=10)
            if matches:
                return matches
            pending = await self.repository.list_reminders(limit=20)
            picked = _best_fuzzy_match(
                keyword, [(item.content, item) for item in pending]
            )
            return [picked] if picked is not None else []
        except Exception:
            logger.exception("Failed to search reminders for delete")
            return None

    async def _cancel_matches(self, matches: list[Reminder]) -> list[Reminder] | None:
        """Cancel each pending match and drop its SM summary. None on error."""
        cancelled: list[Reminder] = []
        for reminder in matches:
            try:
                updated = await self.repository.cancel(reminder.id)
            except Exception:
                logger.exception("Failed to cancel reminder %s", reminder.id)
                return None
            if updated is None:
                continue
            cancelled.append(updated)
            await self._drop_reminder_summary(updated.content)
        return cancelled

    async def _drop_reminder_summary(self, query: str) -> int:
        """Remove Semantic Memory copies of a reminder summary. 0 if none."""
        if self.semantic_memory is None or not query:
            return 0
        try:
            return await self.semantic_memory.delete_facts_containing(
                query, prefix=REMINDER_FACT_PREFIX
            )
        except Exception:
            logger.exception("Failed to drop reminder summary from memory")
            return 0

    async def _drop_fuzzy_summary(self, keyword: str) -> int:
        """Drop the unique reminder summary that fuzzy-matches a mistyped target."""
        if self.semantic_memory is None:
            return 0
        try:
            facts = await self.semantic_memory.list_facts_with_prefix(
                REMINDER_FACT_PREFIX
            )
        except Exception:
            logger.exception("Failed to list reminder summaries for fuzzy delete")
            return 0
        labelled: list[tuple[str, Any]] = []
        for fact in facts:
            remainder = fact.content
            if remainder.startswith(REMINDER_FACT_PREFIX):
                remainder = remainder[len(REMINDER_FACT_PREFIX) :].strip()
            labelled.append((remainder, fact))
        picked = _best_fuzzy_match(keyword, labelled)
        if picked is None:
            return 0
        try:
            return await self.semantic_memory.delete_facts_by_ids([picked.id])
        except Exception:
            logger.exception("Failed to drop fuzzy reminder summary")
            return 0

    # ------------------------------------------------------------------
    # List (all pending)
    # ------------------------------------------------------------------

    async def _list_reminders(self, user_text: str, lang: str) -> SkillResult:
        try:
            reminders = await self.repository.list_reminders(limit=15)
        except Exception:
            logger.exception("Failed to list reminders")
            return SkillResult(
                response_text=_t(lang, "list_fail"),
                handled=True,
            )

        if not reminders:
            return SkillResult(
                response_text=_t(lang, "list_empty"),
                handled=True,
            )

        return SkillResult(
            response_text=self._format_list(reminders, header=_t(lang, "list_header")),
            handled=True,
        )

    # ------------------------------------------------------------------
    # Agenda (time range)
    # ------------------------------------------------------------------

    async def _agenda(
        self,
        user_text: str,
        due_from: datetime,
        due_to: datetime,
        lang: str,
    ) -> SkillResult:
        try:
            reminders = await self.repository.list_reminders(
                limit=30, due_from=due_from, due_to=due_to
            )
        except Exception:
            logger.exception("Failed to load agenda")
            return SkillResult(
                response_text=_t(lang, "agenda_fail"),
                handled=True,
            )

        if not reminders:
            return SkillResult(
                response_text=_t(lang, "agenda_empty"),
                handled=True,
            )

        # Group by local calendar day
        groups: dict[str, list[Reminder]] = {}
        for r in reminders:
            key = self._wall(r.due_at).strftime("%Y-%m-%d") if r.due_at else "no date"
            groups.setdefault(key, []).append(r)

        lines: list[str] = []
        for day in sorted(groups.keys()):
            lines.append(f"{day}:")
            for r in groups[day]:
                time_str = ""
                if r.due_at:
                    local = self._wall(r.due_at)
                    if local.hour or local.minute:
                        time_str = local.strftime("%H:%M") + " "
                preview = r.content[:70] + ("…" if len(r.content) > 70 else "")
                lines.append(f"  - {time_str}{preview}")

        body = "\n".join(lines)
        return SkillResult(
            response_text=f"{_t(lang, 'agenda_header')}\n{body}",
            handled=True,
        )

    # ------------------------------------------------------------------
    # Lookup (specific event)
    # ------------------------------------------------------------------

    async def _lookup(self, user_text: str, lang: str) -> SkillResult:
        keyword = _lookup_keyword(user_text)
        try:
            reminders = await self.repository.search_by_content(keyword, limit=5)
        except Exception:
            logger.exception("Failed to search reminders")
            return SkillResult(
                response_text=_t(lang, "lookup_fail"),
                handled=True,
            )

        if not reminders:
            return SkillResult(
                response_text=_t(lang, "lookup_empty", keyword=keyword),
                handled=True,
            )

        lines = []
        for r in reminders:
            due_str = _format_due(r.due_at, self.timezone)
            if due_str:
                lines.append(f"• {r.content[:80]} — {due_str}")
            else:
                lines.append(f"• {r.content[:80]} ({_t(lang, 'no_date')})")

        return SkillResult(
            response_text=_t(lang, "lookup_header") + "\n" + "\n".join(lines),
            handled=True,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _format_list(self, reminders: list[Reminder], header: str) -> str:
        lines = []
        for i, r in enumerate(reminders, 1):
            due_str = _format_due(r.due_at, self.timezone)
            prefix = f"{due_str} – " if due_str else ""
            preview = r.content[:80] + ("…" if len(r.content) > 80 else "")
            lines.append(f"{i}. {prefix}{preview}")
        return f"{header}\n" + "\n".join(lines)

    def _wall(self, due: datetime) -> datetime:
        """``due`` instant as a wall-clock datetime in the user's timezone."""
        return due.astimezone(zoneinfo_or_utc(self.timezone))
