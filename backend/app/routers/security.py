"""Read-only security audit API."""
from fastapi import APIRouter

from ..services.security_audit import build_audit_report

router = APIRouter(tags=["security"])


@router.get("/security/audit")
async def get_security_audit():
    """Aggregated read-only report: agents, skills, variables, env hints."""
    return await build_audit_report()
