"""App-scoped memory planning transport; no direct database memory writes."""

from uuid import UUID
from psycopg import Error as DatabaseError
from psycopg_pool import PoolTimeout
from typing import Literal
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, ConfigDict
from adex_kernel.core import owner_match
from adex_agent.dependencies import core, runtime
from adex_agent.memory.planner import propose
from adex_agent.models.provider import ProviderFailure

router = APIRouter()


class MemoryPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    owner_id: UUID
    turn_id: UUID
    snapshot: dict
    model: Literal["", "qwen3.8-max", "minimax"] = ""


@router.post("/internal/agent/memory-plan")
async def plan(request: Request, body: MemoryPlanRequest):
    claims = core.require(request, "app", "memory:plan", body.turn_id)
    owner_match(claims, body.owner_id)
    import json

    if len(json.dumps(body.snapshot, default=str, ensure_ascii=False)) > 250000:
        raise HTTPException(413, detail="MEMORY_INPUT_LIMIT")
    try:
        return await propose(runtime, body.owner_id, body.turn_id, body.snapshot, body.model)
    except (DatabaseError, PoolTimeout):
        raise HTTPException(503, detail="MEMORY_STORE_UNAVAILABLE") from None
    except (ValueError, TimeoutError, ProviderFailure):
        raise HTTPException(502, detail="MEMORY_PLAN_UNAVAILABLE") from None
