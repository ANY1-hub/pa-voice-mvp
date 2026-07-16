from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from src.tasks.scheduler import start_scheduler, stop_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect DB, start scheduler
    start_scheduler()
    yield
    # Shutdown: disconnect DB, stop scheduler
    stop_scheduler()

app = FastAPI(title="Jarvis MVP Backend", lifespan=lifespan)

# Allow CORS for vanilla HTML frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Jarvis backend is running"}