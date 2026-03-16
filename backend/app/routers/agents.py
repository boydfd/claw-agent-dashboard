"""Agent-related API routes."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..services import scanner, file_service, version_service, version_db
from ..services.translate import translation_exists

router = APIRouter(tags=["agents"])


@router.get("/agents")
async def list_agents():
    """List all discovered agents."""
    agents = scanner.list_agents()
    # Attach database ID for each agent
    for agent in agents:
        agent["id"] = await version_db.get_or_create_agent(agent["name"])
    return agents


@router.get("/agents/{agent_name}/files")
async def get_agent_files(agent_name: str):
    """List core files for an agent."""
    files = file_service.list_agent_files(agent_name)
    # Annotate with translation status
    for f in files:
        f["has_translation"] = translation_exists(agent_name, f["path"])
    return files


@router.get("/agents/{agent_name}/memory")
async def get_memory_files(agent_name: str):
    """List memory files for an agent."""
    files = file_service.list_memory_files(agent_name)
    for f in files:
        f["has_translation"] = translation_exists(agent_name, f["path"])
    return files


@router.get("/agents/{agent_name}/other-files")
async def get_other_files(agent_name: str):
    """List other files/directories in agent root."""
    return file_service.list_other_files(agent_name)


@router.get("/agents/{agent_name}/skills")
async def get_agent_skills(agent_name: str):
    """List skills for an agent."""
    return file_service.list_agent_skills(agent_name)


@router.get("/agents/{agent_name}/skill-files/{skill_name}")
async def get_skill_files(agent_name: str, skill_name: str):
    """List all files in a skill directory."""
    files = file_service.list_skill_files(agent_name, skill_name)
    return files


@router.get("/agents/{agent_name}/file")
async def get_file_content(agent_name: str, path: str = Query(..., description="Relative file path")):
    """Read a specific file's content."""
    result = file_service.read_file(agent_name, path)
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
