"""Checkpoints HTTP adapter; scopes are checked before invoking capabilities."""

from uuid import UUID
from fastapi import APIRouter, Request, HTTPException
from fastapi.encoders import jsonable_encoder
from adex_kernel.core import digest
from adex_agent.dependencies import core

router = APIRouter()


@router.get("/internal/checkpoints/{ref}")
async def checkpoint(request: Request, ref: UUID):
    claims = core.require(request, "automation", "checkpoint:read", ref)
    cp = await core.query(
        "SELECT * FROM checkpoints WHERE id=%s AND owner_id=%s", (ref, claims["owner"]), one=True
    )
    if not cp:
        raise HTTPException(404, detail="NOT_FOUND")
    if digest(cp["state"]) != cp["sha256"]:
        raise HTTPException(409, detail="CHECKPOINT_CORRUPTED")
    return jsonable_encoder(cp)
