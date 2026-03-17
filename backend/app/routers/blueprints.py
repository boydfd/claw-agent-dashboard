"""Blueprints API — CRUD, file management, derive, sync."""
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from ..services import blueprint_service, version_db

router = APIRouter(prefix="/blueprints", tags=["blueprints"])


class BlueprintCreate(BaseModel):
    name: str
    description: str = ""


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
    try:
        return await blueprint_service.create_blueprint(
            name=body.name, description=body.description
        )
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(400, "Blueprint with this name already exists")
        raise HTTPException(500, str(e))


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
