"""Thin orchestrator for the voice / text chat flow.

Coordinates: optional STT → input validation → memory context → LLM → TTS.
Keeps the FastAPI route thin and the adapters interchangeable.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass

from src.memory.semantic_memory import SemanticMemory
from src.memory.working_memory import WorkingMemory
from src.security.guardrails import process_user_message
from src.services.llm.base import LLMAdapter
from src.services.stt.base import STTAdapter
from src.services.tts.base import TTSAdapter

logger = logging.getLogger(__name__)

# Hard limit for uploaded audio (bytes). Protects CPU / memory on the host.
MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 10 MB

SYSTEM_PROMPT = """You are Jarvis, a personal voice assistant inspired by the AI from Iron Man.
You are helpful, concise, slightly witty, and you remember personal details about the user.
Use the provided personal context naturally when relevant. Do not invent facts about the user.
If you lack information, say so briefly.
Respond in the same language the user is using."""


@dataclass
class ChatResult:
    """Result of one full chat turn."""

    transcript: str
    response: str
    audio_base64: str | None = None


class ChatOrchestrator:
    """Coordinates a single conversational turn with memory context."""

    def __init__(
        self,
        llm: LLMAdapter,
        stt: STTAdapter | None = None,
        tts: TTSAdapter | None = None,
        working_memory: WorkingMemory | None = None,
        semantic_memory: SemanticMemory | None = None,
    ) -> None:
        self.llm = llm
        self.stt = stt
        self.tts = tts
        self.working_memory = working_memory
        self.semantic_memory = semantic_memory

    async def process(
        self,
        text: str | None = None,
        audio_bytes: bytes | None = None,
        language: str | None = None,
    ) -> ChatResult:
        """
        Run one full turn.

        Exactly one of `text` or `audio_bytes` must be provided.
        Returns transcript, LLM response text and optional TTS audio (base64).
        """
        if not text and not audio_bytes:
            raise ValueError("Either text or audio_bytes must be provided")
        if text and audio_bytes:
            raise ValueError("Provide either text or audio_bytes, not both")

        # 1. Resolve transcript (STT or plain text)
        transcript = await self._resolve_transcript(text, audio_bytes, language)

        # 2. Input validation / guardrails
        sanitized = process_user_message(transcript)

        # 3. Memory context
        memory_context = await self._build_memory_context(sanitized)

        # 4. LLM
        messages = self._build_messages(sanitized, memory_context)
        response_text = await self.llm.generate_response(messages)
        response_text = (response_text or "").strip()
        if not response_text:
            response_text = "I am sorry, I could not generate a response."

        # 5. Persist the turn in Working Memory (active use of memory)
        await self._store_turn(sanitized, response_text)

        # 6. TTS (optional – text-only clients can ignore audio)
        audio_b64 = await self._maybe_synthesize(response_text)

        return ChatResult(
            transcript=sanitized,
            response=response_text,
            audio_base64=audio_b64,
        )

    async def _resolve_transcript(
        self,
        text: str | None,
        audio_bytes: bytes | None,
        language: str | None,
    ) -> str:
        """Return the user utterance as text (via STT when audio is given)."""
        if audio_bytes is None:
            return text or ""

        if len(audio_bytes) > MAX_AUDIO_BYTES:
            raise ValueError(
                f"Audio too large ({len(audio_bytes)} bytes). Max is {MAX_AUDIO_BYTES}"
            )
        if self.stt is None:
            raise RuntimeError("STT adapter is not configured")

        transcript = await self.stt.transcribe(audio_bytes, language=language)
        if not transcript.strip():
            raise ValueError("Could not transcribe audio (empty result)")
        return transcript

    async def _maybe_synthesize(self, response_text: str) -> str | None:
        """Run TTS if available; never let TTS failure break the turn."""
        if self.tts is None:
            return None
        try:
            audio_raw = await self.tts.synthesize(response_text)
            if audio_raw:
                return base64.b64encode(audio_raw).decode("ascii")
        except Exception:
            logger.exception("TTS failed – continuing without audio")
        return None

    async def _build_memory_context(self, query: str) -> str:
        """Retrieve a short, relevant memory snippet for the LLM."""
        parts: list[str] = []

        if self.working_memory is not None:
            try:
                recent = await self.working_memory.retrieve(limit=8)
                if recent:
                    lines = [f"- {item.content}" for item in recent]
                    parts.append("Recent conversation context:\n" + "\n".join(lines))
            except Exception:
                logger.exception("Failed to retrieve working memory")

        if self.semantic_memory is not None:
            try:
                facts = await self.semantic_memory.search(query=query, limit=5)
                if facts:
                    lines = [f"- {fact.content}" for fact in facts]
                    parts.append("Relevant personal facts:\n" + "\n".join(lines))
            except Exception:
                logger.exception("Failed to search semantic memory")

        return "\n\n".join(parts) if parts else ""

    def _build_messages(
        self, user_text: str, memory_context: str
    ) -> list[dict[str, str]]:
        """Assemble the chat messages for the LLM."""
        system = SYSTEM_PROMPT
        if memory_context:
            system += (
                "\n\n## Personal context (use naturally, do not invent)\n"
                + memory_context
            )

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ]

    async def _store_turn(self, user_text: str, assistant_text: str) -> None:
        """Store the turn in Working Memory so future turns have context."""
        if self.working_memory is None:
            return
        try:
            await self.working_memory.add(
                content=f"User: {user_text}",
                importance=0.4,
            )
            await self.working_memory.add(
                content=f"Jarvis: {assistant_text}",
                importance=0.4,
            )
        except Exception:
            logger.exception("Failed to store turn in working memory")
