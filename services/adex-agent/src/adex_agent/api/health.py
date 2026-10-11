"""Health HTTP adapter; scopes are checked before invoking capabilities."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
import os
from adex_agent.dependencies import core, runtime

router = APIRouter()


@router.get("/health/live")
async def live():
    return {"status": "UP", "service": "agent"}


@router.get("/health/ready")
async def ready():
    try:
        await core.query("SELECT 1")
        redis_state = "UP"
        try:
            await runtime.redis.ping()
        except Exception:
            redis_state = "DEGRADED"
        return {"status": "UP", "redis": redis_state, "provider": os.getenv("ADEX_MODEL_PROVIDER", "minimax")}
    except Exception:
        return JSONResponse({"status": "DOWN"}, status_code=503)
