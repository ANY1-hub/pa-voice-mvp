"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.api.routes.admin import router as admin_router
from src.api.routes.auth import router as auth_router
from src.api.routes.chat import router as chat_router
from src.api.routes.memory import router as memory_router
from src.api.routes.notes import router as notes_router
from src.api.routes.reminders import router as reminders_router
from src.api.routes.skills import router as skills_router
from src.api.voice_upload_limit import VoiceUploadLimitMiddleware
from src.db.mongodb import close_mongo_connection, connect_to_mongo, db_client
from src.tasks.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: connect DB + start background jobs on startup.

    Args:
        app: FastAPI application instance (unused, required by signature).
    """
    await connect_to_mongo()
    start_scheduler()
    yield
    stop_scheduler()
    await close_mongo_connection()


app = FastAPI(title="Jarvis MVP Backend", lifespan=lifespan)

# Inner: 413 oversized /chat/voice before parse. Outer: CORS (last add).
app.add_middleware(VoiceUploadLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(admin_router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(memory_router, prefix="/api/v1/memory", tags=["memory"])
app.include_router(chat_router, prefix="/api/v1/chat", tags=["chat"])
app.include_router(skills_router, prefix="/api/v1/skills", tags=["skills"])
app.include_router(notes_router, prefix="/api/v1/notes", tags=["notes"])
app.include_router(reminders_router, prefix="/api/v1/reminders", tags=["reminders"])


@app.get("/health")
async def health_check():
    """Readiness probe: cheap Mongo ping before claiming ok.

    Returns:
        200 + ``status: ok`` when Mongo answers ``ping``; otherwise 503 with an
        honest non-ok status. Body never includes secrets or connection URIs.
    """
    client = db_client.client
    if client is None:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unavailable",
                "message": "Database not connected",
            },
        )
    try:
        await client.admin.command("ping")
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unavailable",
                "message": "Database unreachable",
            },
        )
    return {"status": "ok", "message": "Jarvis backend is running"}


class FrontendStaticFiles(StaticFiles):
    """Do not cache HTML/JS/CSS; stale Voice UI JS shows the wrong auth form."""

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        lowered = path.lower()
        if lowered.endswith((".js", ".css", ".html")) or lowered in {
            "",
            ".",
            "index.html",
        }:
            response.headers["Cache-Control"] = "no-store"
        return response


FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
# Last: API routes stay in front. Same origin as /api/v1 — empty DB bootstrap
# does not depend on a second static server.
app.mount(
    "/",
    FrontendStaticFiles(directory=FRONTEND_DIR, html=True),
    name="frontend",
)
