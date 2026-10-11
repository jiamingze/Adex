"""Creation HTTP adapter; scopes are checked before invoking capabilities."""

from uuid import UUID
from fastapi import APIRouter, Request, HTTPException
import json
import os
from adex_tools.dependencies import core
from adex_tools.api.schemas import Creative

router = APIRouter()


@router.post("/internal/creative/generate")
async def creative(request: Request, body: Creative):
    from adex_tools.creation.service import generate

    claims = core.require(request, "agent", "creative:write")
    return await generate(core, UUID(claims["owner"]), body.model_dump(mode="json"))


@router.get("/internal/creative/capabilities")
async def creative_capabilities(request: Request):
    core.require(request, "app", "creative:read")
    from adex_tools.creation.contracts import MockMediaGenerationProvider

    return await MockMediaGenerationProvider().capabilities()


@router.post("/internal/creative/webhook")
async def creative_webhook(request: Request):
    from adex_tools.creation.webhooks import verify_signature

    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 65536:
            raise HTTPException(413, "WEBHOOK_TOO_LARGE")
    raw = bytes(raw)
    verify_signature(
        os.getenv("ADEX_MEDIA_WEBHOOK_SECRET", ""),
        request.headers.get("X-Timestamp", ""),
        raw,
        request.headers.get("X-Signature", ""),
    )
    try:
        body = json.loads(raw)
        job = UUID(body["job_id"])
        event = str(body["event_id"])
        version = int(body["version"])
        status = body["status"]
        if len(event) > 128 or version < 1 or status not in ("RUNNING", "SUCCEEDED", "FAILED", "CANCELED"):
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        raise HTTPException(400, "INVALID_WEBHOOK_EVENT") from None
    async with core.pool.connection() as conn:
        async with conn.transaction():
            cur = await conn.execute("SELECT * FROM media_jobs WHERE id=%s FOR UPDATE", (job,))
            row = await cur.fetchone()
            if not row:
                raise HTTPException(404, "JOB_NOT_FOUND")
            cur = await conn.execute(
                "INSERT INTO provider_events(provider,event_id,job_id,version,signature_verified) VALUES(%s,%s,%s,%s,true) ON CONFLICT DO NOTHING RETURNING event_id",
                (row["provider"], event, job, version),
            )
            if not await cur.fetchone():
                return {"ok": True, "deduplicated": True}
            if version > row["provider_version"] and row["provider_status"] not in (
                "SUCCEEDED",
                "FAILED",
                "CANCELED",
            ):
                await conn.execute(
                    "UPDATE media_jobs SET provider_status=%s,provider_version=%s WHERE id=%s",
                    (status, version, job),
                )
    return {
        "ok": True,
        "note": "Callback records provider observation; publication still requires controlled file import and run fencing",
    }
