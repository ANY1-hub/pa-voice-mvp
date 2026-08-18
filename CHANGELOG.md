# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] 2026-08-18

### Added
- Auth bootstrap hardening (Phase 5):
  - `must_change_password` on User / UserPublic
  - `GET /api/v1/auth/bootstrap-status` → `{ needs_bootstrap: bool }`
  - `POST /api/v1/auth/register` only allowed when user count is 0; otherwise 403
  - First register creates SuperUser with `must_change_password=false`
  - `POST /api/v1/auth/change-password` (current + new, min 12 chars) clears the flag
  - Admin `POST /users` always sets `must_change_password=true`
  - Tests updated (`wipe_users`, second-register forbidden, force-change flow)
- Frontend Auth-UI (Phase 5):
  - Bootstrap screen when `needs_bootstrap` (Create SuperUser)
  - Normal login otherwise
  - Forced password-change screen after login when `must_change_password`
  - Admin panel (SuperUser): list users, create user, toggle active / superuser
- SuperUser bootstrap: first successful registration on an empty users collection becomes SuperUser
- `is_superuser` flag on User / UserPublic
- Admin routes (SuperUser only) under `/api/v1/admin/`:
  - `GET /users` – list users
  - `POST /users` – create user (optional `is_superuser`)
  - `PATCH /users/{user_id}` – update `is_active` / `is_superuser`
- Dependency `get_current_superuser` (403 for non-superusers)
- User vocabulary guide: `docs/user-guide.md` (EN/DE/HU trigger phrases for Notes, Reminders, WebSearch, ActiveRecall)
- Tests for bootstrap, SuperUser guard and admin endpoints
- Date-aware Reminders (Phase 5):
  - NL date/time parsing on create (today/tomorrow/weekdays + “um 14 Uhr” / “at 14:00”)
  - Agenda queries: today / this week / next week / this month (day-grouped output)
  - Specific event lookup (“wann habe ich meinen Termin bei …?”) with date + time
  - Repository: `due_from`/`due_to` filter + `search_by_content`
  - Vocabulary + tests updated
  - Semantic Memory search now touches `last_accessed` and applies a small importance boost (+0.05, capped at 1.0) on every successful hit. Makes the existing cleanup path actually useful.
- Scheduler/consolidation hardening (Phase 5):
  - Consolidation job uses stable id, replace_existing, max_instances=1, coalesce
  - Per-user error isolation so one failed user does not abort the whole job
  - Resilience tests for WebSearchSkill (backend failure, semantic/add_fact errors) and DuckDuckGoClient mapping/exception paths

### Fixed
- Error handling polish (Phase 5):
  - LLM failures return a friendly fallback instead of HTTP 500
  - Unexpected skill exceptions fall through to the LLM path
  - STT conversion/transcription errors map to clear ValueError (HTTP 400)
  - Chat 500 responses use a user-friendly message (no internal class names)

### Notes
- Phase 5 (Polish & Demo) in progress
- Public registration is closed after the first SuperUser; further accounts only via Admin API

## [0.3.0] - 2026-08-03 — Phase 4 closed

Skills layer complete (Notes, Reminders, memory-augmented Web Search).

### Added
- Phase 4 Skills foundation (Option A):
  - Thin `Skill` protocol + `SkillResult`
  - `SkillRegistry` (first-match-wins routing)
- NotesSkill (create + list) with dedicated `notes` collection + Semantic Memory summary write
- RemindersSkill (create + list) with dedicated `reminders` collection + Semantic Memory summary write
- Note + Reminder Pydantic models and repositories (user-scoped)
- Both skills wired into Orchestrator via `get_skill_registry` (deps)
- Unit tests for models, repositories, skills and registry
- Skill-routing tests (LLM skipped when a skill returns `handled=True`)
- WebSearchSkill (memory-augmented DuckDuckGo search)
  - Thin SearchClient + DuckDuckGoClient (ddgs)
  - Personal context from Semantic Memory woven into results
  - Short summary fact written back to Semantic Memory
  - Unit tests with mocked client + purpose docstrings
- ActiveRecallSkill – explicit recall of personal facts from Semantic Memory
  - Trigger phrases in EN/DE ("what do you know about…", "was weißt du über…")
  - Ranked facts returned without going through the full LLM path
  - Registered first in SkillRegistry so knowledge questions are not stolen by other skills
  - Unit tests with purpose docstrings

### Changed
- Orchestrator stays thin: skill routing happens after Guardrails, before memory/LLM path
- `_build_messages` made staticmethod; more precise exception handling in orchestrator paths

## [0.2.0] - 2026-07-28 — Phase 3 closed

Full voice pipeline with multi-language TTS, hardened tests/CI, and MVP prompt-injection guardrails.

### Added
- Voice pipeline end-to-end: STT → transcript → Memory context → LLM → TTS
- Chat API: `POST /api/v1/chat/text`, `POST /api/v1/chat/voice` (JWT)
- Frontend: modular Jarvis UI, live transcript + response, speaking indicator, 16 kHz WAV upload
- Multi-voice Piper TTS (`en` / `de` / `hu`) with language detection heuristic
- Prompt-injection blocklist + regression tests (PATT-inspired)
- Broad unit/API test suite (orchestrator, chat, memory, auth, security, scheduler, piper)
- CI: Ruff, Black, Pytest, Mongo service, uv cache, **coverage floor 80%**
- Scheduler start/stop idempotent; consolidation job covered by tests

### Fixed
- Piper generator API + WAV wrapping for browser playback
- STT browser WAV path + imageio-ffmpeg conversion
- EmailStr domain lowercasing assertion in auth tests
- Ruff UP038 / import hygiene for CI green builds

### Changed
- Orchestrator stays thin; STT/TTS as services; memory failures do not break a turn
- Semantic search remains in-memory cosine (native `$vectorSearch` deferred for NAS CE)

## [0.1.0] - 2026-07-16

### Added
- Project initialization
- Basic README and project structure
- Security & Quality standards defined (ISO alignment)
- Phase 0–2 foundation (Memory Core, Auth + Multi-User, DI)
