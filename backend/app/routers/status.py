"""Status API routes — system metrics, gateway health, agent status, events."""
from typing import Literal, Optional
import httpx
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field, field_validator

from ..services import status as status_service

router = APIRouter(tags=["status"])


@router.get("/status")
async def get_full_status():
    """Get complete system status (gateway + system + all agents)."""
    return status_service.get_full_status()


@router.get("/status/system")
async def get_system_metrics():
    """Get system memory and load metrics."""
    return status_service.get_system_metrics()


@router.get("/status/gateway")
async def get_gateway_status():
    """Get gateway process status."""
    gw = status_service.get_gateway_status()
    gw["uptime_human"] = status_service._format_uptime(gw["uptime_seconds"]) if gw["running"] else "down"
    return gw


@router.get("/status/agent/{agent_name:path}")
async def get_agent_detail(agent_name: str):
    """
    Get detailed status for a specific agent including:
    - Agent status and sessions (with model, token usage, cache rate)
    - Recent events filtered for this agent
    - Compact gateway/system summary
    """
    return status_service.get_agent_detail(agent_name)


@router.get("/status/session/{agent_name:path}/{session_id}/messages")
async def get_session_messages(
    agent_name: str,
    session_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """Get paginated message history for a specific session."""
    return status_service.get_session_messages(agent_name, session_id, offset=offset, limit=limit)


@router.get("/status/events")
async def get_recent_events(
    agent: Optional[str] = Query(None, description="Filter events by agent name"),
    limit: int = Query(100, ge=1, le=500),
):
    """Get recent events parsed from gateway logs."""
    return status_service.get_recent_events(agent_filter=agent, limit=limit)


@router.get("/status/models")
async def get_available_models():
    """Get available models from OpenClaw configuration."""
    return status_service.get_available_models()


class NewSessionRequest(BaseModel):
    agent: str
    session_key: str | None = None  # bind to existing channel session (native /new behavior)


@router.post("/status/session/new")
async def create_new_session(req: NewSessionRequest):
    """Create a new session by sending /new to the Gateway."""
    return await status_service.create_new_session(req.agent, req.session_key)


class SwitchModelRequest(BaseModel):
    agent: str
    model: str
    session_key: str


@router.post("/status/session/model")
async def switch_session_model(req: SwitchModelRequest):
    """Switch model for an existing session via Gateway WebSocket RPC."""
    return await status_service.switch_session_model(req.agent, req.model, req.session_key)


class EnvelopeContext(BaseModel):
    channel: str = "agent-preview"
    sender: str  # required — frontend guards via from-name dialog
    chat_type: str = "group"


class SendMessageRequest(BaseModel):
    agent: str
    session_key: str
    message: str = Field(..., min_length=1, max_length=10000)
    mode: Literal["raw", "envelope"]
    envelope_context: EnvelopeContext | None = None
    attachments: list = Field(default_factory=list)  # reserved for future multimodal

    @field_validator("message", mode="before")
    @classmethod
    def message_not_blank(cls, v):
        if isinstance(v, str) and not v.strip():
            raise ValueError("message must not be blank")
        return v


@router.post("/status/session/send")
async def send_session_message(req: SendMessageRequest):
    try:
        env = req.envelope_context or EnvelopeContext(sender="")
        result = await status_service.send_session_message(
            agent=req.agent,
            session_key=req.session_key,
            message=req.message,
            mode=req.mode,
            envelope_channel=env.channel,
            envelope_sender=env.sender,
            envelope_chat_type=env.chat_type,
        )
        return result
    except httpx.HTTPStatusError as e:
        return {"ok": False, "error": f"Gateway error: {e.response.status_code}"}
    except Exception as e:
        # Avoid leaking internal URLs or headers in error messages
        return {"ok": False, "error": "Failed to send message to gateway"}
