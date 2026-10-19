"""Read-only goal planning proposals; publication is an App use case."""

from uuid import UUID
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from adex_kernel.core import owner_match
from adex_agent.dependencies import core, runtime
from adex_agent.models.provider import ProviderFailure

router = APIRouter()


class GoalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    owner_id: UUID
    request_id: UUID
    title: str = Field(min_length=1, max_length=200)
    outcome: str = Field(default="", max_length=4000)


@router.post("/internal/agent/goal-plan")
async def plan(request: Request, body: GoalRequest):
    claims = core.require(request, "app", "goal:plan")
    owner_match(claims, body.owner_id)
    from adex_agent.goals.planning import compose_plan

    try:
        return await compose_plan(runtime, body)
    except ProviderFailure as exc:
        raise HTTPException(502, detail=exc.code) from None
    except (ValueError, TypeError, TimeoutError):
        raise HTTPException(502, detail="GOAL_PLAN_FAILED") from None
