# pa-voice-mvp

MVP für einen Voice-basierten Personal Assistant (wie Jarvis light).

**Ziel:** Out-of-the-box nutzbar für nicht-technische User. Voice-first, lernt aktiv Erkenntnisse über den User (Präferenzen, Wissensstand, Muster), speichert mit Zeitstempeln und nutzt das für natürliche, personalisierte Interaktion.

**Memory:** Start mit Working Memory + Semantic Memory (neuro-inspiriert: Working wie kurzer Kontext/TTL, Semantic als langfristiges Wissensarchiv mit Importance, Zeitstempeln und aktiver Consolidation).

**Tech Stack (Local-First):**
- STT: faster-whisper
- LLM: Ollama
- TTS: Piper
- Backend: FastAPI
- DB: MongoDB (Community mit Vector Search) auf Synology NAS
- Auth: JWT
- UI: Einfache Browser-App mit Speak-Button

**Zeitrahmen:** 8 Wochen bis Mitte September 2026 (Master's Projekt Referenz)

## Quick Start (später)
```bash
docker compose up
```

Repo für Master's Projekt an der Masterschool of Information Technology, Berlin.