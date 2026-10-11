"""Chat HTTP adapter; scopes are checked before invoking capabilities."""

from adex_agent.execution.interactive import InteractiveTurnService
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from adex_kernel.core import owner_match
from adex_agent.dependencies import core, runtime
from adex_agent.api.schemas import Turn

router = APIRouter()


@router.post("/internal/agent/turns")
async def turn(request: Request, body: Turn):
    claims = core.require(request, "app", "turn:execute", body.turn_id)
    owner_match(claims, body.owner_id)
    if str(body.context.get("owner_id")) != str(body.owner_id) or str(
        body.context.get("conversation_id")
    ) != str(body.conversation_id):
        raise HTTPException(403, detail="SCOPE_DENIED")

    return StreamingResponse(
        InteractiveTurnService(core, runtime).events(body), media_type="application/x-ndjson"
    )
