"""Templates API — CRUD, lookup, render, apply, batch-apply."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..services import template_service

router = APIRouter(prefix="/templates", tags=["templates"])


class TemplateCreate(BaseModel):
    file_path: str
    content: str
    base_template_id: int | None = None


class TemplateUpdate(BaseModel):
    content: str
    commit_msg: str | None = None


class BatchApply(BaseModel):
    template_ids: list[int]


@router.get("/agent/{agent_id}")
async def list_agent_templates(agent_id: int):
    """List all templates for an agent."""
    return await template_service.list_templates_for_agent(agent_id)


@router.get("/lookup")
async def lookup_template(agent_id: int = Query(...), file_path: str = Query(...)):
    """Look up template by (agent_id, file_path). Creates lazily if not found."""
    try:
        return await template_service.lookup_or_create(agent_id, file_path)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/{template_id}")
async def get_template(template_id: int):
    """Get template detail (raw content with !{VAR} placeholders)."""
    template = await template_service.get_template(template_id)
    if not template:
        raise HTTPException(404, "Template not found")
    return template


@router.get("/{template_id}/rendered")
async def get_rendered_template(template_id: int, agent_id: int = Query(None)):
    """Get rendered template content (variables substituted).
    Pass agent_id for derived agents viewing inherited blueprint templates."""
    try:
        return await template_service.render_template_content(
            template_id, requesting_agent_id=agent_id
        )
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/agent/{agent_id}")
async def create_template(agent_id: int, body: TemplateCreate):
    """Create a new template for an agent."""
    from ..services import version_db
    try:
        return await version_db.create_template(
            agent_id=agent_id, file_path=body.file_path,
            content=body.content, base_template_id=body.base_template_id,
        )
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(400, "Template already exists for this agent and file path")
        raise HTTPException(500, str(e))


@router.put("/{template_id}")
async def update_template(template_id: int, body: TemplateUpdate):
    """Update template content. Creates version, renders, and writes to disk."""
    try:
        return await template_service.update_template(
            template_id, body.content, commit_msg=body.commit_msg
        )
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.delete("/{template_id}")
async def delete_template_endpoint(template_id: int):
    success = await template_service.delete_template(template_id)
    if not success:
        raise HTTPException(404, "Template not found")
    return {"deleted": True}


@router.post("/{template_id}/apply")
async def apply_template(template_id: int):
    """Re-render template and write to disk."""
    try:
        return await template_service.apply_template(template_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/batch-apply")
async def batch_apply(body: BatchApply):
    """Re-render multiple templates and write to disk."""
    return await template_service.batch_apply(body.template_ids)
