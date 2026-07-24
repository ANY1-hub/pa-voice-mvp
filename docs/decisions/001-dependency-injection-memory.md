# Decision: Dependency Injection for Memory & Auth Repositories

**Date:** 2026-07-24  
**Status:** Accepted  
**Context:** Phase 2 – Auth + Multi-User + CI stabilisation

## Decision

`WorkingMemory`, `SemanticMemory` and `UserRepository` receive their MongoDB collection (or `None`) via constructor injection.  
The global `db_client` remains exclusively in the connection layer (`src/db/mongodb.py`) and the application lifespan.

## Why now

- Removes event-loop and global-state leakage problems that currently break CI.
- Prepares the planned post-MVP migration to Temporal Knowledge Graphs (Zep / Graphiti) + hybrid retrieval.
- Keeps the architecture consistent with the already decided Adapter Pattern (LLM + Embeddings).
- Enables clean isolation for future multi-agent and permission-scoped memory scenarios.

## Consequences

- Slightly more wiring in `deps.py` and the route handlers.
- Unit tests can pass `collection=None` and no longer need global state resets.
- Future backend swaps (graph store, different DB driver) only affect the factories, not the business logic inside the memory classes.
