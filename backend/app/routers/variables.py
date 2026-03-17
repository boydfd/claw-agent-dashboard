"""Variables API — CRUD + scope resolution + reference scanning."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services import variable_service
from ..services import version_db as vdb

router = APIRouter(prefix="/variables", tags=["variables"])


class VariableCreate(BaseModel):
    name: str
    value: str
    type: str = "text"
    scope: str = "global"
    agent_id: int | None = None
    description: str | None = None


class VariableUpdate(BaseModel):
    name: str | None = None
    value: str | None = None
    type: str | None = None
    description: str | None = None


@router.get("")
async def list_variables(scope: str = None, agent_id: int = None):
    """List all variables, optionally filtered by scope and agent_id."""
    variables = await vdb.list_variables(scope=scope, agent_id=agent_id)
    return [variable_service.mask_variable(v) for v in variables]


@router.get("/agent/{agent_id}")
async def get_agent_variables(agent_id: int):
    """Get effective variables for an agent (global + agent override merged)."""
    return await variable_service.get_merged_variables_for_agent(agent_id)


@router.post("")
async def create_variable(body: VariableCreate):
    """Create a new variable."""
    try:
        return await variable_service.create_variable(
            name=body.name, value=body.value, var_type=body.type,
            scope=body.scope, agent_id=body.agent_id, description=body.description,
        )
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(400, "Variable with this name already exists in this scope")
        raise HTTPException(500, str(e))


@router.put("/{variable_id}")
async def update_variable(variable_id: int, body: VariableUpdate):
    """Update a variable. Returns affected templates. Triggers blueprint sync if blueprint-scoped."""
    try:
        fields = {k: v for k, v in body.model_dump().items() if v is not None}
        variable = await variable_service.update_variable(variable_id, **fields)

        # Find affected templates
        var_raw = await vdb.get_variable(variable_id)
        affected = await variable_service.find_affected_templates(var_raw["name"]) if var_raw else []

        # Blueprint sync trigger: if this is a blueprint-scoped variable, re-sync all derived agents
        if var_raw and var_raw["scope"] == "blueprint":
            from ..services import blueprint_service
            bp = await vdb.get_blueprint_by_agent_id(var_raw["agent_id"])
            if bp:
                # Re-sync all blueprint files to all derived agents
                derivations = await vdb.list_derivations(bp["id"])
                for d in derivations:
                    await blueprint_service.sync_all_files_to_agent(bp, d["agent_id"], d["id"])

        return {"variable": variable, "affected_templates": affected}
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.delete("/{variable_id}")
async def delete_variable(variable_id: int, confirm: bool = False):
    """Delete a variable. Without confirm=true, returns affected templates if any."""
    var = await vdb.get_variable(variable_id)
    if not var:
        raise HTTPException(404, "Variable not found")

    affected = await variable_service.find_affected_templates(var["name"])

    if affected and not confirm:
        return {
            "needs_confirmation": True,
            "affected_templates": affected,
            "message": f"Variable ${{{var['name']}}} is referenced by {len(affected)} template(s). "
                       "Pass confirm=true to delete anyway.",
        }

    success = await variable_service.delete_variable(variable_id)
    if not success:
        raise HTTPException(404, "Variable not found")
    return {"deleted": True}


@router.get("/{variable_id}/references")
async def get_variable_references(variable_id: int):
    """Get list of templates referencing this variable."""
    try:
        return await variable_service.get_variable_references(variable_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
