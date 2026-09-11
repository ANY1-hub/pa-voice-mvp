# AGENTS.md — pa-voice-mvp (Jarvis)

Standing handbook for coding agents. Keep this short. No secrets, no session handoffs, no NEXUS-in-product.

## What this is
Personal voice PA MVP (Masterschool). Repo: ANY1-hub/pa-voice-mvp. Working branch: `develop`.

## Hard boundaries
- Do **not** wire NEXUS (or any collaborator-memory MCP) into Jarvis product code.
- Keep three stores separate: Jarvis Mongo WM+SM, NEXUS (private collaborator memory), Grok chat memory.
- This-month MVP: 2-level WM+SM, notes, reminders, tenant isolation, voice EN/DE/HU.
- Out of scope unless a task explicitly says otherwise: 4-level Brain, family sharing, travel-time, video, LLM skill-router, WebSockets, NEXUS-as-product.

## Do-not-repeat (MVP)
Canonical collaborator-memory recall phrase (any LLM/agent with NEXUS): `pa-voice-mvp do-not-repeat`.
Same rules apply when you only have this file:

**Method**
1. Absolutes live here + NEXUS phrase above.
2. Open fixes go through an approved Slice-Brief (not drive-by patches).
3. Regressions are locked by tests/mutations — memory alone is not a control.

**Absolutes**
- Never `uv` / sync from WSL against this Windows `.venv`.
- Wipe/tests only on a DB whose name contains `test` (`jarvis_test`); never production `jarvis_db`.
- One exclusive pytest at a time on shared NAS `jarvis_test` (agent Shells can double-invoke).
- A green suite is a claim until a property mutation goes red; negatives need a control twin.
- Isolation: two real users. Do not mock away orchestrator/JWT on chat seams. Do not compensate production bugs in tests.
- Prompt-injection blocklist is a heuristic, not a control — wrap/spotlight untrusted text as data.
- No weak/placeholder `SECRET_KEY` at runtime. Never commit secrets.
- Tenant isolation always. Commit only after full suite + coverage floor (file/`--no-cov` is TDD loop only).

**Open security backlog (REVIEWEXTERN 2026-09-07)** — treat as Slice-Brief queue, do not invent:
P2 (mypy in CI first). Already done: P0-1 SECRET_KEY placeholder reject; P1-1 superuser mutation-proof tests; P1-2 blocklist whitespace; P1-3 login rate limit; P1-4 health+DB; P1-5 audio size before body; P1-6 ffmpeg timeout; P1-7 CI deps=image; P2-5 missing model key.

## Environment
- Local path (Ákos laptop): `C:\Users\nyiry\DEV\pa-voice-mvp`
- Use Windows `.venv` / project tooling; never `uv` from WSL for this tree.
- Follow `pyproject` (Ruff, Black, mypy) and lockfile conventions already in the repo.

## Quality loop (Grok Bot team)
Live: Coordinator-Bot (dispatcher; only coding voice to user) → Test-Manager (writes + runs tests) → Code-Writer1 (product only after failing test names) → Code-Write-Manager (audit only).

Non-trivial work: **Slice-Brief** first (goal, out-of-scope, architecture, security/threats, docs duty) approved by Ákos before tests/code. Use shared skills Slice Brief and Threat Pass when available.

Done gates:
- TDD loop may use names then file with `--no-cov` for speed.
- Commit / CI-ok only when Test-Manager reports **full suite pass with the project coverage floor** (same as CI). File-only / `--no-cov` is never a commit signal.
- Product patch: Code-Write-Manager three lines `architecture ok | security ok | clean+docs ok` **and** Test-Manager full-suite+coverage pass → commit.

User pushes unless they ask the coordinator to push. `STOP` voids Writer assignments. Jobsuche is a separate bot, not this loop.

## Tests
- Outside-in TDD. Purpose-Docstrings on tests.
- Prefer real seams: isolation with two users; chat/injection through real HTTP where required; do not mock away orch/JWT seams; do not compensate production bugs in tests.
- A green suite is a claim until a property mutation goes red.
- Run exact node ids first, then the containing file; `--no-cov` ok for focused runs. One pytest at a time on the shared test DB.

## Code style and sources
- English code/docs. PEP 257 on public API. Comments explain why, not what.
- Source order (never training-data patterns): (1) this file + project rules (`pyproject`, `docs/decisions/`, Blatt / project-memory if present) (2) latest official language/library/framework docs (3) Clean Code (4) community best-practice only if no conflict — escalate conflicts to Coordinator / Ákos.
- Lean dependencies. Vanilla JS frontend unless decided otherwise.

## Security
- Tenant isolation is a must.
- Treat untrusted text as data (spotlighting / wrap). A blocklist is a heuristic, not a control.
- Evidence-first. Honest timeouts. See decision `004` when present (FOREMAN grounding/guards).
- No weak `SECRET_KEY` placeholders. Never commit secrets or gitignored project-memory.

## Docs on user-visible change
Update `CHANGELOG` and `README` (or user-facing guide) when behaviour users see changes.

## What not to put here
Secrets, ephemeral handoffs, long tutorials, file-by-file maps agents can discover by reading the code.
