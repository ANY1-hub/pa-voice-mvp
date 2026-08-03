# pa-voice-mvp

**Voice-first Personal Assistant MVP** (inspired by Jarvis)

A local-first, privacy-centric voice assistant that actively learns and maintains personal insights.

## Status (2026-08-03)

| Phase | Status |
|-------|--------|
| 0 Setup & Foundation | ✅ |
| 1 Memory Core | ✅ |
| 2 Auth + Multi-User | ✅ |
| 3 Voice Pipeline MVP | ✅ |
| **4 Skills** | **✅ closed** |
| 5 Polish & Demo | ← current |

## Features (MVP scope)
- Voice interaction (STT + TTS) with visible transcript and reply
- Working Memory + Semantic Memory with active consolidation
- Multi-user isolation (JWT)
- Multi-language TTS voices (en / de / hu)
- Browser UI with one big "Speak" button + text fallback
- Skills: Notes, Reminders, memory-augmented Web Search (DuckDuckGo), Active Recall
- Minimal SuperUser bootstrap + admin endpoints (Phase 5)

**Not in MVP (post-MVP):** streaming, local LLM, GDPR data-rights UI, 4-level memory, Home Assistant, complex roles matrix.

## Tech Stack
- Backend: FastAPI
- Database: MongoDB Community (Docker) on Synology NAS — embeddings in documents; in-app ranking for Phase 1
- STT: faster-whisper
- TTS: Piper (multi-voice)
- LLM (MVP): OpenAI (temporary) → later local / Adapter Pattern
- Auth: JWT + bcrypt

## Authentication

JWT + bcrypt. Multi-user isolation enforced on every memory and chat route.

### Auth Endpoints

| Method | Path                      | Description                  |
|--------|---------------------------|------------------------------|
| POST   | `/api/v1/auth/register`   | Register (email + password). First user becomes SuperUser |
| POST   | `/api/v1/auth/login`      | Returns access token         |
| GET    | `/api/v1/auth/me`         | Current user (requires token)|

### Admin Endpoints (SuperUser only)

| Method | Path                           | Description                          |
|--------|--------------------------------|--------------------------------------|
| GET    | `/api/v1/admin/users`          | List users                           |
| POST   | `/api/v1/admin/users`          | Create user (optional `is_superuser`)|
| PATCH  | `/api/v1/admin/users/{user_id}`| Update `is_active` / `is_superuser`  |

### Chat Endpoints (Phase 3)

| Method | Path                      | Description                                      |
|--------|---------------------------|--------------------------------------------------|
| POST   | `/api/v1/chat/text`       | Text message → Memory context → LLM → TTS        |
| POST   | `/api/v1/chat/voice`      | Audio upload → STT → Memory → LLM → TTS          |

Both require `Authorization: Bearer <token>`.

Response shape:

```json
{
  "transcript": "what the user said",
  "response": "Jarvis reply",
  "audio_base64": "..."
}
```

### Token usage

```http
Authorization: Bearer <access_token>
```

- Lifetime: **24 hours**
- User-ID is always a server-generated UUID v4 (client cannot supply one)
- Email uniqueness is enforced by a MongoDB unique index created at startup
- Memory routes are fully isolated via dependency injection
  → see `docs/decisions/001-dependency-injection-memory.md`

### Skill Vocabulary

Trigger phrases (EN / DE / HU) for Notes, Reminders, Web Search and Active Recall are documented in **[docs/user-guide.md](docs/user-guide.md)**.

## Getting Started (Development)

```bash
# Clone the repo
git clone https://github.com/ANY1-hub/pa-voice-mvp.git
cd pa-voice-mvp

# Create virtual environment (recommended: uv or venv)
uv venv .venv
source .venv/bin/activate   # or .venv\\Scripts\\activate on Windows

# Install dependencies
uv pip install -e ".[dev]"

# Copy env and set MONGODB_URI (local Docker or NAS)
cp .env.example .env

# Run the backend
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend (Voice UI)

```bash
# Terminal 2 – from project root
cd frontend
python -m http.server 5500
```

Open http://localhost:5500
Login with a registered user, then use the big Speak button (or the text input).

Backend must be running on port 8000.
Piper voice models must be present (see [docs/piper-voice-setup.md](docs/piper-voice-setup.md)).

### MongoDB

| Setup | Docs |
|-------|------|
| Local Docker (mongo + app) | `docker-compose.yml` |
| **Synology DS925+ (recommended for shared LAN DB)** | **[docs/nas-mongodb-setup.md](docs/nas-mongodb-setup.md)** + template `deploy/nas/docker-compose.mongodb.yml` |

Example NAS URI in `.env`:

```env
MONGODB_URI=mongodb://pa_admin:<PASSWORD>@<NAS_IP>:27017/?authSource=admin
MONGODB_DB_NAME=jarvis_db
```

### Piper TTS Voice Model

Piper requires local voice models (not included in the repo).
See **[docs/piper-voice-setup.md](docs/piper-voice-setup.md)** for download instructions (Windows + macOS/Linux).

Optional per-language override in `.env`:

```env
PIPER_VOICE_EN=voice_models/piper/en_US-amy-medium.onnx
PIPER_VOICE_DE=voice_models/piper/de_DE-thorsten-medium.onnx
PIPER_VOICE_HU=voice_models/piper/hu_HU-anna-medium.onnx
```

## Development Standards
- Clean Code + Best Practices
- Tests with edge cases for every relevant function (pytest)
- Security by Design (aligned with ISO/IEC 27001 principles)
- Accessibility considerations (WCAG 2.2 / ISO 40500)
- Automated checks via Ruff, Black, pytest (CI coverage ≥ 80%)

## Project Memory
All major decisions are documented in the Project Memory (see internal docs or ask the maintainer).

## License
To be defined.
