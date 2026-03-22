"""Blueprints API — CRUD, file management, derive, sync."""
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from ..services import blueprint_service, version_db

router = APIRouter(prefix="/blueprints", tags=["blueprints"])


class BlueprintCreate(BaseModel):
    name: str
    description: str = ""
    source_agent_id: int | None = None
    exclude_patterns: list[str] | None = None


class BlueprintUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class BlueprintFileCreate(BaseModel):
    file_path: str
    content: str


class BlueprintFileUpdate(BaseModel):
    content: str


class DeriveRequest(BaseModel):
    agent_name: str
    variables: dict[str, str] | None = None
    create_openclaw_agent: bool = True

    @field_validator('agent_name')
    @classmethod
    def validate_agent_name(cls, v):
        if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9_-]*$', v):
            raise ValueError('Agent name must be alphanumeric (hyphens and underscores allowed, must start with letter/number)')
        if len(v) > 64:
            raise ValueError('Agent name must be 64 characters or fewer')
        return v


# --- Blueprint CRUD ---

@router.get("")
async def list_blueprints():
    blueprints = await blueprint_service.list_blueprints()
    # Enrich with file and variable counts
    enriched = []
    for bp in blueprints:
        files = await blueprint_service.list_blueprint_files(bp["id"])
        variables = await blueprint_service.get_blueprint_variables(bp["id"])
        enriched.append({
            **bp,
            "file_count": len(files),
            "variable_count": len(variables),
        })
    return enriched


@router.post("")
async def create_blueprint(body: BlueprintCreate):
    """Create a new blueprint, optionally importing files from an existing agent."""
    try:
        return await blueprint_service.create_blueprint(
            name=body.name,
            description=body.description,
            source_agent_id=body.source_agent_id,
            exclude_patterns=body.exclude_patterns,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(409, f"Blueprint '{body.name}' already exists")
        raise HTTPException(500, str(e))


# ---------------------------------------------------------------------------
# Pending Changes (Filesystem Sync) — global route MUST be before /{blueprint_id}
# ---------------------------------------------------------------------------

@router.get("/pending-changes")
async def get_all_pending_changes():
    """Global pending changes summary across all blueprints."""
    summary = await version_db.get_pending_changes_summary()
    total = sum(s["pending_count"] for s in summary)
    return {"blueprints": summary, "total_pending": total}


@router.get("/{blueprint_id}")
async def get_blueprint(blueprint_id: int):
    bp = await blueprint_service.get_blueprint(blueprint_id)
    if not bp:
        raise HTTPException(404, "Blueprint not found")

    # Enrich with files and variables
    files = await blueprint_service.list_blueprint_files(blueprint_id)
    variables = await blueprint_service.get_blueprint_variables(blueprint_id)
    derivations = await version_db.list_derivations(blueprint_id)

    return {
        **bp,
        "files": files,
        "referenced_variables": variables,
        "derivations": derivations,
    }


@router.put("/{blueprint_id}")
async def update_blueprint(blueprint_id: int, body: BlueprintUpdate):
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    bp = await blueprint_service.update_blueprint(blueprint_id, **fields)
    if not bp:
        raise HTTPException(404, "Blueprint not found")
    return bp


@router.delete("/{blueprint_id}")
async def delete_blueprint(blueprint_id: int, confirm: bool = False):
    if confirm:
        success = await blueprint_service.force_delete_blueprint(blueprint_id)
        if not success:
            raise HTTPException(404, "Blueprint not found")
        return {"deleted": True}
    result = await blueprint_service.delete_blueprint(blueprint_id)
    return result


# --- Blueprint Files ---

@router.get("/{blueprint_id}/files")
async def list_blueprint_files(blueprint_id: int):
    try:
        return await blueprint_service.list_blueprint_files(blueprint_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/{blueprint_id}/files")
async def add_blueprint_file(blueprint_id: int, body: BlueprintFileCreate):
    try:
        return await blueprint_service.add_blueprint_file(
            blueprint_id, body.file_path, body.content
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(400, "File already exists in this blueprint")
        raise HTTPException(500, str(e))


# ---------------------------------------------------------------------------
# Version History — MUST be before greedy {file_path:path} GET route
# ---------------------------------------------------------------------------

@router.get("/{blueprint_id}/files/{file_path:path}/versions")
async def get_blueprint_file_versions(blueprint_id: int, file_path: str, limit: int = 20, offset: int = 0):
    """Get version history for a blueprint file."""
    bp = await blueprint_service.get_blueprint(blueprint_id)
    if not bp:
        raise HTTPException(404, "Blueprint not found")
    versions, total = await version_db.get_versions(bp["agent_id"], file_path, limit=limit, offset=offset)
    return {"versions": versions, "total": total}


@router.get("/{blueprint_id}/files/{file_path:path}/versions/{version_num}")
async def get_blueprint_file_version(blueprint_id: int, file_path: str, version_num: int):
    """Get a specific version of a blueprint file (includes content)."""
    bp = await blueprint_service.get_blueprint(blueprint_id)
    if not bp:
        raise HTTPException(404, "Blueprint not found")
    versions, _ = await version_db.get_versions(bp["agent_id"], file_path)
    version_meta = next((v for v in versions if v["version_num"] == version_num), None)
    if not version_meta:
        raise HTTPException(404, "Version not found")
    # Fetch full version record including content
    version = await version_db.get_version(version_meta["id"])
    return version


@router.post("/{blueprint_id}/files/{file_path:path}/restore/{version_num}")
async def restore_blueprint_file_version(blueprint_id: int, file_path: str, version_num: int):
    """Restore a blueprint file to a specific version."""
    bp = await blueprint_service.get_blueprint(blueprint_id)
    if not bp:
        raise HTTPException(404, "Blueprint not found")

    versions, _ = await version_db.get_versions(bp["agent_id"], file_path)
    version_meta = next((v for v in versions if v["version_num"] == version_num), None)
    if not version_meta:
        raise HTTPException(404, "Version not found")
    # Fetch full version record including content
    version = await version_db.get_version(version_meta["id"])

    # Update DB template
    template = await version_db.get_template_by_path(bp["agent_id"], file_path)
    if template:
        await version_db.update_template(template["id"], version["content"])

    # Write to disk
    from pathlib import Path
    from ..config import BLUEPRINTS_DIR
    disk_file = Path(BLUEPRINTS_DIR) / bp["name"] / file_path
    disk_file.parent.mkdir(parents=True, exist_ok=True)
    disk_file.write_text(version["content"], encoding="utf-8")

    # Clear pending change
    await version_db.delete_pending_change_by_file(blueprint_id, file_path)

    # Sync to derived agents
    await blueprint_service._sync_file_to_derivations(bp, file_path, version["content"])

    # Create new version record for the restore
    content_hash = version_db.compute_hash(version["content"])
    await version_db.create_version(
        agent_id=bp["agent_id"], file_path=file_path,
        content=version["content"], content_hash=content_hash,
        source="dashboard", commit_msg=f"Restored to version {version_num}",
    )

    return {"restored": True, "version_num": version_num, "file_path": file_path}


# --- Blueprint File CRUD (greedy {file_path:path} routes) ---

@router.get("/{blueprint_id}/files/{file_path:path}")
async def get_blueprint_file(blueprint_id: int, file_path: str):
    template = await blueprint_service.get_blueprint_file(blueprint_id, file_path)
    if not template:
        raise HTTPException(404, "File not found")
    return template


@router.put("/{blueprint_id}/files/{file_path:path}")
async def update_blueprint_file(blueprint_id: int, file_path: str, body: BlueprintFileUpdate):
    try:
        return await blueprint_service.update_blueprint_file(
            blueprint_id, file_path, body.content
        )
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.delete("/{blueprint_id}/files/{file_path:path}")
async def delete_blueprint_file(blueprint_id: int, file_path: str):
    success = await blueprint_service.delete_blueprint_file(blueprint_id, file_path)
    if not success:
        raise HTTPException(404, "File not found")
    return {"deleted": True}


# --- Variables ---

@router.get("/{blueprint_id}/variables")
async def list_blueprint_variables(blueprint_id: int):
    return await blueprint_service.get_blueprint_variables(blueprint_id)


# ---------------------------------------------------------------------------
# Pending Changes — per-blueprint
# ---------------------------------------------------------------------------

@router.get("/{blueprint_id}/pending-changes")
async def get_blueprint_pending_changes(blueprint_id: int):
    """Detailed pending changes for a specific blueprint."""
    bp = await blueprint_service.get_blueprint(blueprint_id)
    if not bp:
        raise HTTPException(404, "Blueprint not found")
    changes = await version_db.list_pending_changes(blueprint_id)
    return {
        "blueprint_id": blueprint_id,
        "blueprint_name": bp["name"],
        "changes": changes,
    }


@router.post("/{blueprint_id}/pending-changes/{change_id}/accept")
async def accept_change(blueprint_id: int, change_id: int):
    """Accept a single file change."""
    try:
        result = await blueprint_service.accept_pending_change(change_id)
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/{blueprint_id}/pending-changes/{change_id}/reject")
async def reject_change(blueprint_id: int, change_id: int):
    """Reject a single file change — revert file on disk."""
    try:
        result = await blueprint_service.reject_pending_change(change_id)
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/{blueprint_id}/pending-changes/accept-all")
async def accept_all_changes(blueprint_id: int):
    """Accept all pending changes for a blueprint (auto-accept API)."""
    bp = await blueprint_service.get_blueprint(blueprint_id)
    if not bp:
        raise HTTPException(404, "Blueprint not found")
    try:
        result = await blueprint_service.accept_all_pending_changes(blueprint_id)
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


# --- Derivations ---

@router.get("/{blueprint_id}/derivations")
async def list_derivations(blueprint_id: int):
    return await version_db.list_derivations(blueprint_id)


@router.post("/{blueprint_id}/derive")
async def derive_agent(blueprint_id: int, body: DeriveRequest):
    try:
        return await blueprint_service.derive_agent(
            blueprint_id=blueprint_id,
            agent_name=body.agent_name,
            variables=body.variables,
            create_openclaw_agent=body.create_openclaw_agent,
        )
    except ValueError as e:
        if "already exists" in str(e):
            raise HTTPException(409, str(e))
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))
