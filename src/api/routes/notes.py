"""HTTP list of the current user's notes."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from src.api.deps import get_note_repository
from src.skills.notes.repository import NoteRepository

router = APIRouter()


class NoteOut(BaseModel):
    """One note for the sidebar list."""

    id: str
    title: str | None = None
    content: str
    created_at: datetime
    tags: list[str] = Field(default_factory=list)


class NotesListResponse(BaseModel):
    """Payload for GET /notes."""

    notes: list[NoteOut]


@router.get("", response_model=NotesListResponse)
async def list_notes(
    repo: Annotated[NoteRepository, Depends(get_note_repository)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> NotesListResponse:
    """Return the current user's notes, newest first.

    JWT is enforced via the note-repository dependency (ready user).
    """
    notes = await repo.list_notes(limit=limit)
    return NotesListResponse(
        notes=[
            NoteOut(
                id=note.id,
                title=note.title,
                content=note.content,
                created_at=note.created_at,
                tags=note.tags,
            )
            for note in notes
        ]
    )
