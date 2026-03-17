"""Blueprint service — CRUD, derive, sync orchestration."""
import logging

from . import version_db, file_service, variable_service
from .template_engine import render_template, extract_variable_names

logger = logging.getLogger(__name__)


async def create_blueprint(name: str, description: str = "") -> dict:
    """Create a new blueprint with a virtual agent record."""
    workspace_name = f"_blueprint-{name}"
    agent_id = await version_db.get_or_create_virtual_agent(workspace_name)
    blueprint = await version_db.create_blueprint(
        name=name, description=description, agent_id=agent_id
    )
    return blueprint


async def get_blueprint(blueprint_id: int) -> dict | None:
    return await version_db.get_blueprint(blueprint_id)


async def list_blueprints() -> list[dict]:
    return await version_db.list_blueprints()


async def update_blueprint(blueprint_id: int, **fields) -> dict | None:
    return await version_db.update_blueprint(blueprint_id, **fields)


async def delete_blueprint(blueprint_id: int) -> dict:
    """Delete blueprint. Returns derivation info for confirmation."""
    derivations = await version_db.list_derivations(blueprint_id)
    if derivations:
        return {
            "needs_confirmation": True,
            "derivation_count": len(derivations),
            "derivations": derivations,
        }
    # Delete template files, then blueprint
    bp = await version_db.get_blueprint(blueprint_id)
    if bp:
        templates = await version_db.list_templates(agent_id=bp["agent_id"])
        for t in templates:
            await version_db.delete_template(t["id"])
    await version_db.delete_blueprint(blueprint_id)
    return {"deleted": True}


async def force_delete_blueprint(blueprint_id: int) -> bool:
    """Delete blueprint even with derivations (cascade not automatic)."""
    bp = await version_db.get_blueprint(blueprint_id)
    if not bp:
        return False
    # Delete templates
    templates = await version_db.list_templates(agent_id=bp["agent_id"])
    for t in templates:
        await version_db.delete_template(t["id"])
    # Delete derivation overrides and derivations via version_db CRUD
    derivations = await version_db.list_derivations(blueprint_id)
    for d in derivations:
        overrides = await version_db.list_overrides(d["id"])
        for o in overrides:
            await version_db.remove_override(d["id"], o["file_path"])
    await version_db.delete_derivations_for_blueprint(blueprint_id)
    await version_db.delete_blueprint(blueprint_id)
    return True


# ---------------------------------------------------------------------------
# Blueprint Files (stored in templates table)
# ---------------------------------------------------------------------------

async def list_blueprint_files(blueprint_id: int) -> list[dict]:
    bp = await version_db.get_blueprint(blueprint_id)
    if not bp:
        raise ValueError(f"Blueprint {blueprint_id} not found")
    templates = await version_db.list_templates(agent_id=bp["agent_id"])
    return [{"file_path": t["file_path"], "id": t["id"]} for t in templates]


async def get_blueprint_file(blueprint_id: int, file_path: str) -> dict | None:
    bp = await version_db.get_blueprint(blueprint_id)
    if not bp:
        return None
    return await version_db.get_template_by_path(bp["agent_id"], file_path)


async def add_blueprint_file(blueprint_id: int, file_path: str, content: str) -> dict:
    bp = await version_db.get_blueprint(blueprint_id)
    if not bp:
        raise ValueError(f"Blueprint {blueprint_id} not found")
    template = await version_db.create_template(
        agent_id=bp["agent_id"], file_path=file_path, content=content
    )
    return template


async def update_blueprint_file(
    blueprint_id: int, file_path: str, content: str
) -> dict:
    """Update a blueprint file and sync to all non-overridden derived agents."""
    bp = await version_db.get_blueprint(blueprint_id)
    if not bp:
        raise ValueError(f"Blueprint {blueprint_id} not found")

    template = await version_db.get_template_by_path(bp["agent_id"], file_path)
    if not template:
        raise ValueError(f"File {file_path} not found in blueprint")

    # Update template in DB
    updated = await version_db.update_template(template["id"], content)

    # Sync to derived agents
    await _sync_file_to_derivations(bp, file_path, content)

    return updated


async def delete_blueprint_file(blueprint_id: int, file_path: str) -> bool:
    """Delete blueprint file and remove from non-overridden derived agents."""
    bp = await version_db.get_blueprint(blueprint_id)
    if not bp:
        return False

    template = await version_db.get_template_by_path(bp["agent_id"], file_path)
    if not template:
        return False

    await version_db.delete_template(template["id"])

    # Delete from non-overridden derived agents
    derivations = await version_db.list_derivations(blueprint_id)
    for d in derivations:
        is_overridden = await version_db.is_file_overridden(d["id"], file_path)
        if not is_overridden:
            try:
                agent_name = d["workspace_name"]
                file_service.delete_file(agent_name, file_path)
            except Exception as e:
                logger.warning(f"Failed to delete {file_path} from {d['workspace_name']}: {e}")

    return True


async def get_blueprint_variables(blueprint_id: int) -> list[str]:
    """Get all variable names referenced across blueprint template files."""
    bp = await version_db.get_blueprint(blueprint_id)
    if not bp:
        return []
    templates = await version_db.list_templates(agent_id=bp["agent_id"])
    all_vars = set()
    for t in templates:
        all_vars.update(extract_variable_names(t["content"]))
    return sorted(all_vars)


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------

async def _sync_file_to_derivations(
    blueprint: dict, file_path: str, template_content: str
):
    """Render and write a blueprint file to all non-overridden derived agents."""
    derivations = await version_db.list_derivations(blueprint["id"])

    for d in derivations:
        is_overridden = await version_db.is_file_overridden(d["id"], file_path)
        if is_overridden:
            continue

        try:
            agent_name = d["workspace_name"]
            agent_id = d["agent_id"]

            # Three-layer variable merge
            variables = await variable_service.get_raw_variables_for_derived_agent(
                agent_id, blueprint["agent_id"]
            )

            # Render
            result = render_template(template_content, variables)

            # Write to disk
            try:
                file_service.write_file(agent_name, file_path, result.content)
            except FileNotFoundError:
                file_service.create_file(agent_name, file_path, result.content)

            # Create version record
            content_hash = version_db.compute_hash(result.content)
            await version_db.create_version(
                agent_id=agent_id,
                file_path=file_path,
                content=result.content,
                content_hash=content_hash,
                source="blueprint_sync",
                commit_msg=f"Synced from blueprint '{blueprint['name']}'",
            )

            # Update tracked_files hash
            await version_db.upsert_tracked_file(agent_id, file_path, content_hash)

        except Exception as e:
            logger.error(f"Sync failed for {d['workspace_name']}/{file_path}: {e}")


async def sync_all_files_to_agent(blueprint: dict, agent_id: int, derivation_id: int):
    """Render and write ALL blueprint files to a single derived agent.
    Used during derive and resync."""
    templates = await version_db.list_templates(agent_id=blueprint["agent_id"])

    db = await version_db.get_db()
    cursor = await db.execute(
        "SELECT workspace_name FROM agents WHERE id = ?", (agent_id,)
    )
    agent_row = await cursor.fetchone()
    agent_name = agent_row["workspace_name"]

    variables = await variable_service.get_raw_variables_for_derived_agent(
        agent_id, blueprint["agent_id"]
    )

    for t in templates:
        is_overridden = await version_db.is_file_overridden(derivation_id, t["file_path"])
        if is_overridden:
            continue

        result = render_template(t["content"], variables)

        try:
            file_service.write_file(agent_name, t["file_path"], result.content)
        except FileNotFoundError:
            file_service.create_file(agent_name, t["file_path"], result.content)

        content_hash = version_db.compute_hash(result.content)
        await version_db.create_version(
            agent_id=agent_id,
            file_path=t["file_path"],
            content=result.content,
            content_hash=content_hash,
            source="blueprint_sync",
            commit_msg=f"Synced from blueprint '{blueprint['name']}'",
        )
        await version_db.upsert_tracked_file(agent_id, t["file_path"], content_hash)


# ---------------------------------------------------------------------------
# Derive
# ---------------------------------------------------------------------------

async def derive_agent(
    blueprint_id: int,
    agent_name: str,
    variables: dict[str, str] | None = None,
    create_openclaw_agent: bool = False,
) -> dict:
    """Create a derived agent from a blueprint."""
    bp = await version_db.get_blueprint(blueprint_id)
    if not bp:
        raise ValueError(f"Blueprint {blueprint_id} not found")

    workspace_name = f"workspace-{agent_name}"

    # Check for duplicate
    db = await version_db.get_db()
    cursor = await db.execute(
        "SELECT id FROM agents WHERE workspace_name = ?", (workspace_name,)
    )
    if await cursor.fetchone():
        raise ValueError(f"Agent '{agent_name}' already exists")

    # 1. Create agent record
    agent_id = await version_db.get_or_create_agent(workspace_name)

    # 2. Create derivation record
    derivation = await version_db.create_derivation(bp["id"], agent_id)

    # 3. Create agent-scoped variables for overrides
    if variables:
        for var_name, var_value in variables.items():
            await version_db.create_variable(
                name=var_name, value=var_value, var_type="text",
                scope="agent", agent_id=agent_id,
            )

    # 4. Create workspace directory
    from pathlib import Path
    from ..config import AGENTS_DIR
    workspace_dir = Path(AGENTS_DIR) / workspace_name
    workspace_dir.mkdir(parents=True, exist_ok=True)

    # 5. Render all blueprint files and write
    await sync_all_files_to_agent(bp, agent_id, derivation["id"])

    # 6. OpenClaw integration
    openclaw_result = None
    if create_openclaw_agent:
        from .openclaw_service import register_agent, restart_gateway
        try:
            # Get TALK_ROOM from merged variables for binding
            merged_vars = await variable_service.get_raw_variables_for_derived_agent(
                agent_id, bp["agent_id"]
            )
            talk_room = merged_vars.get("TALK_ROOM")
            openclaw_result = await register_agent(agent_name, workspace_name, talk_room)
            await restart_gateway()
        except Exception as e:
            logger.error(f"OpenClaw registration failed: {e}")
            openclaw_result = {"error": str(e)}

    return {
        "agent_id": agent_id,
        "agent_name": agent_name,
        "workspace_name": workspace_name,
        "derivation_id": derivation["id"],
        "blueprint_name": bp["name"],
        "openclaw": openclaw_result,
    }


# ---------------------------------------------------------------------------
# Resync
# ---------------------------------------------------------------------------

async def resync_file(agent_id: int, file_path: str) -> dict:
    """Remove override and re-render file from blueprint."""
    derivation = await version_db.get_derivation_by_agent_id(agent_id)
    if not derivation:
        raise ValueError("Agent is not derived from a blueprint")

    bp = await version_db.get_blueprint(derivation["blueprint_id"])
    if not bp:
        raise ValueError("Blueprint not found")

    # Remove override
    await version_db.remove_override(derivation["id"], file_path)

    # Get blueprint template content
    template = await version_db.get_template_by_path(bp["agent_id"], file_path)
    if not template:
        raise ValueError(f"File {file_path} not found in blueprint")

    # Render and write
    db = await version_db.get_db()
    cursor = await db.execute(
        "SELECT workspace_name FROM agents WHERE id = ?", (agent_id,)
    )
    agent_row = await cursor.fetchone()
    agent_name = agent_row["workspace_name"]

    variables = await variable_service.get_raw_variables_for_derived_agent(
        agent_id, bp["agent_id"]
    )
    result = render_template(template["content"], variables)

    try:
        file_service.write_file(agent_name, file_path, result.content)
    except FileNotFoundError:
        file_service.create_file(agent_name, file_path, result.content)

    content_hash = version_db.compute_hash(result.content)
    version = await version_db.create_version(
        agent_id=agent_id,
        file_path=file_path,
        content=result.content,
        content_hash=content_hash,
        source="blueprint_sync",
        commit_msg=f"Resynced from blueprint '{bp['name']}'",
    )
    await version_db.upsert_tracked_file(agent_id, file_path, content_hash)

    return {"resynced": True, "file_path": file_path, "version": version}


async def get_derivation_status(agent_id: int) -> dict | None:
    """Get derivation status for an agent: blueprint info + per-file override status."""
    derivation = await version_db.get_derivation_by_agent_id(agent_id)
    if not derivation:
        return None

    bp = await version_db.get_blueprint(derivation["blueprint_id"])
    if not bp:
        return None

    # Get blueprint files
    templates = await version_db.list_templates(agent_id=bp["agent_id"])
    overrides = await version_db.list_overrides(derivation["id"])
    overridden_paths = {o["file_path"] for o in overrides}

    files = []
    for t in templates:
        files.append({
            "file_path": t["file_path"],
            "is_overridden": t["file_path"] in overridden_paths,
        })

    return {
        "is_derived": True,
        "blueprint_id": bp["id"],
        "blueprint_name": bp["name"],
        "derivation_id": derivation["id"],
        "files": files,
    }
