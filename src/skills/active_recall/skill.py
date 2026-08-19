"""ActiveRecallSkill – answer explicit "what do you know about X" questions from Semantic Memory."""

from __future__ import annotations

import logging
import re
from typing import Any

from src.memory.semantic_memory import SemanticMemory
from src.models.memory import SemanticMemoryFact
from src.skills.base import Skill, SkillResult

logger = logging.getLogger(__name__)

# Longer phrases first so stripping leaves a clean topic.
_TRIGGER_PHRASES: list[str] = [
    r"what do you know about me",
    r"what do you know about",
    r"what do you remember about",
    r"what did i tell you about",
    r"remind me what i (said|told you) about",
    r"remind me about",
    r"recall what you know about",
    r"was weißt du über mich",
    r"was weißt du über",
    r"was erinnerst du dich an",
    r"was habe ich (dir )?(über|zu) .+ gesagt",
    r"erinnere mich an",
    r"was weißt du noch (über|von)",
    r"meine vorlieben",
    r"my preferences",
    r"what do you know",
]

_TRIGGER_RE = re.compile(
    r"\b(" + r"|".join(_TRIGGER_PHRASES) + r")\b",
    re.IGNORECASE,
)

_FILLER_RE = re.compile(
    r"^(about|über|an|zu|von|regarding|concerning)\s+",
    re.IGNORECASE,
)


class ActiveRecallSkill(Skill):
    """Explicit active recall of personal facts stored in Semantic Memory.

    Triggers on clear recall intents and returns ranked facts without going
    through the full LLM path. Keeps the Orchestrator thin.
    """

    name = "active_recall"

    def __init__(self, semantic_memory: SemanticMemory | None = None) -> None:
        self.semantic_memory = semantic_memory

    def can_handle(self, user_text: str, context: dict[str, Any] | None = None) -> bool:
        text = user_text.strip()
        if not text:
            return False
        return bool(_TRIGGER_RE.search(text))

    async def execute(
        self,
        user_text: str,
        user_id: str,
        **deps: Any,
    ) -> SkillResult:
        query = self._extract_query(user_text)

        if self.semantic_memory is None:
            return SkillResult(
                response_text="I have no long-term memory available right now.",
                handled=True,
            )

        try:
            facts = await self.semantic_memory.search(query=query, limit=6)
        except Exception:
            logger.exception("Active recall search failed")
            return SkillResult(
                response_text="Sorry, I could not look that up right now.",
                handled=True,
            )

        return self._format_response(query, facts)

    def _extract_query(self, user_text: str) -> str:
        """Strip trigger phrases and light fillers; return the topic."""
        text = user_text.strip()
        # Remove the first matching trigger phrase
        text = _TRIGGER_RE.sub("", text, count=1).strip(" :?,-").strip()
        text = _FILLER_RE.sub("", text).strip()
        return text

    def _format_response(
        self,
        query: str,
        facts: list[SemanticMemoryFact],
    ) -> SkillResult:
        if not facts:
            if query:
                msg = f"I don't have anything stored about '{query}' yet."
            else:
                msg = "I don't have any personal facts stored yet."
            return SkillResult(response_text=msg, handled=True)

        lines = [f"- {f.content}" for f in facts]
        body = "\n".join(lines)

        if query and query.lower() not in {"me", "mich", "mir"}:
            header = f"Here's what I know about {query}:"
        else:
            header = "Here's what I know about you:"

        return SkillResult(
            response_text=f"{header}\n{body}",
            handled=True,
        )
