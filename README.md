# pa-voice-mvp

**Voice-first Personal Assistant MVP** (inspired by Jarvis)

A local-first, privacy-centric voice assistant that actively learns and maintains personal insights.

## Features (MVP)
- Voice interaction (STT + TTS)
- Working Memory + Semantic Memory with active consolidation
- Reminders, notes, and memory-augmented web search
- Multi-user support with proper isolation
- Browser UI with one big "Speak" button

## Tech Stack
- Backend: FastAPI
- Database: MongoDB Community (Docker) on Synology NAS — embeddings in documents; in-app ranking for Phase 1
- STT: faster-whisper
- TTS: Piper
- LLM (MVP): OpenAI (temporary) → later local Ollama
- Auth: JWT + bcrypt

## Getting Started (Development)

```bash
# Clone the repo
git clone https://github.com/ANY1-hub/pa-voice-mvp.git
cd pa-voice-mvp

# Create virtual environment (recommended: uv or venv)
uv venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows

# Install dependencies
uv pip install -e ".[dev]"

# Copy env and set MONGODB_URI (local Docker or NAS)
cp .env.example .env

# Run the app
uvicorn src.main:app --reload
```

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

## Development Standards
- Clean Code + Best Practices
- Tests with edge cases for every relevant function (pytest)
- Security by Design (aligned with ISO/IEC 27001 principles)
- Accessibility considerations (WCAG 2.2 / ISO 40500)
- Automated checks via Ruff, Black, mypy, pytest

## Project Memory
All major decisions are documented in the Project Memory (see internal docs or ask the maintainer).

## License
To be defined.
