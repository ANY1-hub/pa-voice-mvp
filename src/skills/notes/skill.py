"""NotesSkill – create and list structured notes with Semantic Memory summary."""

from __future__ import annotations

import logging
import re
from typing import Any

from src.memory.semantic_memory import SemanticMemory
from src.skills.base import Skill, SkillResult
from src.skills.notes.repository import NoteRepository

logger = logging.getLogger(__name__)

# Simple intent patterns (English + German + Hungarian keywords for MVP)
_CREATE_PATTERNS = re.compile(
    r"\b(note|notiz|jegyzet|remember this|merk dir|jegyzeteld|save note|"
    r"schreib auf|notiere)\b",
    re.IGNORECASE,
)
_LIST_PATTERNS = re.compile(
    r"\b(list notes|show notes|meine notizen|notizen zeigen|"
    r"listázd a jegyzeteket|show my notes|what notes)\b",
    re.IGNORECASE,
)


class NotesSkill(Skill):
    """Create and retrieve structured notes.

    On create, also writes a short summary fact into Semantic Memory so the
    agent can recall the note naturally in later conversations.
    """

    name = "notes"

    def __init__(
        self,
        repository: NoteRepository,
        semantic_memory: SemanticMemory | None = None,
    ) -> None:
        """Wire the collaborators.

        Args:
            repository: User-scoped NoteRepository.
            semantic_memory: Optional SemanticMemory for the summary fact.
        """
        self.repository = repository
        self.semantic_memory = semantic_memory

    def can_handle(self, user_text: str, context: dict[str, Any] | None = None) -> bool:
        """Cheap keyword check for create or list intents."""
        text = user_text.strip()
        if not text:
            return False
        return bool(_CREATE_PATTERNS.search(text) or _LIST_PATTERNS.search(text))

    async def execute(
        self,
        user_text: str,
        user_id: str,
        **deps: Any,
    ) -> SkillResult:
        """Dispatch to create or list based on the utterance."""
        text = user_text.strip()

        if _LIST_PATTERNS.search(text):
            return await self._list_notes(text)

        # Default to create when create-pattern matched (or ambiguous)
        return await self._create_note(text)

    async def _create_note(self, user_text: str) -> SkillResult:
        """Extract content and persist a note + semantic summary."""
        # Very light extraction: strip the trigger phrase if present
        content = _CREATE_PATTERNS.sub("", user_text).strip(" :,-").strip()
        if not content:
            content = user_text.strip()

        if len(content) < 2:
            return SkillResult(
                response_text="I need a bit more content for the note.",
                handled=True,
            )

        try:
            note = await self.repository.create(content=content)
        except Exception:
            logger.exception("Failed to create note")
            return SkillResult(
                response_text="Sorry, I could not save the note.",
                handled=True,
            )

        # Write short summary into Semantic Memory (Option A)
        summary = f"User saved a note: {note.content[:200]}"
        if note.title:
            summary = f"User saved a note titled '{note.title}': {note.content[:150]}"

        if self.semantic_memory is not None:
            try:
                await self.semantic_memory.add_fact(
                    fact=summary,
                    importance=0.55,
                    entities=["note"],
                )
            except Exception:
                logger.exception("Failed to write note summary to semantic memory")

        return SkillResult(
            response_text=f"Got it. I saved the note: {note.content[:120]}",
            handled=True,
            memory_writes=[{"content": summary, "importance": 0.55}],
        )

    async def _list_notes(self, user_text: str) -> SkillResult:
        """Return a short summary of recent notes."""
        try:
            notes = await self.repository.list_notes(limit=10)
        except Exception:
            logger.exception("Failed to list notes")
            return SkillResult(
                response_text="Sorry, I could not retrieve your notes.",
                handled=True,
            )

        if not notes:
            return SkillResult(
                response_text="You have no notes yet.",
                handled=True,
            )

        lines = []
        for i, n in enumerate(notes, 1):
            preview = n.content[:80] + ("…" if len(n.content) > 80 else "")
            if n.title:
                lines.append(f"{i}. {n.title}: {preview}")
            else:
                lines.append(f"{i}. {preview}")

        body = "\n".join(lines)
        return SkillResult(
            response_text=f"Here are your recent notes:\n{body}",
            handled=True,
        )
