"""Slice-Brief 4 / Cluster 2: identity address via User.display_name.

Jarvis must address and answer name questions from ``User.display_name``
(e.g. Ákosh). Leftover Semantic Memory name strings (Tony / Tony Stark),
including unprefixed free-text and Note/Reminder summaries that mention an
old name, must not win identity. Name utterances update the User record and
write the durable SM slot ``name`` with write-time supersession (Decision
002 end-state: ``valid_to`` / superseded) — not enrichment or an is_name
shim. Recall returns current facts only. Succession (name change) is in
scope; allergy correction is not.

Mutation: serving leftover Tony SM as the spoken name, or leaving two
current ``name`` slots, must go red. Control twins: non-name facts (allergy)
still surface; topic recall does not prepend display_name; user_id isolation
on supersession.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.memory.semantic_memory import SemanticMemory
from src.models.memory import SemanticMemoryFact
from src.services.orchestrator import ChatOrchestrator, system_prompt_for
from src.skills.active_recall.skill import ActiveRecallSkill

USER_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
USER_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
_NOW = datetime(2026, 9, 9, 12, 0, tzinfo=UTC)

# Demo leftovers (not ADDRESS_FACT_PREFIX copies).
_TONY_NAME_FACTS = (
    "User's name is Tony.",
    "Tony Stark",
    "User is called Tony Stark.",
)


def _fact(
    content: str,
    *,
    user_id: str = USER_A,
    importance: float = 0.8,
    slot: str | None = None,
    valid_to: datetime | None = None,
) -> SemanticMemoryFact:
    kwargs: dict = {
        "user_id": user_id,
        "content": content,
        "importance_score": importance,
        "entities_involved": [],
        "created_at": _NOW,
        "last_accessed": _NOW,
    }
    # End-state fields (Decision 002). Product must accept these on the model.
    if slot is not None:
        kwargs["slot"] = slot
    if valid_to is not None:
        kwargs["valid_to"] = valid_to
    return SemanticMemoryFact(**kwargs)


def _field_ops_match(doc: dict, key: str, ops: dict) -> bool:
    """Match one field against a Mongo operator dict ($exists/$eq/$regex/$ne)."""
    if "$exists" in ops and bool(ops["$exists"]) != (key in doc):
        return False
    if "$eq" in ops and doc.get(key) != ops["$eq"]:
        return False
    if "$regex" in ops:
        flags = re.IGNORECASE if "i" in str(ops.get("$options", "")) else 0
        if re.search(ops["$regex"], str(doc.get(key, "")), flags) is None:
            return False
    return not ("$ne" in ops and doc.get(key) == ops["$ne"])


def _doc_matches(doc: dict, query: dict) -> bool:
    for key, value in query.items():
        if key == "$or":
            if not any(_doc_matches(doc, clause) for clause in value):
                return False
            continue
        if isinstance(value, dict):
            if not _field_ops_match(doc, key, value):
                return False
        elif doc.get(key) != value:
            return False
    return True


class _FakeCursor:
    def __init__(self, items: list[dict]):
        self._items = [dict(item) for item in items]

    def sort(self, *args, **kwargs):
        return self

    def limit(self, n: int):
        self._items = self._items[:n]
        return self

    def __aiter__(self):
        return self._aiter()

    async def _aiter(self):
        for item in self._items:
            yield dict(item)


class SlotAwareCollection:
    """In-memory collection that honours user_id and current-only (valid_to)."""

    def __init__(self, docs: list[dict] | None = None):
        self._docs = [dict(d) for d in (docs or [])]
        self.find_queries: list[dict] = []
        # Product succession uses update_many; _touch_facts still uses update_one.
        self.update_many = AsyncMock(side_effect=self._update_many)
        self.update_one = AsyncMock(side_effect=self._update_one)
        self.insert_one = AsyncMock(side_effect=self._insert_one)
        self.find_one = AsyncMock(side_effect=self._find_one)

    def find(self, query: dict | None = None):
        query = dict(query or {})
        self.find_queries.append(query)
        matched = [d for d in self._docs if _doc_matches(d, query)]
        return _FakeCursor(matched)

    async def _find_one(self, query: dict | None = None):
        query = dict(query or {})
        for d in self._docs:
            if _doc_matches(d, query):
                return dict(d)
        return None

    async def _insert_one(self, doc: dict):
        self._docs.append(dict(doc))
        return MagicMock(inserted_id=doc.get("id") or doc.get("_id"))

    async def _apply_update(self, query: dict, update: dict) -> int:
        matched = 0
        for d in self._docs:
            if not _doc_matches(d, query):
                continue
            matched += 1
            if "$set" in update:
                d.update(update["$set"])
        return matched

    async def _update_one(self, query: dict, update: dict, **kwargs):
        matched = await self._apply_update(query, update)
        return MagicMock(matched_count=matched, modified_count=matched)

    async def _update_many(self, query: dict, update: dict, **kwargs):
        matched = await self._apply_update(query, update)
        return MagicMock(matched_count=matched, modified_count=matched)


# ---------------------------------------------------------------------------
# Active recall: display_name wins over leftover SM names
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_name_question_uses_display_name_not_leftover_tony_sm():
    """EN 'What is my name?' must answer with display_name, never leftover Tony SM."""
    mock_sem = MagicMock()
    mock_sem.search = AsyncMock(
        return_value=[_fact(c) for c in _TONY_NAME_FACTS]
        + [_fact("User is allergic to hazelnuts.")]
    )
    skill = ActiveRecallSkill(semantic_memory=mock_sem)

    result = await skill.execute(
        user_text="What is my name?",
        user_id=USER_A,
        display_name="Ákosh",
    )

    assert result.handled is True
    assert "Ákosh" in result.response_text
    body = result.response_text.casefold()
    assert "tony" not in body
    assert "stark" not in body


@pytest.mark.asyncio
async def test_german_name_question_ignores_tony_stark_sm():
    """DE 'Wie heiße ich?' must use display_name; leftover Tony Stark must not win."""
    mock_sem = MagicMock()
    mock_sem.search = AsyncMock(
        return_value=[
            _fact("User's name is Tony Stark."),
            _fact("The user prefers to be addressed as Tony."),
        ]
    )
    skill = ActiveRecallSkill(semantic_memory=mock_sem)

    result = await skill.execute(
        user_text="Wie heiße ich?",
        user_id=USER_A,
        display_name="Ákosh",
    )

    assert result.handled is True
    assert "Ákosh" in result.response_text
    assert "Tony" not in result.response_text
    assert "Stark" not in result.response_text


@pytest.mark.asyncio
async def test_hungarian_name_question_uses_display_name():
    """HU 'Mi a nevem?' must answer with display_name only."""
    mock_sem = MagicMock()
    mock_sem.search = AsyncMock(return_value=[_fact("User's name is Tony.")])
    skill = ActiveRecallSkill(semantic_memory=mock_sem)

    result = await skill.execute(
        user_text="Mi a nevem?",
        user_id=USER_A,
        display_name="Ákosh",
    )

    assert result.handled is True
    assert "Ákosh" in result.response_text
    assert "Tony" not in result.response_text


@pytest.mark.asyncio
async def test_about_me_filters_leftover_name_facts_keeps_allergy():
    """About-me: display_name address only; leftover name SM filtered; allergy stays."""
    mock_sem = MagicMock()
    mock_sem.search = AsyncMock(
        return_value=[
            _fact("User's name is Tony."),
            _fact("Tony Stark"),
            _fact("User is allergic to hazelnuts."),
        ]
    )
    skill = ActiveRecallSkill(semantic_memory=mock_sem)

    result = await skill.execute(
        user_text="What do you know about me?",
        user_id=USER_A,
        display_name="Ákosh",
    )

    assert "Ákosh" in result.response_text
    assert "Tony" not in result.response_text
    assert "hazelnut" in result.response_text.casefold()


@pytest.mark.asyncio
async def test_reminder_summary_with_old_name_does_not_win_identity():
    """Reminder writeback mentioning Tony must not become the spoken identity."""
    mock_sem = MagicMock()
    mock_sem.search = AsyncMock(
        return_value=[
            _fact("User set a reminder: call Tony about taxes"),
            _fact("User's name is Tony."),
        ]
    )
    skill = ActiveRecallSkill(semantic_memory=mock_sem)

    result = await skill.execute(
        user_text="What is my name?",
        user_id=USER_A,
        display_name="Ákosh",
    )

    assert "Ákosh" in result.response_text
    # Identity answer must not present Tony as the user's name.
    assert "tony" not in result.response_text.casefold()


@pytest.mark.asyncio
async def test_note_summary_with_old_name_does_not_win_identity():
    """Note writeback mentioning an old name must not win name recall."""
    mock_sem = MagicMock()
    mock_sem.search = AsyncMock(
        return_value=[
            _fact("User saved a note: Tony Stark birthday gift ideas"),
        ]
    )
    skill = ActiveRecallSkill(semantic_memory=mock_sem)

    result = await skill.execute(
        user_text="What's my name?",
        user_id=USER_A,
        display_name="Ákosh",
    )

    assert "Ákosh" in result.response_text
    assert "tony" not in result.response_text.casefold()
    assert "stark" not in result.response_text.casefold()


@pytest.mark.asyncio
async def test_topic_allergy_recall_still_returns_allergy_control():
    """Control twin: topic recall for allergies still surfaces the allergy fact."""
    mock_sem = MagicMock()
    mock_sem.search = AsyncMock(return_value=[_fact("User is allergic to hazelnuts.")])
    skill = ActiveRecallSkill(semantic_memory=mock_sem)

    result = await skill.execute(
        user_text="What do you know about my allergies?",
        user_id=USER_A,
        display_name="Ákosh",
    )

    assert result.handled is True
    assert "hazelnut" in result.response_text.casefold()
    # Topic path must not inject the preferred name (existing contract).
    assert "Ákosh" not in result.response_text


def test_system_prompt_address_uses_display_name_only():
    """Control: LLM system address instruction comes from display_name alone."""
    prompt = system_prompt_for("Ákosh")
    assert "Ákosh" in prompt
    assert "Tony" not in prompt
    assert "Address the user as Ákosh" in prompt


# ---------------------------------------------------------------------------
# Durable slot ``name`` + write-time supersession (Decision 002)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_name_slot_write_supersedes_previous_current():
    """Writing slot=name must leave exactly one current fact; old gets valid_to."""
    collection = SlotAwareCollection()
    mem = SemanticMemory(user_id=USER_A, collection=collection, embeddings_adapter=None)

    first = await mem.add_fact(
        "User's name is Tony.",
        importance=0.9,
        entities=["Tony"],
        slot="name",
    )
    second = await mem.add_fact(
        "User's name is Ákosh.",
        importance=0.9,
        entities=["Ákosh"],
        slot="name",
    )

    assert first.slot == "name"
    assert second.slot == "name"
    assert second.valid_to is None

    # Prior current for this user+slot must be closed (succession, not delete).
    assert collection.update_many.await_count >= 1
    current = [
        d
        for d in collection._docs
        if d.get("slot") == "name"
        and d.get("user_id") == USER_A
        and d.get("valid_to") is None
    ]
    assert len(current) == 1
    assert "Ákosh" in current[0]["content"]
    superseded = [
        d
        for d in collection._docs
        if d.get("slot") == "name"
        and d.get("user_id") == USER_A
        and d.get("valid_to") is not None
    ]
    assert len(superseded) == 1
    assert "Tony" in superseded[0]["content"]


@pytest.mark.asyncio
async def test_search_returns_only_current_name_slot():
    """Recall must not surface a superseded name slot value."""
    collection = SlotAwareCollection(
        [
            {
                "_id": "old",
                "id": "old",
                "user_id": USER_A,
                "content": "User's name is Tony.",
                "importance_score": 0.9,
                "entities_involved": ["Tony"],
                "created_at": _NOW.isoformat(),
                "last_accessed": _NOW.isoformat(),
                "embedding": None,
                "language": None,
                "slot": "name",
                "valid_to": _NOW.isoformat(),
            },
            {
                "_id": "cur",
                "id": "cur",
                "user_id": USER_A,
                "content": "User's name is Ákosh.",
                "importance_score": 0.9,
                "entities_involved": ["Ákosh"],
                "created_at": _NOW.isoformat(),
                "last_accessed": _NOW.isoformat(),
                "embedding": None,
                "language": None,
                "slot": "name",
                "valid_to": None,
            },
        ]
    )
    mem = SemanticMemory(user_id=USER_A, collection=collection, embeddings_adapter=None)

    results = await mem.search("name", limit=10)
    contents = [r.content for r in results]

    assert any("Ákosh" in c for c in contents)
    assert all("Tony" not in c for c in contents)


@pytest.mark.asyncio
async def test_name_slot_supersession_is_user_scoped():
    """Superseding A's name must not close B's current name slot (tenant isolation)."""
    collection = SlotAwareCollection(
        [
            {
                "_id": "b-name",
                "id": "b-name",
                "user_id": USER_B,
                "content": "User's name is Pepper.",
                "importance_score": 0.9,
                "entities_involved": ["Pepper"],
                "created_at": _NOW.isoformat(),
                "last_accessed": _NOW.isoformat(),
                "embedding": None,
                "language": None,
                "slot": "name",
                "valid_to": None,
            }
        ]
    )
    mem_a = SemanticMemory(
        user_id=USER_A, collection=collection, embeddings_adapter=None
    )

    await mem_a.add_fact(
        "User's name is Ákosh.",
        importance=0.9,
        entities=["Ákosh"],
        slot="name",
    )

    b_current = [
        d
        for d in collection._docs
        if d.get("user_id") == USER_B and d.get("slot") == "name"
    ]
    assert len(b_current) == 1
    assert b_current[0].get("valid_to") is None
    assert "Pepper" in b_current[0]["content"]

    # Every update_many that closes a name slot must include user_id == A.
    for call in collection.update_many.await_args_list:
        query = call.args[0] if call.args else call.kwargs.get("filter") or {}
        if query.get("slot") == "name" or (isinstance(query, dict) and "slot" in query):
            assert query.get("user_id") == USER_A


# ---------------------------------------------------------------------------
# Name utterances update User.display_name (not a competing free SM name)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_name_utterance_updates_user_display_name_not_competing_sm():
    """'My name is Ákosh' must update User.display_name; no second current free name SM."""
    mock_llm = AsyncMock()
    # First call: fact extract (before reply, per Slice 3). JSON name fact only.
    mock_llm.generate_response.side_effect = [
        '{"facts":[{"content":"User\'s name is Ákosh.","entities":["Ákosh"]}]}',
        "Nice to meet you, Ákosh.",
    ]
    mock_tts = AsyncMock()
    mock_tts.synthesize.return_value = b"wav"
    mock_wm = AsyncMock()
    mock_wm.retrieve.return_value = []
    mock_wm.add.return_value = None
    mock_wm.user_id = USER_A

    collection = SlotAwareCollection()
    mock_sm = SemanticMemory(
        user_id=USER_A, collection=collection, embeddings_adapter=None
    )
    # Spy wrapper: still a real SemanticMemory for slot writes.
    user_repo = AsyncMock()
    user_repo.set_display_name = AsyncMock(
        return_value=MagicMock(id=USER_A, display_name="Ákosh")
    )

    orch = ChatOrchestrator(
        llm=mock_llm,
        tts=mock_tts,
        working_memory=mock_wm,
        semantic_memory=mock_sm,
        display_name="Tony",
        user_repository=user_repo,
    )

    await orch.process(text="My name is Ákosh")

    user_repo.set_display_name.assert_awaited()
    args = user_repo.set_display_name.await_args.args
    assert USER_A in args or args[0] == USER_A
    assert any("Ákosh" in str(a) for a in args) or (
        "Ákosh" in str(user_repo.set_display_name.await_args.kwargs)
    )
    assert orch.display_name == "Ákosh"

    # At most one current name-slot fact; free-text Tony leftover must not stay current.
    current_name = [
        d
        for d in collection._docs
        if d.get("valid_to") is None
        and (
            d.get("slot") == "name" or "name is" in (d.get("content") or "").casefold()
        )
    ]
    # Competing unsuperseded Tony name content must not remain current.
    assert all("tony" not in (d.get("content") or "").casefold() for d in current_name)
    if current_name:
        assert len([d for d in current_name if d.get("slot") == "name"]) <= 1
