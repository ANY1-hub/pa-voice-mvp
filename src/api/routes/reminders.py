"""Due reminder delivery: list fired reminders and acknowledge them."""

from __future__ import annotations

import base64
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from src.api.deps import get_reminder_repository, get_tts_adapter
from src.services.tts.base import TTSAdapter
from src.skills.reminders import skill as reminders_skill
from src.skills.reminders.repository import ReminderRepository
from src.skills.reminders.skill import fire_speech

router = APIRouter()


class DueReminderOut(BaseModel):
    """One fired reminder ready to show and speak."""

    id: str
    content: str
    text: str
    audio_base64: str | None = None
    due_at: datetime | None = None
    language: str | None = None


class DueRemindersResponse(BaseModel):
    """Payload for GET /reminders/due."""

    reminders: list[DueReminderOut]


class ReminderOut(BaseModel):
    """One reminder for the sidebar list."""

    id: str
    content: str
    status: str
    due_at: datetime | None = None
    created_at: datetime


class RemindersListResponse(BaseModel):
    """Payload for GET /reminders (all statuses)."""

    reminders: list[ReminderOut]


@router.get("", response_model=RemindersListResponse)
async def list_reminders(
    repo: Annotated[ReminderRepository, Depends(get_reminder_repository)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> RemindersListResponse:
    """Return the current user's reminders of any status.

    JWT is enforced via the reminder-repository dependency (ready user).
    """
    reminders = await repo.list_reminders(limit=limit, status=None)
    return RemindersListResponse(
        reminders=[
            ReminderOut(
                id=item.id,
                content=item.content,
                status=item.status,
                due_at=item.due_at,
                created_at=item.created_at,
            )
            for item in reminders
        ]
    )


@router.get("/due", response_model=DueRemindersResponse)
async def list_due_reminders(
    repo: Annotated[ReminderRepository, Depends(get_reminder_repository)],
    tts: Annotated[TTSAdapter | None, Depends(get_tts_adapter)],
) -> DueRemindersResponse:
    """Claim due reminders for the current user and return them with TTS."""
    now = reminders_skill._now_utc()
    await repo.claim_due_for_user(now)
    fired = await repo.list_fired_unacked()
    items: list[DueReminderOut] = []
    for reminder in fired:
        text = fire_speech(reminder.content, reminder.language)
        audio_b64 = None
        if tts is not None:
            try:
                raw = await tts.synthesize(text, language=reminder.language)
                if raw:
                    audio_b64 = base64.b64encode(raw).decode("ascii")
            except Exception:
                audio_b64 = None
        items.append(
            DueReminderOut(
                id=reminder.id,
                content=reminder.content,
                text=text,
                audio_base64=audio_b64,
                due_at=reminder.due_at,
                language=reminder.language,
            )
        )
    return DueRemindersResponse(reminders=items)


@router.post("/{reminder_id}/ack")
async def acknowledge_reminder(
    reminder_id: str,
    repo: Annotated[ReminderRepository, Depends(get_reminder_repository)],
) -> dict:
    """Mark a due reminder as done so it is not spoken again."""
    updated = await repo.acknowledge(reminder_id)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reminder not found",
        )
    return {"status": "ok", "id": updated.id}
