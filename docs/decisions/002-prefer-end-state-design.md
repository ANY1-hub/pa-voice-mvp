# Decision: Prefer the end-state design

**Date:** 2026-08-20  
**Status:** Accepted  
**Motto:** No shortcuts we would have to undo.

## Context

The project is still greenfield. Nothing is in production. There is no irreplaceable live data. Compatibility layers for “legacy” shapes (ObjectId vs UUID, sparse unique indexes, dual identifiers) cost more than a clean cut, because they would have to be ripped out before the north star.

## Decision

Prefer the **end-state design** over incremental compatibility.

- If a stronger change is needed to reach the goal, take it now.
- Do not ship shims, dual IDs, or “we’ll migrate later” paths that can bite us at the end.
- Wipe and rebuild local/test databases when the target shape changes.

## Consequences

- Agents and humans optimize for the target architecture, not for hypothetical production.
- Refactors (IDs, memory, routing) may be larger in one step and smaller over the life of the project.
