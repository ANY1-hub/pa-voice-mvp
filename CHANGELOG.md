# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] 2026-08-20

### Fixed
- Empty-DB SuperUser setup: FastAPI serves the Voice UI at ``/`` (same origin as the API). A headless-browser test (Playwright engine via ``JARVIS_E2E_BROWSER``, default chromium; Chrome/Edge if the Playwright build is missing) opens the real page on an empty users collection and fails if Sign-in is shown instead of Create SuperUser

### Added
- First-login preferred name: `display_name` on User, `POST /api/v1/auth/display-name`, chat/memory/admin gated until set (after password change). Jarvis addresses the user by that name; a semantic fact is stored for recall
- Skill phrase matching: accent-fold, inflection tails on long tokens, up to two filler words (three in Hungarian) between tokens
- Due reminder delivery: scheduler claims at ``due_at``, ``GET /api/v1/reminders/due`` + TTS, ``POST /ack``, frontend poll while the tab is open
- Working principle: prefer the end-state design (`docs/decisions/002-prefer-end-state-design.md`)
- Mongo ``_id`` is the application UUID for users, memory, notes, and reminders; unique ``id`` index (greenfield, no ObjectId)
- Chat-turn ``correlation_id`` (UUID v4) on ``ChatResult``, API responses, logs, and Working Memory writes
- Routing gold set (`tests/eval/routing_gold.json`) for EN/DE/HU skill vs LLM fallthrough
- Reminder create parses relative waits: `in 2 minutes`, `in 5 Minuten`, `2 perc múlva`
- Turn measurement on `ChatResult`: path, skill name, language, duration_ms (structured log)
- Mongo task probes: note/reminder persist, recall reads a seeded fact, search returns a mocked hit
- Change-password returns a fresh JWT so the session stays valid after `token_version` rotation
- Notes, Active Recall and Web Search reply in EN / DE / HU (same pattern as Reminders)
- Chat text and voice send the Help-panel language flag as an STT/TTS hint
- Chat turns that state a personal fact (name, preference, …) are extracted into Semantic Memory (importance 0.75, original language). Active Recall can find them on the next turn.
- Ten spoken “tell Jarvis about yourself” phrases in EN/DE/HU on the Help panel (`personal_facts`)
- Working Memory TTL of 48 hours (`expires_at` + Mongo TTL index)
- Ten canonical spoken trigger phrases per skill in EN/DE/HU (`src/skills/vocabulary.py`); Help panel lists only the selected language; `GET /api/v1/skills/phrases`
- Chat bubbles store UTC ISO timestamps and show local time next to You / J.A.R.V.I.S.; a date separator is inserted for each local calendar day
- Frontend i18n (EN / DE / HU) with flag buttons in the Help panel; help lists show only the selected language
- RemindersSkill replies in the user's language; optional LLM slot fill for create content/due date

### Fixed
- Forced password change no longer keeps a dead JWT (admin-created users were dumped back to login)
- German “Erinnere mich an …” creates a reminder instead of being stolen by Active Recall
- Language heuristic: German `mit` / English `van` no longer select the Hungarian TTS voice
- Hungarian text with ö/ü or áéíóú is no longer classified as German (ő/ű-only check was too strict)
- Hungarian agenda phrases (“mi van a héten”, “mi van ma”) use the matching date window instead of always today
- Reminders: "remind me today …" creates a reminder instead of listing the agenda; agenda no longer claims bare "today"/"this week" chat
- Reminders: time-of-day without a date token now sets due_at (today, or tomorrow if already past); `erinner(e)? mich` matches German create
- Semantic search is hybrid: facts without embeddings stay findable; weak cosine hits are dropped; consolidation job now embeds promoted facts
- Chat no longer returns HTTP 400 when persisting an assistant reply that contains blocklist substrings such as `system:`
- `must_change_password` is enforced on chat/memory/admin (not only the UI); password change invalidates existing JWTs
- Bootstrap: unique `bootstrap_slot` so two concurrent first-registers cannot both become SuperUser
- Docker Compose passes `SECRET_KEY` / `MONGODB_URI` (not the unused `JWT_SECRET`); Dockerfile copies `src/` before `-e .` and drops `--reload`
- Mongo substring search escapes user regex; DuckDuckGo errors propagate instead of looking like "no results"
- STT detected language is passed to TTS; a clearly German/Hungarian reply overrides a stale English hint
- Safari MediaRecorder fallback (mp4); speak-button click race while the mic permission prompt is open
- Default English Piper voice is the documented Alan GB model

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
