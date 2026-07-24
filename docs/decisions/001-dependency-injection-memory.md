# Decision: Dependency Injection for Memory & Auth Repositories

**Date:** 2026-07-24  
**Status:** Accepted  
**Context:** Phase 2 – Auth + Multi-User + CI-Stabilisierung

## Decision
WorkingMemory, SemanticMemory und UserRepository erhalten ihre MongoDB-Collection 
(oder `None`) per Konstruktor-Injection. Der globale `db_client` bleibt ausschließlich 
in der Connection-Schicht (`src/db/mongodb.py`) und im Lifespan.

## Why now
- Eliminiert Event-Loop- und State-Leak-Probleme in den Tests.
- Bereitet den geplanten Wechsel auf Temporal Knowledge Graphs (Zep/Graphiti) vor.
- Hält die Architektur konsistent mit dem bereits beschlossenen Adapter-Pattern 
  (LLM + Embeddings).
- Ermöglicht saubere Isolation für zukünftige Multi-Agent- und Permission-Szenarien.

## Consequences
- Etwas mehr Wiring in `deps.py` und den Routes.
- Unit-Tests können `collection=None` übergeben und brauchen keinen globalen Reset mehr.
- Spätere Backend-Wechsel (Graph, andere DB) betreffen nur die Factories, nicht die 
  Business-Logik der Memory-Klassen.
