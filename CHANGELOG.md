# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Phase 4 kick-off (Option A): thin Skill interface + SkillRegistry
- Note model + dedicated `notes` collection (via NoteRepository)
- NotesSkill (create + list) with Semantic Memory summary write
- Unit tests for Note, NoteRepository, NotesSkill and Registry

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
