"""RemindersSkill – create, list, agenda and lookup with optional due_at."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from src.memory.semantic_memory import SemanticMemory
from src.models.reminder import Reminder
from src.skills.base import Skill, SkillResult
from src.skills.reminders.repository import ReminderRepository

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Intent patterns
# ---------------------------------------------------------------------------

_CREATE_PATTERNS = re.compile(
    r"\b(remind me|reminder|erinner(?:e)? mich|erinnerung|emlékeztess|"
    r"set a reminder|stell eine erinnerung|merk dir das)\b",
    re.IGNORECASE,
)
_LIST_PATTERNS = re.compile(
    r"\b(list reminders|show reminders|meine erinnerungen|"
    r"erinnerungen zeigen|what reminders|zeig mir die erinnerungen|"
    r"listázd az emlékeztetőket)\b",
    re.IGNORECASE,
)
# Agenda must be an explicit schedule question, not a bare date word.
# Bare "today" / "this week" used to steal creates and ordinary chat.
_AGENDA_PATTERNS = re.compile(
    r"\b("
    r"was steht|"
    r"what'?s on|what is on|"
    r"agenda|"
    r"what(?:'s| is) (?:on )?(?:today|this week|next week|this month)"
    r")\b",
    re.IGNORECASE,
)
_LOOKUP_PATTERNS = re.compile(
    r"\b(wann habe ich|when is|wann muss ich|when do i|when was|"
    r"wann ist|when did|wann war|when should|wann soll|"
    r"when do i have)\b",
    re.IGNORECASE,
)

# Relative date tokens
_TOMORROW = re.compile(r"\b(tomorrow|morgen)\b", re.IGNORECASE)
_TODAY = re.compile(r"\b(today|heute)\b", re.IGNORECASE)
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


def _parse_due(text: str) -> datetime | None:  # noqa: C901
    """Parse a simple relative date (+ optional time) from free text.

    Supports: today/heute, tomorrow/morgen, day-after, weekdays.
    Returns None when no date token is found.
    """
    now = _now_utc()
    base: datetime | None = None

    if _DAY_AFTER.search(text):
        base = (now + timedelta(days=2)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    elif _TOMORROW.search(text):
        base = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    elif _TODAY.search(text):
        base = now.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
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
    # common filler words after stripping
    cleaned = re.sub(
        r"\b(an den|an die|an das|an|to|um|at|on)\b", "", cleaned, flags=re.I
    )
    return cleaned.strip(" :,-.").strip()


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

    if re.search(r"\b(heute|today)\b", lower):
        return today_start, today_start + timedelta(days=1) - timedelta(microseconds=1)

    if re.search(r"\b(diese woche|this week)\b", lower):
        # Monday of current week → Sunday end
        start = today_start - timedelta(days=today_start.weekday())
        end = start + timedelta(days=7) - timedelta(microseconds=1)
        return start, end

    if re.search(r"\b(nächste woche|next week)\b", lower):
        start = today_start - timedelta(days=today_start.weekday()) + timedelta(days=7)
        end = start + timedelta(days=7) - timedelta(microseconds=1)
        return start, end

    if re.search(r"\b(diesen monat|dieser monat|this month)\b", lower):
        start = today_start.replace(day=1)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        end = end - timedelta(microseconds=1)
        return start, end

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


class RemindersSkill(Skill):
    """Create, list, agenda-query and look up structured reminders.

    On create, also writes a short summary fact into Semantic Memory.
    """

    name = "reminders"

    def __init__(
        self,
        repository: ReminderRepository,
        semantic_memory: SemanticMemory | None = None,
    ) -> None:
        self.repository = repository
        self.semantic_memory = semantic_memory

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

        # Create wins over agenda: "remind me today to call mom" must not
        # be handled as "what's on today".
        if _CREATE_PATTERNS.search(text):
            return await self._create_reminder(text)

        if _LOOKUP_PATTERNS.search(text):
            return await self._lookup(text)

        if _LIST_PATTERNS.search(text):
            return await self._list_reminders(text)

        if _AGENDA_PATTERNS.search(text):
            agenda = _agenda_range(text)
            if agenda is None:
                now = _now_utc()
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                agenda = (
                    today_start,
                    today_start + timedelta(days=1) - timedelta(microseconds=1),
                )
            return await self._agenda(text, agenda[0], agenda[1])

        return await self._create_reminder(text)

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def _create_reminder(self, user_text: str) -> SkillResult:
        due_at = _parse_due(user_text)
        content = _strip_date_tokens(user_text)
        if not content:
            content = user_text.strip()

        if len(content) < 2:
            return SkillResult(
                response_text="I need a bit more content for the reminder.",
                handled=True,
            )

        try:
            reminder = await self.repository.create(content=content, due_at=due_at)
        except Exception:
            logger.exception("Failed to create reminder")
            return SkillResult(
                response_text="Sorry, I could not save the reminder.",
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

        due_str = f" on {_format_due(due_at)}" if due_at else ""
        return SkillResult(
            response_text=f"Got it. I'll remind you{due_str}: {reminder.content[:120]}",
            handled=True,
            memory_writes=[{"content": summary, "importance": 0.6}],
        )

    # ------------------------------------------------------------------
    # List (all pending)
    # ------------------------------------------------------------------

    async def _list_reminders(self, user_text: str) -> SkillResult:
        try:
            reminders = await self.repository.list_reminders(limit=15)
        except Exception:
            logger.exception("Failed to list reminders")
            return SkillResult(
                response_text="Sorry, I could not retrieve your reminders.",
                handled=True,
            )

        if not reminders:
            return SkillResult(
                response_text="You have no pending reminders.",
                handled=True,
            )

        return SkillResult(
            response_text=self._format_list(
                reminders, header="Here are your pending reminders:"
            ),
            handled=True,
        )

    # ------------------------------------------------------------------
    # Agenda (time range)
    # ------------------------------------------------------------------

    async def _agenda(
        self, user_text: str, due_from: datetime, due_to: datetime
    ) -> SkillResult:
        try:
            reminders = await self.repository.list_reminders(
                limit=30, due_from=due_from, due_to=due_to
            )
        except Exception:
            logger.exception("Failed to load agenda")
            return SkillResult(
                response_text="Sorry, I could not load your agenda.",
                handled=True,
            )

        if not reminders:
            return SkillResult(
                response_text="Nothing scheduled in that period.",
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
            response_text=f"Here's what's on:\n{body}",
            handled=True,
        )

    # ------------------------------------------------------------------
    # Lookup (specific event)
    # ------------------------------------------------------------------

    async def _lookup(self, user_text: str) -> SkillResult:
        keyword = _lookup_keyword(user_text)
        try:
            reminders = await self.repository.search_by_content(keyword, limit=5)
        except Exception:
            logger.exception("Failed to search reminders")
            return SkillResult(
                response_text="Sorry, I could not search your reminders.",
                handled=True,
            )

        if not reminders:
            return SkillResult(
                response_text=f"I couldn't find a reminder matching '{keyword}'.",
                handled=True,
            )

        lines = []
        for r in reminders:
            due_str = _format_due(r.due_at)
            if due_str:
                lines.append(f"• {r.content[:80]} — {due_str}")
            else:
                lines.append(f"• {r.content[:80]} (no date set)")

        return SkillResult(
            response_text="Here's what I found:\n" + "\n".join(lines),
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
