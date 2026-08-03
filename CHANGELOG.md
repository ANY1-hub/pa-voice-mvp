# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- ActiveRecallSkill – explicit recall of personal facts from Semantic Memory
  - Trigger phrases in EN/DE ("what do you know about…", "was weißt du über…")
  - Ranked facts returned without going through the full LLM path
  - Registered first in SkillRegistry so knowledge questions are not stolen by other skills
  - Unit tests with purpose docstrings

### Notes
- Next: Phase 5 (Polish & Demo)

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
