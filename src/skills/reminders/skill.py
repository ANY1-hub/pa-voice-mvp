"""RemindersSkill – create, list, agenda and lookup with optional due_at."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from src.core.language import detect_response_language
from src.memory.semantic_memory import SemanticMemory
from src.models.reminder import Reminder
from src.services.llm.base import LLMAdapter
from src.skills.base import Skill, SkillResult
from src.skills.reminders.repository import ReminderRepository
from src.skills.reminders.slots import extract_reminder_slots
from src.skills.vocabulary import (
    REMINDERS_AGENDA,
    REMINDERS_AGENDA_EXTRA,
    REMINDERS_CREATE,
    REMINDERS_CREATE_EXTRA,
    REMINDERS_LIST,
    REMINDERS_LIST_EXTRA,
    REMINDERS_LOOKUP,
    REMINDERS_LOOKUP_EXTRA,
    compile_phrase_regex,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Intent patterns
# ---------------------------------------------------------------------------

_CREATE_PATTERNS = compile_phrase_regex(REMINDERS_CREATE, extra=REMINDERS_CREATE_EXTRA)
_LIST_PATTERNS = compile_phrase_regex(REMINDERS_LIST, extra=REMINDERS_LIST_EXTRA)
_AGENDA_PATTERNS = compile_phrase_regex(REMINDERS_AGENDA, extra=REMINDERS_AGENDA_EXTRA)
_LOOKUP_PATTERNS = compile_phrase_regex(REMINDERS_LOOKUP, extra=REMINDERS_LOOKUP_EXTRA)

# Relative date tokens
_TOMORROW = re.compile(r"\b(tomorrow|morgen|holnap)\b", re.IGNORECASE)
_TODAY = re.compile(r"\b(today|heute|ma)\b", re.IGNORECASE)
_NUMERIC_DATE = re.compile(r"\b(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?\b")
_DAY_AFTER = re.compile(r"\b(übermorgen|day after tomorrow)\b", re.IGNORECASE)

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

# Relative wait: "in 2 minutes", "in 5 Minuten", "in einer Stunde", "2 perc múlva"
_RELATIVE_IN = re.compile(
    r"\bin\s+(?:einer|einem|one|a)\s+"
    r"(minutes?|mins?|minuten|minute|hours?|hrs?|stunden|stunde)\b",
    re.IGNORECASE,
)
_RELATIVE_N = re.compile(
    r"\bin\s+(\d+)\s*" r"(minutes?|mins?|minuten|minute|hours?|hrs?|stunden|stunde)\b",
    re.IGNORECASE,
)
_RELATIVE_HU = re.compile(
    r"\b(\d+)\s*(perc|óra)\s*múlva\b",
    re.IGNORECASE,
)


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
    """Parse 'in N minutes' / 'in einer Stunde' / 'N perc múlva'."""
    m = _RELATIVE_HU.search(text)
    if m:
        return now + _unit_to_delta(int(m.group(1)), m.group(2))
    m = _RELATIVE_N.search(text)
    if m:
        return now + _unit_to_delta(int(m.group(1)), m.group(2))
    m = _RELATIVE_IN.search(text)
    if m:
        return now + _unit_to_delta(1, m.group(1))
    return None


def _parse_due(text: str) -> datetime | None:  # noqa: C901
    """Parse a simple relative date (+ optional time) from free text.

    Supports: in N minutes/hours, today/heute, tomorrow/morgen, day-after,
    weekdays. Returns None when no date token is found.
    """
    now = _now_utc()
    relative = _parse_relative_duration(text, now)
    if relative is not None:
        return relative
    base: datetime | None = None

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
            year = now.year
        try:
            base = datetime(year, month, day, tzinfo=UTC)
        except ValueError:
            base = None

    if base is None and _DAY_AFTER.search(text):
        base = (now + timedelta(days=2)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    elif base is None and _TOMORROW.search(text):
        base = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    elif base is None and _TODAY.search(text):
        base = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif base is None:
        wd = _WEEKDAY_RE.search(text)
        if wd:
            target = _WEEKDAYS[wd.group(1).lower()]
            days_ahead = (target - now.weekday()) % 7
            t_preview = _parse_time(text)
            if days_ahead == 0 and t_preview:
                hour, minute = t_preview
                same_day = now.replace(
                    hour=hour, minute=minute, second=0, microsecond=0
                )
                days_ahead = 0 if same_day > now else 7
            elif days_ahead == 0:
                days_ahead = 7  # next occurrence, not today
            base = (now + timedelta(days=days_ahead)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

    t = _parse_time(text)
    if base is None:
        # Time of day without a date token → today, or tomorrow if already past.
        if t is None:
            return None
        hour, minute = t
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    if t:
        hour, minute = t
        base = base.replace(hour=hour, minute=minute)
    return base


def _strip_date_tokens(text: str) -> str:
    """Remove date/time tokens so the remaining text is clean content."""
    cleaned = _CREATE_PATTERNS.sub("", text)
    cleaned = _TOMORROW.sub("", cleaned)
    cleaned = _TODAY.sub("", cleaned)
    cleaned = _DAY_AFTER.sub("", cleaned)
    cleaned = _WEEKDAY_RE.sub("", cleaned)
    cleaned = _TIME_RE.sub("", cleaned)
    cleaned = _NUMERIC_DATE.sub("", cleaned)
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


def _format_due(due: datetime | None) -> str:
    """Human-readable due string (date + time if not midnight)."""
    if due is None:
        return ""
    date_part = due.strftime("%Y-%m-%d")
    if due.hour or due.minute:
        return f"{date_part} {due.strftime('%H:%M')}"
    return date_part


def _agenda_range(text: str) -> tuple[datetime, datetime] | None:
    """Return (due_from, due_to) for known agenda phrases, else None."""
    now = _now_utc()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    lower = text.lower()

    # Next-week before this-week: "jövő héten" also contains "héten".
    if re.search(r"\b(nächste woche|next week|jövő héten|jövő hét)\b", lower):
        start = today_start - timedelta(days=today_start.weekday()) + timedelta(days=7)
        end = start + timedelta(days=7) - timedelta(microseconds=1)
        return start, end

    if re.search(r"\b(diese woche|this week|a héten|ezen a héten)\b", lower):
        start = today_start - timedelta(days=today_start.weekday())
        end = start + timedelta(days=7) - timedelta(microseconds=1)
        return start, end

    if re.search(r"\b(diesen monat|dieser monat|this month|ebben a hónapban)\b", lower):
        start = today_start.replace(day=1)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        end = end - timedelta(microseconds=1)
        return start, end

    if re.search(r"\b(heute|today|ma)\b", lower):
        return today_start, today_start + timedelta(days=1) - timedelta(microseconds=1)

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


_REPLIES: dict[str, dict[str, str]] = {
    "en": {
        "need_content": "I need a bit more content for the reminder.",
        "save_fail": "Sorry, I could not save the reminder.",
        "created": "Got it. I'll remind you{due}: {content}",
        "created_due": " on {due}",
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
    },
    "de": {
        "need_content": "Ich brauche etwas mehr Inhalt für die Erinnerung.",
        "save_fail": "Sorry, ich konnte die Erinnerung nicht speichern.",
        "created": "Alles klar. Ich erinnere dich{due}: {content}",
        "created_due": " am {due}",
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
    },
    "hu": {
        "need_content": "Kicsit több tartalom kell az emlékeztetőhöz.",
        "save_fail": "Sajnos nem tudtam menteni az emlékeztetőt.",
        "created": "Rendben. Emlékeztetlek{due}: {content}",
        "created_due": " ekkor: {due}",
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
    """Create, list, agenda-query and look up structured reminders.

    On create, also writes a short summary fact into Semantic Memory.
    Replies use the same language as the user so TTS is not English-on-German.
    """

    name = "reminders"

    def __init__(
        self,
        repository: ReminderRepository,
        semantic_memory: SemanticMemory | None = None,
        llm: LLMAdapter | None = None,
    ) -> None:
        self.repository = repository
        self.semantic_memory = semantic_memory
        self.llm = llm

    def can_handle(self, user_text: str, context: dict[str, Any] | None = None) -> bool:
        text = user_text.strip()
        if not text:
            return False
        return bool(
            _CREATE_PATTERNS.search(text)
            or _LIST_PATTERNS.search(text)
            or _AGENDA_PATTERNS.search(text)
            or _LOOKUP_PATTERNS.search(text)
        )

    async def execute(
        self,
        user_text: str,
        user_id: str,
        **deps: Any,
    ) -> SkillResult:
        text = user_text.strip()
        lang = detect_response_language(text)

        # Create wins over agenda: "remind me today to call mom" must not
        # be handled as "what's on today".
        if _CREATE_PATTERNS.search(text):
            return await self._create_reminder(text, lang)

        if _LOOKUP_PATTERNS.search(text):
            return await self._lookup(text, lang)

        if _LIST_PATTERNS.search(text):
            return await self._list_reminders(text, lang)

        if _AGENDA_PATTERNS.search(text):
            agenda = _agenda_range(text)
            if agenda is None:
                now = _now_utc()
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                agenda = (
                    today_start,
                    today_start + timedelta(days=1) - timedelta(microseconds=1),
                )
            return await self._agenda(text, agenda[0], agenda[1], lang)

        return await self._create_reminder(text, lang)

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def _create_reminder(self, user_text: str, lang: str) -> SkillResult:
        due_at = _parse_due(user_text)
        content = _strip_date_tokens(user_text)
        if not content:
            content = user_text.strip()

        if self.llm is not None:
            llm_content, llm_due = await extract_reminder_slots(
                self.llm, user_text, _now_utc()
            )
            if llm_content:
                content = llm_content
            if llm_due is not None:
                due_at = llm_due

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

        summary = f"User set a reminder: {reminder.content[:200]}"
        if due_at:
            summary += f" (due {_format_due(due_at)})"

        if self.semantic_memory is not None:
            try:
                await self.semantic_memory.add_fact(
                    fact=summary,
                    importance=0.6,
                    entities=["reminder"],
                )
            except Exception:
                logger.exception("Failed to write reminder summary to semantic memory")

        due_part = _t(lang, "created_due", due=_format_due(due_at)) if due_at else ""
        return SkillResult(
            response_text=_t(
                lang,
                "created",
                due=due_part,
                content=reminder.content[:120],
            ),
            handled=True,
            memory_writes=[{"content": summary, "importance": 0.6}],
        )

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

        # Group by day
        groups: dict[str, list[Reminder]] = {}
        for r in reminders:
            key = r.due_at.strftime("%Y-%m-%d") if r.due_at else "no date"
            groups.setdefault(key, []).append(r)

        lines: list[str] = []
        for day in sorted(groups.keys()):
            lines.append(f"{day}:")
            for r in groups[day]:
                time_str = ""
                if r.due_at and (r.due_at.hour or r.due_at.minute):
                    time_str = r.due_at.strftime("%H:%M") + " "
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
            due_str = _format_due(r.due_at)
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
            due_str = _format_due(r.due_at)
            prefix = f"{due_str} – " if due_str else ""
            preview = r.content[:80] + ("…" if len(r.content) > 80 else "")
            lines.append(f"{i}. {prefix}{preview}")
        return f"{header}\n" + "\n".join(lines)
