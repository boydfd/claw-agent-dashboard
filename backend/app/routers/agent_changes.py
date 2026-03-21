"""Router for agent file change review (pending changes from disk edits)."""
from fastapi import APIRouter, HTTPException

from ..services import version_db, file_service, variable_service
from ..services.template_engine import render_template, reverse_render

router = APIRouter(prefix="/agents", tags=["agent-changes"])


@router.get("/{agent_name}/pending-changes")
async def list_pending_changes(agent_name: str):
    """List all pending file changes for an agent."""
    agent_id = await version_db.get_or_create_agent(agent_name)
    changes = await version_db.list_agent_pending_changes(agent_id)
    return {"agent_name": agent_name, "changes": changes}


@router.post("/{agent_name}/pending-changes/{change_id}/accept")
async def accept_change(agent_name: str, change_id: int):
    """Accept a pending file change: sync disk content into template system."""
    try:
        result = await _accept_change(agent_name, change_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_name}/pending-changes/{change_id}/reject")
async def reject_change(agent_name: str, change_id: int):
    """Reject a pending file change: overwrite disk with template content."""
    try:
        result = await _reject_change(agent_name, change_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_name}/pending-changes/accept-all")
async def accept_all_changes(agent_name: str):
    """Accept all pending changes for an agent."""
    agent_id = await version_db.get_or_create_agent(agent_name)
    changes = await version_db.list_agent_pending_changes(agent_id)
    results = []
    for change in changes:
        try:
            r = await _accept_change(agent_name, change["id"])
            results.append(r)
        except Exception as e:
            results.append({"accepted": False, "file_path": change["file_path"], "error": str(e)})
    return {"results": results}


@router.post("/{agent_name}/pending-changes/reject-all")
async def reject_all_changes(agent_name: str):
    """Reject all pending changes for an agent."""
    agent_id = await version_db.get_or_create_agent(agent_name)
    changes = await version_db.list_agent_pending_changes(agent_id)
    results = []
    for change in changes:
        try:
            r = await _reject_change(agent_name, change["id"])
            results.append(r)
        except Exception as e:
            results.append({"rejected": False, "file_path": change["file_path"], "error": str(e)})
    return {"results": results}


async def _get_template_and_variables(agent_id: int, file_path: str):
    """Look up template via full chain and resolve correct variables."""
    template = await version_db.get_template_by_path(agent_id, file_path)
    is_inherited = False

    derivation = await version_db.get_derivation_by_agent_id(agent_id)
    blueprint_agent_id = None
    if derivation:
        bp = await version_db.get_blueprint(derivation["blueprint_id"])
        if bp:
            blueprint_agent_id = bp["agent_id"]

    if not template and blueprint_agent_id:
        template = await version_db.get_template_by_path(blueprint_agent_id, file_path)
        is_inherited = True

    # Resolve variables with correct scope
    if derivation and blueprint_agent_id:
        variables = await variable_service.get_raw_variables_for_derived_agent(
            agent_id, blueprint_agent_id
        )
    else:
        variables = await variable_service.get_raw_variables_for_agent(agent_id)

    return template, variables, is_inherited, derivation


async def _accept_change(agent_name: str, change_id: int) -> dict:
    """Accept a single pending change."""
    change = await version_db.get_agent_pending_change(change_id)
    if not change or change["status"] != "pending":
        raise ValueError(f"Pending change {change_id} not found or already resolved")

    agent_id = change["agent_id"]
    file_path = change["file_path"]
    new_content = change["new_content"]

    # Validate change belongs to the specified agent
    expected_agent_id = await version_db.get_or_create_agent(agent_name)
    if agent_id != expected_agent_id:
        raise ValueError(f"Change {change_id} does not belong to agent {agent_name}")

    template, variables, is_inherited, derivation = await _get_template_and_variables(
        agent_id, file_path
    )

    if not template:
        # No template — create one from disk content
        template = await version_db.create_template(agent_id, file_path, new_content)
    elif is_inherited:
        # Inherited from blueprint — detach: create agent's own template copy
        template = await version_db.create_template(agent_id, file_path, template["content"])
        # Record derivation override
        if derivation:
            await version_db.add_override(derivation["id"], file_path)

    # Recover !{VAR} placeholders via reverse render
    recovered_template = reverse_render(template["content"], variables, new_content)

    # Update template in DB with recovered content
    await version_db.update_template(template["id"], recovered_template)

    # Render and write to disk
    result = render_template(recovered_template, variables)
    file_service.write_file(agent_name, file_path, result.content)

    # Create version record (store rendered content that was written to disk)
    content_hash = version_db.compute_hash(result.content)
    await version_db.create_version(
        agent_id=agent_id, file_path=file_path,
        content=result.content, content_hash=content_hash,
        source="disk_sync",
    )

    # Update tracked hash
    await version_db.upsert_tracked_file(agent_id, file_path, content_hash)

    # Resolve pending change
    await version_db.resolve_agent_pending_change(change_id, "accepted")

    return {"accepted": True, "file_path": file_path, "change_type": change["change_type"]}


async def _reject_change(agent_name: str, change_id: int) -> dict:
    """Reject a single pending change."""
    change = await version_db.get_agent_pending_change(change_id)
    if not change or change["status"] != "pending":
        raise ValueError(f"Pending change {change_id} not found or already resolved")

    agent_id = change["agent_id"]
    file_path = change["file_path"]

    # Validate change belongs to the specified agent
    expected_agent_id = await version_db.get_or_create_agent(agent_name)
    if agent_id != expected_agent_id:
        raise ValueError(f"Change {change_id} does not belong to agent {agent_name}")

    template, variables, _, _ = await _get_template_and_variables(agent_id, file_path)

    if template:
        # Render template and overwrite disk
        result = render_template(template["content"], variables)
        file_service.write_file(agent_name, file_path, result.content)
        rendered_hash = version_db.compute_hash(result.content)
        await version_db.upsert_tracked_file(agent_id, file_path, rendered_hash)
    else:
        # No template — just update tracked hash to current disk content
        await version_db.upsert_tracked_file(agent_id, file_path, change["new_hash"])

    # Resolve pending change
    await version_db.resolve_agent_pending_change(change_id, "rejected")

    return {"rejected": True, "file_path": file_path}
