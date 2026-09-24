# Decision: Grounding, spotlighting, and two-tier output guards

**Date:** 2026-09-02
**Status:** Accepted (design decision). Items 3–5 are only partly implemented today; full spotlighting (per-call random delimiter + datamarking), live-chain attack tests against the real wrap, and two-tier output guards remain roadmap work. "Accepted" means the approach is agreed, not that every item is done.
**Source:** Prior research from an internal review of Masterschool Institute of Technology capstone AI patterns (2026). Behaviour only.
**Do not:** import shop-floor domain code or private collaborator-memory tooling. Jarvis Brain stays independent of the voice frontend and is not a collaborator-memory store.

Motto: The model is the last step. Stating a rule in the prompt is not a control.

## Context

A related capstone explored a shop floor that remembers. Its AI block is useful to Jarvis because the hard work is not the model call. It is gathering evidence, fencing untrusted text, and checking the answer — the same class of remaining capstone items (structural wrap, live-chain injection tests, silent-success).

Jarvis already: phrase-registry before LLM, Notes without an API key, memory labelled untrusted in `_build_messages`, 90% coverage gate, mutation-as-claim from the 1 Sep review checklist.

## Decision

### Now (Phase 5 / this-month MVP)

1. **Not one model for everything.** Skills, clocks, and isolation stay deterministic. The LLM does not route skills and does not invent "nothing stored" / "deleted" / reminder due times.
2. **Evidence first, model last.** Gather sources (notes, WM, SM, web) with ids, then call the model, then check. What has no source id may not appear as a fact.
3. **User text and retrieved memory are DATA.** A system-prompt sentence is not enough (see the review's spotlighting guidance). Implement **spotlighting** as the structural wrap:
   - Trusted retrieved facts: `[source_id] ...` wrappers.
   - Untrusted user / worker / web text: per-call random delimiter plus datamarking (whitespace replaced so it cannot look like an instruction).
   - Our own marker, not a foreign `tool_result_data` envelope.
4. **Attack notes go through the real chain.** A fixed corpus (EN/DE/HU plus harmless twins) must hit `POST /chat/text` / `ChatOrchestrator.process` with the real wrap. Do not mock away the orchestrator or JWT seam. A green unit test of `sanitize_user_input` is not the control.
5. **Two-tier output guards.**
   - Narrative (chat, Active Recall): unbacked numbers or extra claims get flagged (hypothesis / low confidence / unsupported), not necessarily withheld.
   - Action (create/cancel reminder, "saved" / "deleted" / "nothing in memory"): unbacked or partial results are rejected or reported honestly. Never a silent success.
6. **Timeouts tell the truth.** If work finished after the client gave up, do not tell the user it failed (e.g. proxy 10s vs backend 60s). Sibling of ffmpeg `timeout=60` and partial reminder delete.

### Later (Brain / demo polish — not this increment)

- AI provenance envelope on every AI output (`ai_generated`, `generated_by`, `requires_human_review`, `model_version`). Caveats are system-authored, not model-authored.
- PII replace (`[PERSON]`) before store.
- Recall by pattern (relations, failure causality, component), not shared wording. That is Brain, not Phase 5.
- Jarvis does not actuate. It explains, notes, and reminds. A human (or a later explicit skill) decides.

## Consequences

- The review checklist "structural wrap" should-item is this spotlighting recipe, not a longer blocklist.
- Coverage gate and mutation method stay. Spotlighting tests must go red if the wrap is stripped.
- Do not start an event-chain skill, 4-level memory, or a collaborator-memory client just to get these grounding properties.
