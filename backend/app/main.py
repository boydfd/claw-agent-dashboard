"""FastAPI main entry point."""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .routers import agents, translate, settings, global_skills, status, versions, variables, templates, blueprints, agent_changes, search, security
from .services import version_db

# CORS origins — defaults to ["*"] for development.
# In production, set ALLOWED_ORIGINS to a comma-separated list of allowed origins.
_raw_origins = os.environ.get("ALLOWED_ORIGINS", "*").strip()
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",")] if _raw_origins != "*" else ["*"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — DB only; background tasks run in worker process
    await version_db.init_db()
    yield
    # Shutdown
    await version_db.close_db()


app = FastAPI(title="Agent Preview Tool", version="1.0.0", lifespan=lifespan)

# CORS — configurable via ALLOWED_ORIGINS env var
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
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
app.include_router(security.router, prefix="/api")

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
