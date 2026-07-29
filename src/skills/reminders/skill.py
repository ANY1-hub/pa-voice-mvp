"""RemindersSkill – create and list structured reminders with Semantic Memory summary."""

from __future__ import annotations

import logging
import re
from typing import Any

from src.memory.semantic_memory import SemanticMemory
from src.skills.base import Skill, SkillResult
from src.skills.reminders.repository import ReminderRepository

logger = logging.getLogger(__name__)

_CREATE_PATTERNS = re.compile(
    r"\b(remind me|reminder|erinner mich|erinnerung|emlékeztess|"
    r"set a reminder|stell eine erinnerung|merk dir das)\b",
    re.IGNORECASE,
)
_LIST_PATTERNS = re.compile(
    r"\b(list reminders|show reminders|meine erinnerungen|"
    r"erinnerungen zeigen|what reminders|zeig mir die erinnerungen|"
    r"listázd az emlékeztetőket)\b",
    re.IGNORECASE,
)


class RemindersSkill(Skill):
    """Create and retrieve structured reminders.

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
        return bool(_CREATE_PATTERNS.search(text) or _LIST_PATTERNS.search(text))

    async def execute(
        self,
        user_text: str,
        user_id: str,
        **deps: Any,
    ) -> SkillResult:
        text = user_text.strip()

        if _LIST_PATTERNS.search(text):
            return await self._list_reminders(text)

        return await self._create_reminder(text)

    async def _create_reminder(self, user_text: str) -> SkillResult:
        content = _CREATE_PATTERNS.sub("", user_text).strip(" :,-").strip()
        if not content:
            content = user_text.strip()

        if len(content) < 2:
            return SkillResult(
                response_text="I need a bit more content for the reminder.",
                handled=True,
            )

        try:
            reminder = await self.repository.create(content=content)
        except Exception:
            logger.exception("Failed to create reminder")
            return SkillResult(
                response_text="Sorry, I could not save the reminder.",
                handled=True,
            )

        summary = f"User set a reminder: {reminder.content[:200]}"

        if self.semantic_memory is not None:
            try:
                await self.semantic_memory.add_fact(
                    fact=summary,
                    importance=0.6,
                    entities=["reminder"],
                )
            except Exception:
                logger.exception("Failed to write reminder summary to semantic memory")

        return SkillResult(
            response_text=f"Got it. I'll remind you: {reminder.content[:120]}",
            handled=True,
            memory_writes=[{"content": summary, "importance": 0.6}],
        )

    async def _list_reminders(self, user_text: str) -> SkillResult:
        try:
            reminders = await self.repository.list_reminders(limit=10)
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

        lines = []
        for i, r in enumerate(reminders, 1):
            preview = r.content[:80] + ("…" if len(r.content) > 80 else "")
            lines.append(f"{i}. {preview}")

        body = "\n".join(lines)
        return SkillResult(
            response_text=f"Here are your pending reminders:\n{body}",
            handled=True,
        )
