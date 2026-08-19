# Project Memory – pa-voice-mvp

**Last updated:** 2026-08-19  
**Branch:** `develop`  
**Latest HEAD:** `40f3549`

This file is the durable, human-readable source of truth for major project decisions.  
The agent keeps the internal Project Memory in sync with this document.

---

## Vision / Goal

Voice-first Personal Assistant (MVP) that actively collects, stores, links and uses personal insights.  
Inspired by Jarvis. One big "Speak" button, out-of-the-box usable, local-first.

---

## Memory Strategy (MVP)

- **2 levels only:** Working Memory + Semantic Memory
- Working: short-term session context + recent interactions (TTL 48 h via `expires_at` + Mongo TTL index, importance)
- Semantic: long-term facts/preferences with timestamps, importance scores, vector embeddings, `entities_involved`
- Active maintenance via background consolidation jobs
- Personal facts stated in chat are extracted into Semantic Memory (importance 0.75, original language)
- Storage: MongoDB Community (Docker on Synology NAS), user isolation by namespace
- Later expansion to 4 levels (Episodic + Perceptual) is **post-MVP**

Detailed design: `docs/memory-design.md`

---

## Tech Stack (MVP)

| Component       | Choice                                      |
|-----------------|---------------------------------------------|
| STT             | faster-whisper (local)                      |
| TTS             | Piper (local, multi-voice en/de/hu)         |
| Backend         | FastAPI                                     |
| DB              | MongoDB Community Edition (Docker on NAS)   |
| LLM / Embeddings| Temporary OpenAI (gpt-4o-mini / text-embedding-3-small) until ~Oct 2026 |
| Adapter Pattern | Ready for later swap to local models        |
| Web Search      | DuckDuckGo (`ddgs`)                         |
| Background Tasks| APScheduler                                 |
| Frontend        | Vanilla HTML/JS + Tailwind (CDN)            |
| Auth            | JWT + bcrypt, 24 h token lifetime, server-generated UUID v4 |
| VCS             | GitHub (https://github.com/ANY1-hub/pa-voice-mvp) |

---

## Architecture Decisions

- Dependency Injection for Memory & Auth (collections via constructor, FastAPI deps)  
  → `docs/decisions/001-dependency-injection-memory.md`
- STT/TTS as separate services, Orchestrator stays thin
- Security by Design (ISO/IEC 27001 principles)
- Skills use Option A: own Mongo collections (`notes`, `reminders`) + short summary fact into Semantic Memory
- Skill routing: first-match-wins (phrase-based for MVP)

---

## MVP Scope (until mid/end September 2026)

**In scope**
- Full voice pipeline from the beginning
- Active recall of personal facts during conversation
- Multi-user isolation
- Background consolidation
- Skills: Notes, Reminders (date-aware + agenda), memory-augmented Web Search, Active Recall
- SuperUser bootstrap + Frontend Auth-UI
- Automatic extraction of personal facts from chat into Semantic Memory

**Explicitly out of MVP**
- Streaming
- Local LLM
- GDPR data-rights UI (hard post-MVP requirement)
- 4-level memory
- Home Assistant
- Voice biometrics
- Complex roles matrix
- Intent router (LLM-based) – deferred; phrase routing is sufficient for MVP

---

## Phases

| Phase | Status |
|-------|--------|
| 0 Setup & Foundation | ✅ |
| 1 Memory Core | ✅ |
| 2 Auth + Multi-User | ✅ |
| 3 Voice Pipeline MVP | ✅ |
| 4 Skills | ✅ closed |
| **5 Polish & Demo** | **← current** |

---

## Phase 5 Progress (2026-08-19)

**Done**
- Auth bootstrap hardening (`must_change_password`, SuperUser, Admin routes + Frontend UI)
- Date-aware Reminders + agenda + localized replies (EN/DE/HU) + optional LLM slot fill
- Chat timestamps: UTC ISO stored, local time next to You / J.A.R.V.I.S. + date separators
- Help-Panel i18n with flag buttons (🇬🇧 / 🇩🇪 / 🇭🇺) + language-filtered phrase lists
- Canonical spoken trigger phrases (10 per skill in EN/DE/HU) in `src/skills/vocabulary.py` + `GET /api/v1/skills/phrases`
- Personal-fact extraction from chat → Semantic Memory (importance 0.75) + Help-panel phrases
- Working Memory TTL 48 h (`expires_at` + Mongo TTL index)
- Semantic Memory hybrid search + embedding resilience + `last_accessed` boost
- STT language → TTS + reply-language override
- Many resilience fixes (Safari recording, CORS, DuckDuckGo errors, bootstrap race, etc.)

**Still open**
- Residual skill-response language consistency
- Demo polish / hardening

---

## Key Rules

- All code, docs, commits, comments in **English**
- User pushes; Agent verifies on GitHub afterwards
- No code suggestions without existing reference code or explicit “mach weiter”
- Local-first + easy model swap
- Memory is active, not passive
- TDD for new increments (failing test first)
- After every code-changing increment: check CI on `develop`. Fix immediately if red.
- Changelog & docs hygiene after every feature increment and especially when closing a Phase
- Test purpose docstrings on every new test function

---

## Post-MVP Notes (compact North Star)

- **Memory Evolution**: Expand to 4 levels. Long-term recommendation: Temporal Knowledge Graphs (Zep/Graphiti) + Hybrid.  
  Research notes under `docs/research/`.
- **GDPR**: Mandatory UI for view + delete own data (Art. 15/17). Export (Art. 20) nice-to-have.
- **LLM Upgrade**: Adapter Pattern ready. Main candidate = Inkling (Thinking Machines, open-weights MoE).
- **GOVERN / ASSURE**, **Agent Harness**, **Graph Engineering**, **Loop Engineering** – active reminders with clear triggers (see internal memory / research notes).
- **Family Multi-Agent Coordination**, File/Image → Perceptual Memory, online calendar sync – later.

(Full research notes stay in `docs/research/`. This section only keeps the short North Star.)

---

## Process Note

Whenever the agent updates the internal Project Memory, it **must also update this file** (`docs/project-memory.md`) in the same session and keep both in sync.
