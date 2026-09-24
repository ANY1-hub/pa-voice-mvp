# Memory Design (neuro-inspired)

**Inspiration:** Atkinson-Shiffrin Multi-Store Model + current consolidation research
**Goal:** The agent actively collects insights and maintains the knowledge archive (Jarvis-like).

## Current architecture (MVP)

Two memory levels:

### 1. Working Memory (short-term)

- Session context and recent interactions
- Fields per entry:
  - `id` / Mongo ``_id`` (same UUID v4; unique index)
  - `user_id` (UUID string)
  - `content`
  - `importance_score` (0.0 – 1.0)
  - `created_at`
  - `last_accessed`
  - `correlation_id` (optional chat-turn UUID)
- Stored in MongoDB collection `working_memory`
- Retrieval: sorted by `last_accessed`, optional text filter; expired items (`expires_at`) are hidden
- TTL: 48 hours (`expires_at` as BSON Date + Mongo TTL index)
- Before write: security check via `validate_memory_write`
- Chat turns (importance 0.4) stay short-term; durable facts are also extracted into Semantic Memory

### 2. Semantic Memory (long-term)

- Durable user insights: preferences, facts, patterns, knowledge state
- Fields per entry:
  - `id` / Mongo ``_id`` (same UUID v4; unique index)
  - `user_id` (UUID string)
  - `content`
  - `importance_score` (0.0 – 1.0)
  - `entities_involved`
  - `created_at`
  - `last_accessed`
  - `embedding` (optional)
  - `language` (optional ISO tag of the original text; no auto-translation)
  - `slot` (optional durable slot id, e.g. ``name``; name-slot supersession)
  - `valid_to` (optional datetime; when set, the fact is superseded and must not win recall)
- Stored in MongoDB collection `semantic_memory`
- Before write: security check via `validate_memory_write`

#### Retrieval strategy (current)

1. **With embeddings adapter:** query is embedded; ranking by cosine similarity **in-memory** (sufficient for MVP scale).
2. **Without embeddings:** case-insensitive text search on `content`, sorted by `importance_score`.

> Native MongoDB `$vectorSearch` is possible in Community Edition since 2025/2026, but needs an extra search process (`mongot`) and index setup. For the current local-first / NAS setup (plain `mongo` image) the in-memory path stays intentionally active. A later switch is prepared.

## Security

- Every write goes through `src/security/guardrails.py` → `validate_memory_write`
- Input validation and memory policy (importance threshold, allowed sources)
- User isolation via `user_id` (UUID) in every query
- Auth: JWT `user_id` (no `X-User-Id` header)

## Consolidation (MVP – minimal, extensible)

Background job (APScheduler, every 60 minutes):

1. **Promotion Working → Semantic**
   Working Memory items with `importance_score >= 0.7` are copied into Semantic Memory and then deleted from Working Memory.

2. **SemanticMemory.consolidate()** (per user):
   - `_cleanup_old_entries()`: deletes facts with `importance_score < 0.25` and `last_accessed` older than 30 days.
   - `_deduplicate()`: removes exact duplicates (normalised content). Keep order: copy with an embedding first, then highest `importance_score`, then latest `last_accessed`.
   - `_link_entities()`: **Stub** – prepared for entity linking (ambitious version).
   - `_detect_drift()`: **Stub** – prepared for preference-drift detection (ambitious version).

The method shape is deliberate so the ambitious version can fill the stubs later without changing the public API or the scheduler.

## Later extension (4-level)

Planned after the MVP:

- **Episodic Memory** – concrete events / episodes
- **Perceptual Memory** – sensory / multimodal impressions

## Relevant files

| Area | File |
|------|------|
| Working Memory | `src/memory/working_memory.py` |
| Semantic Memory | `src/memory/semantic_memory.py` |
| Models | `src/models/memory.py` |
| Security | `src/security/guardrails.py`, `memory_policy.py`, `input_validator.py` |
| API | `src/api/routes/memory.py` |
| Scheduler / Job | `src/tasks/scheduler.py` |
| Embeddings | `src/services/embeddings/` |
| Tests (Consolidation) | `tests/test_consolidation.py` |
