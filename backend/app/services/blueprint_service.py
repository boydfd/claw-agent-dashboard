"""Blueprint service — CRUD, derive, sync orchestration."""
import fnmatch
import logging
from pathlib import Path, PurePosixPath

from . import version_db, file_service, variable_service
from .template_engine import render_template, extract_variable_names

logger = logging.getLogger(__name__)


async def initialize_blueprint_dirs():
    """On startup: materialize DB blueprint templates to disk if directories don't exist."""
    from ..config import BLUEPRINTS_DIR

    bp_dir = Path(BLUEPRINTS_DIR)
    bp_dir.mkdir(parents=True, exist_ok=True)

    blueprints = await version_db.list_blueprints()
    for bp in blueprints:
        target_dir = bp_dir / bp["name"]
        if target_dir.exists():
            continue  # Already exists, will be handled by change detection

        # Create directory and write all template files
        target_dir.mkdir(parents=True, exist_ok=True)
        templates = await version_db.list_templates(agent_id=bp["agent_id"])
        for t in templates:
            file_path = target_dir / t["file_path"]
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(t["content"], encoding="utf-8")
        logger.info(f"Materialized blueprint '{bp['name']}' to {target_dir} ({len(templates)} files)")


def _matches_exclude_pattern(file_path: str, patterns: list[str]) -> bool:
    """Check if a file path matches any exclude pattern.
    Patterns with '/' match against the full relative path.
    Patterns without '/' match against the basename only."""
    basename = PurePosixPath(file_path).name
    for pattern in patterns:
        if '/' in pattern:
            if fnmatch.fnmatch(file_path, pattern):
                return True
        else:
            if fnmatch.fnmatch(basename, pattern):
                return True
    return False


async def create_blueprint(name: str, description: str = "",
                           source_agent_id: int | None = None,
                           exclude_patterns: list[str] | None = None) -> dict:
    """Create a new blueprint with a virtual agent record.
    Optionally import files from an existing agent."""
    workspace_name = f"_blueprint-{name}"
    agent_id = await version_db.get_or_create_virtual_agent(workspace_name)
    blueprint = await version_db.create_blueprint(
        name=name, description=description, agent_id=agent_id
    )

    imported_file_count = 0

    if source_agent_id is not None:
        # Validate source agent
        db = await version_db.get_db()
        cursor = await db.execute(
            "SELECT id, workspace_name, is_virtual FROM agents WHERE id = ?",
            (source_agent_id,)
        )
        source_agent = await cursor.fetchone()
        if not source_agent:
            raise FileNotFoundError("Source agent not found")
        if source_agent["is_virtual"]:
            raise ValueError("Cannot import from a blueprint's virtual agent")

        # Verify workspace directory exists on filesystem
        from ..config import AGENTS_DIR
        workspace_dir = Path(AGENTS_DIR) / source_agent["workspace_name"]
        if not workspace_dir.exists():
            raise FileNotFoundError(
                f"Agent workspace directory not found: {source_agent['workspace_name']}"
            )

        # Get all files from agent workspace
        agent_files = file_service.list_all_agent_files(source_agent["workspace_name"])

        # Filter by exclude patterns
        patterns = exclude_patterns or []
        if patterns:
            agent_files = [
                f for f in agent_files
                if not _matches_exclude_pattern(f["path"], patterns)
            ]

        # Import each file as a blueprint template
        for f in agent_files:
            await version_db.create_template(
                agent_id=blueprint["agent_id"],
                file_path=f["path"],
                content=f["content"],
            )
            imported_file_count += 1

    return {
        **blueprint,
        "imported_file_count": imported_file_count,
    }


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
    await version_db.delete_pending_changes_for_blueprint(blueprint_id)
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
    await version_db.delete_pending_changes_for_blueprint(blueprint_id)
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

    # Write to disk
    from ..config import BLUEPRINTS_DIR
    disk_file = Path(BLUEPRINTS_DIR) / bp["name"] / file_path
    disk_file.parent.mkdir(parents=True, exist_ok=True)
    disk_file.write_text(content, encoding="utf-8")

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

    # Write to disk file
    from ..config import BLUEPRINTS_DIR
    disk_file = Path(BLUEPRINTS_DIR) / bp["name"] / file_path
    disk_file.parent.mkdir(parents=True, exist_ok=True)
    disk_file.write_text(content, encoding="utf-8")

    # Clear any pending change for this file
    await version_db.delete_pending_change_by_file(blueprint_id, file_path)

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

    # Delete from disk
    from ..config import BLUEPRINTS_DIR
    disk_file = Path(BLUEPRINTS_DIR) / bp["name"] / file_path
    disk_file.unlink(missing_ok=True)
    await version_db.delete_pending_change_by_file(blueprint_id, file_path)

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


async def get_blueprint_variables(blueprint_id: int) -> list[dict]:
    """Get all variables referenced across blueprint template files, with source file info."""
    bp = await version_db.get_blueprint(blueprint_id)
    if not bp:
        return []
    templates = await version_db.list_templates(agent_id=bp["agent_id"])
    var_map = {}  # name -> set of file_paths
    for t in templates:
        for var_name in extract_variable_names(t["content"]):
            var_map.setdefault(var_name, set()).add(t["file_path"])
    return sorted(
        [{"name": k, "source_files": sorted(v)} for k, v in var_map.items()],
        key=lambda x: x["name"]
    )


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


async def resync_all_files(agent_id: int) -> dict:
    """Remove ALL overrides, delete stale derived template records, and
    re-render every blueprint file to disk.

    This also handles the compat case where ``lookup_or_create`` previously
    materialised rendered content as derived-agent template records — those
    records are deleted so the agent falls back to inheriting from the
    blueprint.
    """
    derivation = await version_db.get_derivation_by_agent_id(agent_id)
    if not derivation:
        raise ValueError("Agent is not derived from a blueprint")

    bp = await version_db.get_blueprint(derivation["blueprint_id"])
    if not bp:
        raise ValueError("Blueprint not found")

    # 1. Clear ALL overrides for this derivation
    await version_db.clear_all_overrides(derivation["id"])

    # 2. Delete any erroneously materialised template records owned by
    #    the derived agent (compat: old lookup_or_create bug).  Blueprint
    #    templates belong to bp["agent_id"], not to agent_id.
    stale_templates = await version_db.list_templates(agent_id=agent_id)
    deleted_count = 0
    for t in stale_templates:
        await version_db.delete_template(t["id"])
        deleted_count += 1

    # 3. Re-render every blueprint file to disk
    await sync_all_files_to_agent(bp, agent_id, derivation["id"])

    return {
        "resynced": True,
        "blueprint_name": bp["name"],
        "deleted_stale_templates": deleted_count,
    }


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


# ---------------------------------------------------------------------------
# Accept / Reject pending changes
# ---------------------------------------------------------------------------


async def _generate_change_commit_msg(change: dict) -> str:
    """Generate a descriptive commit message for a pending change.
    TODO: integrate LLM via summary_service for richer messages."""
    if change["change_type"] == "deleted":
        return f"Delete {change['file_path']}"
    elif change["change_type"] == "added":
        return f"Add {change['file_path']}"
    else:
        return f"Update {change['file_path']}"


async def accept_pending_change(change_id: int) -> dict:
    """Accept a single pending change: update DB, create version, sync derived agents."""
    change = await version_db.get_pending_change(change_id)
    if not change or change["status"] != "pending":
        raise ValueError(f"Pending change {change_id} not found or already resolved")

    bp = await version_db.get_blueprint(change["blueprint_id"])
    if not bp:
        raise ValueError(f"Blueprint not found for change {change_id}")

    # 1. Update DB template
    if change["change_type"] == "modified":
        template = await version_db.get_template_by_path(bp["agent_id"], change["file_path"])
        if template:
            await version_db.update_template(template["id"], change["new_content"])
    elif change["change_type"] == "added":
        await version_db.create_template(bp["agent_id"], change["file_path"], change["new_content"])
    elif change["change_type"] == "deleted":
        template = await version_db.get_template_by_path(bp["agent_id"], change["file_path"])
        if template:
            await version_db.delete_template(template["id"])

    # 2. Create version record with LLM-generated commit message
    version_content = change["new_content"] if change["new_content"] is not None else ""
    content_hash = version_db.compute_hash(version_content)
    commit_msg = await _generate_change_commit_msg(change)
    await version_db.create_version(
        agent_id=bp["agent_id"], file_path=change["file_path"],
        content=version_content, content_hash=content_hash,
        source="filesystem_sync", commit_msg=commit_msg,
    )

    # 3. Propagate to derived agents
    synced_agents = []
    failed_agents = []
    if change["change_type"] == "deleted":
        derivations = await version_db.list_derivations(bp["id"])
        for d in derivations:
            is_overridden = await version_db.is_file_overridden(d["id"], change["file_path"])
            if not is_overridden:
                try:
                    file_service.delete_file(d["workspace_name"], change["file_path"])
                    synced_agents.append(d["workspace_name"])
                except Exception as e:
                    logger.warning(f"Failed to delete {change['file_path']} from {d['workspace_name']}: {e}")
                    failed_agents.append(d["workspace_name"])
    elif change["new_content"] is not None:
        try:
            await _sync_file_to_derivations(bp, change["file_path"], change["new_content"])
            derivations = await version_db.list_derivations(bp["id"])
            for d in derivations:
                is_overridden = await version_db.is_file_overridden(d["id"], change["file_path"])
                if not is_overridden:
                    synced_agents.append(d["workspace_name"])
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            # Report all non-overridden derivations as failed
            derivations = await version_db.list_derivations(bp["id"])
            for d in derivations:
                is_overridden = await version_db.is_file_overridden(d["id"], change["file_path"])
                if not is_overridden:
                    failed_agents.append(d["workspace_name"])

    # 4. Resolve pending change
    await version_db.resolve_pending_change(change_id, "accepted")

    return {
        "accepted": True,
        "file_path": change["file_path"],
        "change_type": change["change_type"],
        "commit_msg": commit_msg,
        "synced_agents": synced_agents,
        "failed_agents": failed_agents,
    }


async def reject_pending_change(change_id: int) -> dict:
    """Reject a pending change: revert file on disk to DB content."""
    from ..config import BLUEPRINTS_DIR

    change = await version_db.get_pending_change(change_id)
    if not change or change["status"] != "pending":
        raise ValueError(f"Pending change {change_id} not found or already resolved")

    bp = await version_db.get_blueprint(change["blueprint_id"])
    if not bp:
        raise ValueError(f"Blueprint not found for change {change_id}")

    bp_dir = Path(BLUEPRINTS_DIR) / bp["name"]
    file_path = bp_dir / change["file_path"]

    if change["change_type"] == "modified":
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(change["old_content"], encoding="utf-8")
    elif change["change_type"] == "added":
        file_path.unlink(missing_ok=True)
    elif change["change_type"] == "deleted":
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(change["old_content"], encoding="utf-8")

    await version_db.resolve_pending_change(change_id, "rejected")

    return {
        "rejected": True,
        "file_path": change["file_path"],
        "reverted": True,
    }


async def accept_all_pending_changes(blueprint_id: int) -> dict:
    """Accept all pending changes for a blueprint."""
    changes = await version_db.list_pending_changes(blueprint_id)
    results = []
    failed = []

    for change in changes:
        try:
            result = await accept_pending_change(change["id"])
            results.append(result)
        except Exception as e:
            logger.error(f"Failed to accept change {change['id']}: {e}")
            failed.append({"file_path": change["file_path"], "error": str(e)})

    return {
        "accepted_count": len(results),
        "changes": results,
        "failed_changes": failed,
    }
