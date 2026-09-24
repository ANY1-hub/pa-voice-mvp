# AGENTS.md — pa-voice-mvp (Jarvis)

Standing handbook for coding agents. Keep this short. No secrets, no session handoffs.

If AGENTS.local.md exists, also read it.

## What this is
Personal voice PA MVP (Masterschool). Repo: ANY1-hub/pa-voice-mvp. Working branch: `develop`.

## Hard boundaries
- Do **not** wire any private collaborator-memory MCP into Jarvis product code.
- Keep product stores separate: Jarvis Mongo WM+SM stays the only in-product memory.
- This-month MVP: 2-level WM+SM, notes, reminders, tenant isolation, voice EN/DE/HU.
- Out of scope unless a task explicitly says otherwise: 4-level Brain, family sharing, travel-time, video, LLM skill-router, WebSockets, collaborator-memory-as-product.
- **EU AI Act compliance is mandatory** for product behaviour and Slice-Briefs (transparency, honest limits, risk-class awareness, human-controlled side effects). Local checklist: docs/research/eu-ai-act-standing-requirement.md (gitignored). Not legal advice — standing engineering constraint.

## Do-not-repeat (MVP)

**Method**
1. Absolutes live here (and in local notes when present).
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

**Open security backlog** — treat as Slice-Brief queue, do not invent:
P2 remaining: none (2026-09-07 P2 queue empty). Already done: P2-6 bcrypt 72; P2-7 admin list; P2-1 mypy in CI; P2-2 user_id indexes; P2-3 blocklist leak; P2-4 CORS; P0-1 SECRET_KEY placeholder reject; P1-1 superuser mutation-proof tests; P1-2 blocklist whitespace; P1-3 login rate limit; P1-4 health+DB; P1-5 audio size before body; P1-6 ffmpeg timeout; P1-7 CI deps=image; P2-5 missing model key.

## Environment
- Local clone path is machine-specific; use placeholders in public docs.
- Use Windows `.venv` / project tooling; never `uv` from WSL for this tree.
- Follow `pyproject` (Ruff, Black, mypy) and lockfile conventions already in the repo.

## Quality loop
Separate roles: dispatch / test authorship / product implementation / audit. Product code lands only after failing tests exist. Non-trivial work: **Slice-Brief** first (goal, out-of-scope, architecture, security/threats incl. EU AI Act / GDPR touchpoints, docs duty) approved by the maintainer before tests/code.

Done gates:
- TDD loop may use names then file with `--no-cov` for speed.
- Commit / CI-ok only when the full suite passes with the project coverage floor (same as CI). File-only / `--no-cov` is never a commit signal.
- Product patch: architecture ok | security ok | clean+docs ok **and** full-suite+coverage pass → commit.

The maintainer pushes unless they ask for a push. `STOP` voids open writer assignments.

## Tests
- Outside-in TDD. Purpose-Docstrings on tests.
- Prefer real seams: isolation with two users; chat/injection through real HTTP where required; do not mock away orch/JWT seams; do not compensate production bugs in tests.
- A green suite is a claim until a property mutation goes red.
- Run exact node ids first, then the containing file; `--no-cov` ok for focused runs. One pytest at a time on the shared test DB.

## Code style and sources
- English code/docs. PEP 257 on public API. Comments explain why, not what.
- Source order (never training-data patterns): (1) this file + project rules (`pyproject`, `docs/decisions/`, project-memory if present) (2) latest official language/library/framework docs (3) Clean Code (4) community best-practice only if no conflict — escalate conflicts to the maintainer.
- Lean dependencies. Vanilla JS frontend unless decided otherwise.

## Security
- Tenant isolation is a must.
- Treat untrusted text as data (label personal context as untrusted in the system prompt). A blocklist is a heuristic, not a control.
- Evidence-first. Honest timeouts. See decision `004` when present (grounding and guards).
- No weak `SECRET_KEY` placeholders. Never commit secrets or gitignored project-memory.
- EU AI Act: mark AI-assembled context where it matters; no fake memory; reopen principal questions (step 0) / a compliance Slice before any high-risk use class (employment, credit, health diagnosis, biometric ID, minors as product focus, etc.). GDPR structures stay in force wherever personal data exists.

## Docs on user-visible change
Update `CHANGELOG` and `README` (or user-facing guide) when behaviour users see changes.

## What not to put here
Secrets, ephemeral handoffs, long tutorials, file-by-file maps agents can discover by reading the code, private workflow tooling names.
