"""Variable service — CRUD, scope resolution, masking, reference scanning."""
from . import version_db
from .template_engine import count_variable_references

SECRET_MASK = "******"


def mask_variable(var: dict) -> dict:
    """Return a copy with secret values masked."""
    result = dict(var)
    if result.get("type") == "secret":
        result["value"] = SECRET_MASK
    return result


async def list_all_variables() -> list[dict]:
    """List all variables (secrets masked)."""
    variables = await version_db.list_variables()
    return [mask_variable(v) for v in variables]


async def get_merged_variables_for_agent(agent_id: int) -> list[dict]:
    """Get effective variables for an agent: agent-level overrides global.
    Returns masked list with scope field indicating origin."""
    global_vars = await version_db.list_variables(scope="global")
    agent_vars = await version_db.list_variables(scope="agent", agent_id=agent_id)

    merged = {}
    for v in global_vars:
        merged[v["name"]] = mask_variable(v)
    for v in agent_vars:
        merged[v["name"]] = mask_variable(v)

    return list(merged.values())


async def get_raw_variables_for_agent(agent_id: int) -> dict[str, str]:
    """Get effective variable name->value mapping (unmasked) for rendering.
    Agent-level overrides global."""
    global_vars = await version_db.list_variables(scope="global")
    agent_vars = await version_db.list_variables(scope="agent", agent_id=agent_id)

    result = {}
    for v in global_vars:
        result[v["name"]] = v["value"]
    for v in agent_vars:
        result[v["name"]] = v["value"]
    return result


async def create_variable(name: str, value: str, var_type: str = "text",
                          scope: str = "global", agent_id: int = None,
                          description: str = None) -> dict:
    var = await version_db.create_variable(
        name=name, value=value, var_type=var_type,
        scope=scope, agent_id=agent_id, description=description
    )
    return mask_variable(var)


async def update_variable(variable_id: int, **fields) -> dict:
    """Update variable. If value == SECRET_MASK, skip value update."""
    if fields.get("value") == SECRET_MASK:
        del fields["value"]
    var = await version_db.update_variable(variable_id, **fields)
    if var is None:
        raise ValueError(f"Variable {variable_id} not found")
    return mask_variable(var)


async def delete_variable(variable_id: int) -> bool:
    return await version_db.delete_variable(variable_id)


async def get_variable_references(variable_id: int) -> list[dict]:
    """Find all templates referencing this variable, with ref counts."""
    var = await version_db.get_variable(variable_id)
    if not var:
        raise ValueError(f"Variable {variable_id} not found")

    templates = await version_db.find_templates_referencing_variable(var["name"])
    results = []
    for t in templates:
        ref_count = count_variable_references(t["content"], var["name"])
        workspace = t.get("agent_workspace_name", "")
        display_name = workspace.replace("workspace-", "") if workspace != "workspace" else "main"
        results.append({
            "id": t["id"],
            "agent_id": t["agent_id"],
            "agent_name": display_name,
            "file_path": t["file_path"],
            "ref_count": ref_count,
        })
    return results


async def find_affected_templates(var_name: str) -> list[dict]:
    """Find templates affected by a variable name change."""
    templates = await version_db.find_templates_referencing_variable(var_name)
    results = []
    for t in templates:
        ref_count = count_variable_references(t["content"], var_name)
        workspace = t.get("agent_workspace_name", "")
        display_name = workspace.replace("workspace-", "") if workspace != "workspace" else "main"
        results.append({
            "id": t["id"],
            "agent_id": t["agent_id"],
            "agent_name": display_name,
            "file_path": t["file_path"],
            "ref_count": ref_count,
        })
    return results
