"""Abstract Skill interface and result type.

Skills stay independent of the orchestrator. The orchestrator only routes
to a skill when ``can_handle`` returns True and then uses the returned
``SkillResult``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillResult:
    """Outcome of a skill execution.

    Attributes:
        response_text: Natural-language reply the user should hear/see.
        handled: Whether the skill fully handled the turn (default True).
        memory_writes: Optional list of facts the caller may write to
            Semantic Memory (dicts with at least ``content``).
    """

    response_text: str
    handled: bool = True
    memory_writes: list[dict[str, Any]] = field(default_factory=list)


class Skill(ABC):
    """Base class for all skills.

    Concrete skills implement ``can_handle`` (cheap intent check) and
    ``execute`` (side-effecting work + response generation).
    """

    name: str

    @abstractmethod
    def can_handle(self, user_text: str, context: dict[str, Any] | None = None) -> bool:
        """Return True if this skill should handle the given user text.

        Args:
            user_text: Sanitized user utterance.
            context: Optional extra context (recent turns, language, …).

        Returns:
            True when the skill claims the turn.
        """
        ...

    @abstractmethod
    async def execute(
        self,
        user_text: str,
        user_id: str,
        **deps: Any,
    ) -> SkillResult:
        """Execute the skill and return a result.

        Args:
            user_text: Sanitized user utterance.
            user_id: Authenticated user ID (server-side).
            **deps: Injected collaborators (repositories, SemanticMemory, …).

        Returns:
            SkillResult with the reply text and optional memory side-effects.
        """
        ...
