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
- Database: MongoDB (with Vector Search) on Synology NAS
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

# Run the app (later)
uvicorn src.main:app --reload
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
