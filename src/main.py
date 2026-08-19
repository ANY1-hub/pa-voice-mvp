"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.admin import router as admin_router
from src.api.routes.auth import router as auth_router
from src.api.routes.chat import router as chat_router
from src.api.routes.memory import router as memory_router
from src.db.mongodb import close_mongo_connection, connect_to_mongo
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

# Allow CORS for vanilla HTML frontend
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


@app.get("/health")
async def health_check():
    """Simple health check endpoint.

    Returns:
        Dict with ``status`` and a short message.
    """
    return {"status": "ok", "message": "Jarvis backend is running"}
