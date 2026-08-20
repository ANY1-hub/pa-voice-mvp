# Memory Design (neuro-inspiriert)

**Inspiration:** Atkinson-Shiffrin Multi-Store Model + aktuelle Consolidation-Forschung  
**Ziel:** Der Agent sammelt aktiv Erkenntnisse und pflegt das Wissensarchiv (Jarvis-like).

## Aktuelle Architektur (MVP)

Zwei Memory-Ebenen:

### 1. Working Memory (kurzfristig)

- Session-Kontext und letzte Interaktionen
- Felder pro Eintrag:
  - `id` / Mongo ``_id`` (same UUID v4; unique index)
  - `user_id` (UUID-String)
  - `content`
  - `importance_score` (0.0 – 1.0)
  - `created_at`
  - `last_accessed`
  - `correlation_id` (optional chat-turn UUID)
- Speicherung in MongoDB-Collection `working_memory`
- Retrieval: nach `last_accessed` sortiert, optionaler Textfilter; abgelaufene Items (`expires_at`) werden ausgeblendet
- TTL: 48 Stunden (`expires_at` als BSON Date + Mongo TTL-Index)
- Vor dem Schreiben: Security-Check über `validate_memory_write`
- Chat-Turns (Importance 0.4) bleiben kurzfristig; dauerhafte Fakten werden zusätzlich in Semantic Memory extrahiert

### 2. Semantic Memory (langfristig)

- Dauerhafte User-Erkenntnisse: Präferenzen, Fakten, Muster, Wissensstand
- Felder pro Eintrag:
  - `id` / Mongo ``_id`` (same UUID v4; unique index)
  - `user_id` (UUID-String)
  - `content`
  - `importance_score` (0.0 – 1.0)
  - `entities_involved`
  - `created_at`
  - `last_accessed`
  - `embedding` (optional)
  - `language` (optional ISO-Tag des Originaltexts; keine Auto-Übersetzung)
- Speicherung in MongoDB-Collection `semantic_memory`
- Vor dem Schreiben: Security-Check über `validate_memory_write`

#### Retrieval-Strategie (aktuell)

1. **Mit Embeddings-Adapter:** Query wird eingebettet, Ranking per Cosine Similarity **in-memory** (ausreichend für MVP-Scale).
2. **Ohne Embeddings:** Case-insensitive Textsuche auf `content`, sortiert nach `importance_score`.

> Native MongoDB `$vectorSearch` ist in der Community Edition seit 2025/2026 möglich, erfordert aber zusätzlichen Search-Prozess (`mongot`) und Index-Erstellung. Für den aktuellen Local-First-/NAS-Setup (reines `mongo`-Image) bleibt die in-memory-Variante bewusst aktiv. Ein späterer Wechsel ist vorbereitet.

## Security

- Jeder Write geht durch `src/security/guardrails.py` → `validate_memory_write`
- Input-Validierung und Memory-Policy (Importance-Schwelle, erlaubte Sources)
- User-Isolation über `user_id` (UUID) in jeder Query
- Auth: JWT `user_id` (kein `X-User-Id` Header)

## Consolidation (MVP – Minimal, erweiterbar)

Hintergrund-Job (APScheduler, alle 60 Minuten):

1. **Promotion Working → Semantic**  
   Items aus Working Memory mit `importance_score >= 0.7` werden nach Semantic Memory übernommen und danach aus Working Memory gelöscht.

2. **SemanticMemory.consolidate()** (pro User):
   - `_cleanup_old_entries()`: Löscht Fakten mit `importance_score < 0.25` und `last_accessed` älter als 30 Tage.
   - `_deduplicate()`: Entfernt exakte Duplikate (normalisierter Content). Behält den Eintrag mit höchster Importance (bei Gleichstand den neueren).
   - `_link_entities()`: **Stub** – vorbereitet für Entity-Linking (ambitionierte Version).
   - `_detect_drift()`: **Stub** – vorbereitet für Preference-Drift-Erkennung (ambitionierte Version).

Die Struktur der Methode ist bewusst so gewählt, dass die ambitionierte Version später nur die Stubs füllen muss, ohne die öffentliche API oder den Scheduler zu ändern.

## Spätere Erweiterung (4-Level)

Geplant nach dem MVP:

- **Episodic Memory** – konkrete Ereignisse / Episoden
- **Perceptual Memory** – sensorische / multimodale Eindrücke

## Relevante Dateien

| Bereich              | Datei                                      |
|----------------------|--------------------------------------------|
| Working Memory       | `src/memory/working_memory.py`             |
| Semantic Memory      | `src/memory/semantic_memory.py`            |
| Models               | `src/models/memory.py`                     |
| Security             | `src/security/guardrails.py`, `memory_policy.py`, `input_validator.py` |
| API                  | `src/api/routes/memory.py`                 |
| Scheduler / Job      | `src/tasks/scheduler.py`                   |
| Embeddings           | `src/services/embeddings/`                 |
| Tests (Consolidation)| `tests/test_consolidation.py`              |
