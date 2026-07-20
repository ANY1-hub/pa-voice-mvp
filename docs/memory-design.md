# Memory Design (neuro-inspiriert)

**Inspiration:** Atkinson-Shiffrin Multi-Store Model + aktuelle Consolidation-Forschung
**Ziel:** Der Agent sammelt aktiv Erkenntnisse und pflegt das Wissensarchiv (Jarvis-like).

## Aktuelle Architektur (MVP)

Zwei Memory-Ebenen:

### 1. Working Memory (kurzfristig)

- Session-Kontext und letzte Interaktionen
- Felder pro Eintrag:
  - `user_id`
  - `content`
  - `importance_score` (0.0 – 1.0)
  - `created_at`
  - `last_accessed`
- Speicherung in MongoDB-Collection `working_memory`
- Retrieval: nach `last_accessed` sortiert, optionaler Textfilter
- Vor dem Schreiben: Security-Check über `validate_memory_write`

### 2. Semantic Memory (langfristig)

- Dauerhafte User-Erkenntnisse: Präferenzen, Fakten, Muster, Wissensstand
- Felder pro Eintrag:
  - `user_id`
  - `content`
  - `importance_score` (0.0 – 1.0)
  - `entities_involved`
  - `created_at`
  - `last_accessed`
  - `embedding` (optional)
- Speicherung in MongoDB-Collection `semantic_memory`
- Vor dem Schreiben: Security-Check über `validate_memory_write`

#### Retrieval-Strategie (aktuell)

1. **Mit Embeddings-Adapter:** Query wird eingebettet, Ranking per Cosine Similarity (in-memory, ausreichend für MVP)
2. **Ohne Embeddings:** Case-insensitive Textsuche auf `content`, sortiert nach `importance_score`

> Hinweis: Native MongoDB Vector Search ist für später vorgesehen. Im MVP bleibt die Ähnlichkeitssuche bewusst in Python.

## Security

- Jeder Write geht durch `src/security/guardrails.py` → `validate_memory_write`
- Input-Validierung und Memory-Policy (Importance-Schwelle, erlaubte Sources)
- User-Isolation über `user_id` in jeder Query

## Consolidation (geplant)

Hintergrund-Job (APScheduler) für:

- Verlinken verwandter Fakten
- Widersprüche erkennen
- Preference-Drift erkennen (über Timestamps + Importance)
- Aufräumen veralteter / unwichtiger Einträge

Aktueller Stand: Methode `SemanticMemory.consolidate()` existiert als Stub (`TODO`).

## Spätere Erweiterung (4-Level)

Geplant nach dem MVP:

- **Episodic Memory** – konkrete Ereignisse / Episoden
- **Perceptual Memory** – sensorische / multimodale Eindrücke

## Relevante Dateien

| Bereich | Datei |
|---------|-------|
| Working Memory | `src/memory/working_memory.py` |
| Semantic Memory | `src/memory/semantic_memory.py` |
| Models | `src/models/memory.py` |
| Security | `src/security/guardrails.py`, `memory_policy.py`, `input_validator.py` |
| API | `src/api/routes/memory.py` |
| Embeddings | `src/services/embeddings/` |
