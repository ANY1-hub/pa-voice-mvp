"""Optional LLM slot filling for reminder create (regex remains the fallback)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from src.core.timezones import zoneinfo_or_utc
from src.services.llm.base import LLMAdapter, llm_text

logger = logging.getLogger(__name__)


def _slot_system(timezone: str) -> str:
    """System prompt: clock times are local to ``timezone``, due_iso is UTC."""
    return f"""You extract reminder slots from a user utterance.
Return JSON only with keys:
- content: the thing to be reminded of (no date/time words, no trigger phrases)
- due_iso: UTC ISO-8601 datetime string, or null if no date/time is present
The user's IANA timezone is {timezone}. Named clock times (13:30, um 14 Uhr)
are wall-clock times in that timezone; convert them to UTC for due_iso.
Use now_utc / now_local as the reference for relative dates (today, tomorrow, weekdays).
If the user names a calendar date such as 18.8. or 18/8/2026, interpret it in
the user's timezone, then emit UTC ISO.
Do not invent a reminder from a question (for example "do I have a reminder?").
"""


async def extract_reminder_slots(
    llm: LLMAdapter,
    user_text: str,
    now_utc: datetime,
    timezone: str | None = None,
) -> tuple[str | None, datetime | None]:
    """Ask the LLM for (content, due_at). Returns (None, None) on failure."""
    tz_name = timezone or "UTC"
    now_local = now_utc.astimezone(zoneinfo_or_utc(timezone))
    messages = [
        {"role": "system", "content": _slot_system(tz_name)},
        {
            "role": "user",
            "content": (
                f"now_utc={now_utc.isoformat()}\n"
                f"now_local={now_local.isoformat()}\n"
                f"timezone={tz_name}\n"
                f"utterance={user_text}"
            ),
        },
    ]
    try:
        raw = await llm.generate_response(
            messages,
            temperature=0,
            response_format={"type": "json_object"},
        )
        data = json.loads(llm_text(raw) or "{}")
    except Exception:
        logger.exception("Reminder slot extraction failed – using regex fallback")
        return None, None

    content = data.get("content")
    if not isinstance(content, str) or len(content.strip()) < 2:
        content = None
    else:
        content = content.strip()

    due: datetime | None = None
    due_iso = data.get("due_iso")
    if isinstance(due_iso, str) and due_iso.strip():
        try:
            parsed = datetime.fromisoformat(due_iso.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            due = parsed.astimezone(UTC)
        except ValueError:
            due = None

    return content, due
