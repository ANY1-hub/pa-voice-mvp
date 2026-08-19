"""Optional LLM slot filling for reminder create (regex remains the fallback)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from src.services.llm.base import LLMAdapter

logger = logging.getLogger(__name__)

_SLOT_SYSTEM = """You extract reminder slots from a user utterance.
Return JSON only with keys:
- content: the thing to be reminded of (no date/time words, no trigger phrases)
- due_iso: UTC ISO-8601 datetime string, or null if no date/time is present
Use the provided "now_utc" as the reference for relative dates (today, tomorrow, weekdays).
If the user names a calendar date such as 18.8. or 18/8/2026, convert it to UTC ISO.
"""


async def extract_reminder_slots(
    llm: LLMAdapter,
    user_text: str,
    now_utc: datetime,
) -> tuple[str | None, datetime | None]:
    """Ask the LLM for (content, due_at). Returns (None, None) on failure."""
    messages = [
        {"role": "system", "content": _SLOT_SYSTEM},
        {
            "role": "user",
            "content": f"now_utc={now_utc.isoformat()}\nutterance={user_text}",
        },
    ]
    try:
        raw = await llm.generate_response(
            messages,
            temperature=0,
            response_format={"type": "json_object"},
        )
        data = json.loads(raw or "{}")
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
