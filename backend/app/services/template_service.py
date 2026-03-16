"""Template service — CRUD, lazy-load, render to disk, batch-apply."""
from . import version_db
from .template_engine import render_template
from .variable_service import get_raw_variables_for_agent
from .file_service import read_file, write_file


async def get_template(template_id: int) -> dict | None:
    return await version_db.get_template(template_id)


async def list_templates_for_agent(agent_id: int) -> list[dict]:
    return await version_db.list_templates(agent_id=agent_id)


async def lookup_or_create(agent_id: int, file_path: str) -> dict:
    """Look up template by (agent_id, file_path). If not found, create from actual file."""
    template = await version_db.get_template_by_path(agent_id, file_path)
    if template:
        return template

    # Lazy-load: read actual file and create template record
    agent = await _get_agent(agent_id)
    agent_name = agent["workspace_name"]

    content = ""
    file_data = read_file(agent_name, file_path)
    if file_data:
        content = file_data["content"]

    template = await version_db.create_template(
        agent_id=agent_id, file_path=file_path, content=content
    )
    return template


async def update_template(template_id: int, content: str,
                          commit_msg: str = None) -> dict:
    """Update template content, create version, render and write to disk."""
    template = await version_db.get_template(template_id)
    if not template:
        raise ValueError(f"Template {template_id} not found")

    # Update template in DB
    updated = await version_db.update_template(template_id, content)

    # Create version record
    agent_id = template["agent_id"]
    content_hash = version_db.compute_hash(content)
    await version_db.create_version(
        agent_id=agent_id,
        file_path=template["file_path"],
        content=content,
        content_hash=content_hash,
        source="template",
        commit_msg=commit_msg,
    )

    # Render and write to disk
    await _render_and_write(agent_id, template["file_path"], content)

    return updated


async def render_template_content(template_id: int) -> dict:
    """Render a template with its agent's variables, return rendered content + warnings."""
    template = await version_db.get_template(template_id)
    if not template:
        raise ValueError(f"Template {template_id} not found")

    variables = await get_raw_variables_for_agent(template["agent_id"])
    result = render_template(template["content"], variables)
    return {
        "content": result.content,
        "warnings": result.warnings,
        "template_id": template_id,
    }


async def apply_template(template_id: int) -> dict:
    """Re-render a single template and write to disk."""
    template = await version_db.get_template(template_id)
    if not template:
        raise ValueError(f"Template {template_id} not found")

    warnings = await _render_and_write(
        template["agent_id"], template["file_path"], template["content"]
    )
    return {"template_id": template_id, "warnings": warnings}


async def batch_apply(template_ids: list[int]) -> list[dict]:
    """Re-render multiple templates and write to disk."""
    results = []
    for tid in template_ids:
        try:
            result = await apply_template(tid)
            results.append({**result, "status": "ok"})
        except Exception as e:
            results.append({"template_id": tid, "status": "error", "error": str(e)})
    return results


async def delete_template(template_id: int) -> bool:
    return await version_db.delete_template(template_id)


# --- Internal helpers ---

async def _get_agent(agent_id: int) -> dict:
    db = await version_db.get_db()
    cursor = await db.execute(
        "SELECT * FROM agents WHERE id = ?", (agent_id,)
    )
    row = await cursor.fetchone()
    if not row:
        raise ValueError(f"Agent {agent_id} not found")
    return dict(row)


async def _render_and_write(agent_id: int, file_path: str, template_content: str) -> list[str]:
    """Render template and write result to the agent's actual file on disk."""
    agent = await _get_agent(agent_id)
    variables = await get_raw_variables_for_agent(agent_id)
    result = render_template(template_content, variables)

    # Write rendered content to disk
    write_file(agent["workspace_name"], file_path, result.content)

    # Update tracked_files hash so change_detector doesn't re-detect
    rendered_hash = version_db.compute_hash(result.content)
    await version_db.upsert_tracked_file(agent_id, file_path, rendered_hash)

    return result.warnings
