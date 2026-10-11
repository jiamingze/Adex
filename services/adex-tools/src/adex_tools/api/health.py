"""Health HTTP adapter; scopes are checked before invoking capabilities."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from adex_tools.dependencies import core

router = APIRouter()


@router.get("/health/live")
async def live():
    return {"status": "UP", "service": "tools"}


@router.get("/health/ready")
async def ready():
    try:
        await core.query("SELECT 1")
        return {"status": "UP"}
    except Exception:
        return JSONResponse({"status": "DOWN"}, status_code=503)
