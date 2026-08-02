import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.config import settings
from app.db.database import init_db
from app.api.v1.sessions import router as sessions_router
from app.api.v1.sessions import websocket_session_stream

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    await init_db()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(sessions_router, prefix=settings.API_V1_STR)

# Register websocket under /ws/sessions/{session_id} directly if needed
app.add_api_websocket_route("/ws/sessions/{session_id}", websocket_session_stream)

@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok", "version": settings.VERSION}

# Mount static frontend directory if present
static_dir = os.path.join(os.path.dirname(__file__), "app", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", tags=["System"])
def read_root():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {
        "message": "Computer Use Agent Backend API is operational.",
        "docs": "/docs",
        "version": settings.VERSION
    }
