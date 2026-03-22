"""Agent-related API routes."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..services import scanner, file_service, version_service, version_db, template_service
from ..services.translate import translation_exists

router = APIRouter(tags=["agents"])


@router.get("/agents")
async def list_agents():
    """List all discovered agents."""
    agents = await scanner.list_agents_async()
    # Attach database ID and blueprint name for each agent
    for agent in agents:
        agent["id"] = await version_db.get_or_create_agent(agent["name"])
        # Look up blueprint derivation
        derivation = await version_db.get_derivation_by_agent_id(agent["id"])
        if derivation:
            bp = await version_db.get_blueprint(derivation["blueprint_id"])
            agent["blueprint_name"] = bp["name"] if bp else None
        else:
            agent["blueprint_name"] = None
    return agents


@router.get("/agents/{agent_name}/files")
async def get_agent_files(agent_name: str):
    """List core files for an agent."""
    files = await file_service.list_agent_files_async(agent_name)
    # Annotate with translation status
    for f in files:
        f["has_translation"] = translation_exists(agent_name, f["path"])
    return files


@router.get("/agents/{agent_name}/memory")
async def get_memory_files(agent_name: str):
    """List memory files for an agent."""
    files = await file_service.list_memory_files_async(agent_name)
    for f in files:
        f["has_translation"] = translation_exists(agent_name, f["path"])
    return files


@router.get("/agents/{agent_name}/other-files")
async def get_other_files(agent_name: str):
    """List other files/directories in agent root."""
    return await file_service.list_other_files_async(agent_name)


@router.get("/agents/{agent_name}/skills")
async def get_agent_skills(agent_name: str):
    """List skills for an agent."""
    return await file_service.list_agent_skills_async(agent_name)


@router.get("/agents/{agent_name}/skill-files/{skill_name}")
async def get_skill_files(agent_name: str, skill_name: str):
    """List all files in a skill directory."""
    files = await file_service.list_skill_files_async(agent_name, skill_name)
    return files


@router.get("/agents/{agent_name}/file")
async def get_file_content(agent_name: str, path: str = Query(..., description="Relative file path")):
    """Read a specific file's content."""
    result = await file_service.read_file_async(agent_name, path)
    if result is None:
        raise HTTPException(status_code=404, detail="File not found")
    result["has_translation"] = translation_exists(agent_name, path)
    return result


class SaveFileRequest(BaseModel):
    content: str
    commit_msg: str | None = None


@router.put("/agents/{agent_name}/file")
async def save_file(agent_name: str, path: str = Query(...), body: SaveFileRequest = ...):
    """Write content back to the original file with version tracking."""
    try:
        version = await version_service.save_file_with_version(
            agent_name, path, body.content, body.commit_msg
        )
        # Auto-override: if this agent is derived, mark file as overridden
        agent_id = await version_db.get_or_create_agent(agent_name)
        derivation = await version_db.get_derivation_by_agent_id(agent_id)
        if derivation:
            await version_db.add_override(derivation["id"], path)
        return {
            "path": path,
            "name": path.split("/")[-1],
            "saved": True,
            "version_num": version["version_num"],
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Save failed: {str(e)}")


@router.post("/agents/{agent_name}/file/detach")
async def detach_file_from_blueprint(agent_name: str, path: str = Query(...)):
    """Detach a file from its blueprint by creating the agent's own template copy."""
    db = await version_db.get_db()
    cursor = await db.execute(
        "SELECT id FROM agents WHERE workspace_name = ?", (agent_name,)
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(404, "Agent not found")
    try:
        template = await template_service.detach_from_blueprint(row["id"], path)
        return {"template_id": template["id"], "agent_id": row["id"]}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/agents/{agent_name}/file/restore-blueprint")
async def restore_file_to_blueprint(agent_name: str, path: str = Query(...)):
    """Restore a file to its blueprint version, undoing the detach."""
    db = await version_db.get_db()
    cursor = await db.execute(
        "SELECT id FROM agents WHERE workspace_name = ?", (agent_name,)
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(404, "Agent not found")
    try:
        result = await template_service.restore_to_blueprint(row["id"], path)
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/agents/{agent_name}/derivation-status")
async def get_derivation_status(agent_name: str):
    """Get blueprint derivation info for an agent."""
    from ..services import blueprint_service
    # Use read-only lookup — do NOT create an agent record for a status query
    db = await version_db.get_db()
    cursor = await db.execute(
        "SELECT id FROM agents WHERE workspace_name = ?", (agent_name,)
    )
    row = await cursor.fetchone()
    if not row:
        return {"is_derived": False}
    status = await blueprint_service.get_derivation_status(row["id"])
    if not status:
        return {"is_derived": False}
    return status


