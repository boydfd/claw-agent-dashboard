"""FastAPI main entry point."""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .config import ES_URL
from .routers import agents, translate, settings, global_skills, status, versions, variables, templates, blueprints, agent_changes, search
from .services import version_db, change_detector, blueprint_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await version_db.init_db()
    await blueprint_service.initialize_blueprint_dirs()
    await change_detector.start_detector(interval=30)
    # Start session indexer if ES is configured
    _session_indexer = None
    if ES_URL:
        from .services.session_indexer import SessionIndexer
        _session_indexer = SessionIndexer()
        await _session_indexer.start()
    yield
    # Shutdown
    if _session_indexer:
        await _session_indexer.stop()
    await change_detector.stop_detector()
    await version_db.close_db()


app = FastAPI(title="Agent Preview Tool", version="1.0.0", lifespan=lifespan)

# CORS for dev mode
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(agents.router, prefix="/api")
app.include_router(translate.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(status.router, prefix="/api")
app.include_router(global_skills.router, prefix="/api")
app.include_router(versions.router, prefix="/api")
app.include_router(variables.router, prefix="/api")
app.include_router(templates.router, prefix="/api")
app.include_router(blueprints.router, prefix="/api")
app.include_router(agent_changes.router, prefix="/api")
app.include_router(search.router, prefix="/api/search")

# Serve frontend static files (production build)
STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the SPA index.html for all non-API routes."""
        file_path = STATIC_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(STATIC_DIR / "index.html"))
