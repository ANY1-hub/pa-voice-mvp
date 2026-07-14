# Memory Design (neuro-inspiriert)

**Inspiration:** Atkinson-Shiffrin Multi-Store Model + aktuelle Consolidation-Forschung.

**Working Memory (MVP Level 1):**
- Kurze Session-Kontext + letzte N Interaktionen
- TTL + Importance Scoring
- Schnelle In-Memory oder kurze Mongo-Docs

**Semantic Memory (MVP Level 2):**
- Langfristige User-Erkenntnisse: Präferenzen, Wissensstand, Fakten, Muster
- Mit Zeitstempel (für Drift-Erkennung)
- Importance Score
- Vector Embeddings + MongoDB Vector Search für Retrieval
- Aktive Consolidation: Hintergrund-Job (z.B. Session-Ende oder täglich) zum Verlinken, Aufräumen, Widersprüche finden (wie "Lint" im Karpathy-Ansatz)

**Später (4-Level):** Episodic + Perceptual ergänzen.

**Ziel:** Der Agent sammelt aktiv Erkenntnisse und pflegt das Wissensarchiv (Jarvis-like).
