"""NotesSkill – create and list structured notes with Semantic Memory summary."""

from __future__ import annotations

import logging
from typing import Any

from src.memory.semantic_memory import SemanticMemory
from src.skills.base import Skill, SkillResult
from src.skills.notes.repository import NoteRepository
from src.skills.replies import reply_language, t
from src.skills.vocabulary import (
    NOTES_CREATE,
    NOTES_CREATE_EXTRA,
    NOTES_LIST,
    NOTES_LIST_EXTRA,
    compile_phrase_regex,
)

logger = logging.getLogger(__name__)

_CREATE_PATTERNS = compile_phrase_regex(NOTES_CREATE, extra=NOTES_CREATE_EXTRA)
_LIST_PATTERNS = compile_phrase_regex(NOTES_LIST, extra=NOTES_LIST_EXTRA)

_REPLIES: dict[str, dict[str, str]] = {
    "en": {
        "need_content": "I need a bit more content for the note.",
        "save_fail": "Sorry, I could not save the note.",
        "created": "Got it. I saved the note: {content}",
        "list_fail": "Sorry, I could not retrieve your notes.",
        "list_empty": "You have no notes yet.",
        "list_header": "Here are your recent notes:\n{body}",
    },
    "de": {
        "need_content": "Ich brauche etwas mehr Inhalt für die Notiz.",
        "save_fail": "Sorry, ich konnte die Notiz nicht speichern.",
        "created": "Alles klar. Ich habe die Notiz gespeichert: {content}",
        "list_fail": "Sorry, ich konnte deine Notizen nicht laden.",
        "list_empty": "Du hast noch keine Notizen.",
        "list_header": "Hier sind deine letzten Notizen:\n{body}",
    },
    "hu": {
        "need_content": "Kicsit több tartalom kell a jegyzethez.",
        "save_fail": "Sajnos nem tudtam menteni a jegyzetet.",
        "created": "Rendben. Elmentettem a jegyzetet: {content}",
        "list_fail": "Sajnos nem tudtam lekérni a jegyzeteidet.",
        "list_empty": "Még nincs jegyzeted.",
        "list_header": "Ezek a jegyzeteid:\n{body}",
    },
}


def _strip_leading_create_trigger(user_text: str) -> str:
    """Strip a create trigger only when it is a leading prefix."""
    match = _CREATE_PATTERNS.search(user_text)
    if match is None or match.start() != 0:
        return user_text.strip()
    return _CREATE_PATTERNS.sub("", user_text, count=1).strip(" :,-").strip()


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
        lang = reply_language(text, deps)

        if _LIST_PATTERNS.search(text):
            return await self._list_notes(text, lang)

        return await self._create_note(text, lang)

    async def _create_note(self, user_text: str, lang: str) -> SkillResult:
        """Extract content and persist a note + semantic summary."""
        content = _strip_leading_create_trigger(user_text)
        if not content:
            content = user_text.strip()

        if len(content) < 2:
            return SkillResult(
                response_text=t(_REPLIES, lang, "need_content"),
                handled=True,
            )

        try:
            note = await self.repository.create(content=content)
        except Exception:
            logger.exception("Failed to create note")
            return SkillResult(
                response_text=t(_REPLIES, lang, "save_fail"),
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
            response_text=t(_REPLIES, lang, "created", content=note.content[:120]),
            handled=True,
            memory_writes=[{"content": summary, "importance": 0.55}],
        )

    async def _list_notes(self, user_text: str, lang: str) -> SkillResult:
        """Return a short summary of recent notes."""
        try:
            notes = await self.repository.list_notes(limit=10)
        except Exception:
            logger.exception("Failed to list notes")
            return SkillResult(
                response_text=t(_REPLIES, lang, "list_fail"),
                handled=True,
            )

        if not notes:
            return SkillResult(
                response_text=t(_REPLIES, lang, "list_empty"),
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
            response_text=t(_REPLIES, lang, "list_header", body=body),
            handled=True,
        )
