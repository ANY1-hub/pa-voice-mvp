"""Simple in-process skill registry.

Keeps the orchestrator thin: it only asks the registry for a matching skill.
"""

from __future__ import annotations

from typing import Any

from src.skills.base import Skill


class SkillRegistry:
    """Register and look up skills by name or by capability."""

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        """Add a skill instance under its ``name``.

        Args:
            skill: Concrete skill instance.

        Raises:
            ValueError: If a skill with the same name is already registered.
        """
        if skill.name in self._skills:
            raise ValueError(f"Skill '{skill.name}' is already registered")
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill | None:
        """Return a skill by name or None."""
        return self._skills.get(name)

    def find_handler(
        self, user_text: str, context: dict[str, Any] | None = None
    ) -> Skill | None:
        """Return the first skill that claims it can handle the text.

        Order is registration order (dict insertion order in Python 3.7+).

        Args:
            user_text: Sanitized user utterance.
            context: Optional extra context passed to ``can_handle``.

        Returns:
            Matching Skill or None.
        """
        for skill in self._skills.values():
            if skill.can_handle(user_text, context):
                return skill
        return None

    def list_names(self) -> list[str]:
        """Return the names of all registered skills."""
        return list(self._skills.keys())
