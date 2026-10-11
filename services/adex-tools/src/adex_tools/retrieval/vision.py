import base64
import os
import hashlib
import httpx
from fastapi import HTTPException
from psycopg.types.json import Jsonb
from adex_kernel.core import digest, required


async def understand(core, owner, file_id, prompt):
    key = os.getenv("ADEX_VISION_API_KEY", "")
    if not key or os.getenv("ADEX_VISION_PROVIDER") != "minimax-coding-plan":
        raise HTTPException(503, "VISION_BLOCKED_EXTERNAL")
    async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
        async with client.stream(
            "GET",
            required("ADEX_APP_URL") + f"/internal/files/{file_id}/content",
            headers={"Authorization": "Bearer " + core.token("app", "file:read", owner, file_id)},
        ) as response:
            if response.is_error:
                raise HTTPException(404, "FILE_NOT_AVAILABLE")
            data = bytearray()
            async for chunk in response.aiter_bytes():
                data.extend(chunk)
                if len(data) > 4 * 1024 * 1024:
                    raise HTTPException(413, "VISION_IMAGE_TOO_LARGE")
    mime = (
        "image/png" if data.startswith(b"\x89PNG") else "image/jpeg" if data.startswith(b"\xff\xd8") else None
    )
    if not mime:
        raise HTTPException(422, "VISION_FORMAT_UNSUPPORTED")
    effect = "vision:" + digest({"file_sha256": hashlib.sha256(data).hexdigest(), "prompt": prompt})
    async with core.pool.connection() as conn:
        async with conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (str(owner) + effect,))
            cur = await conn.execute(
                "SELECT * FROM effects WHERE owner_id=%s AND effect_key=%s FOR UPDATE", (owner, effect)
            )
            old = await cur.fetchone()
            if old:
                if old["state"] == "SUCCEEDED":
                    return old["result"]
                raise HTTPException(409, "VISION_RESULT_UNKNOWN")
            await conn.execute(
                "INSERT INTO effects(owner_id,effect_key,request_hash,tool_id,state) VALUES(%s,%s,%s,'vision.read','IN_FLIGHT')",
                (owner, effect, effect),
            )
    try:
        async with httpx.AsyncClient(timeout=45, trust_env=False, follow_redirects=False) as client:
            response = await client.post(
                "https://api.minimaxi.com/v1/coding_plan/vlm",
                headers={"Authorization": "Bearer " + key},
                json={
                    "prompt": prompt,
                    "image_url": "data:" + mime + ";base64," + base64.b64encode(data).decode(),
                },
            )
            response.raise_for_status()
            value = response.json()
            if value.get("base_resp", {}).get("status_code", 0) != 0 or not value.get("content"):
                raise ValueError()
        result = {
            "text": value["content"][:12000],
            "provider": "minimax-coding-plan",
            "file_id": str(file_id),
        }
        await core.query(
            "UPDATE effects SET state='SUCCEEDED',result=%s WHERE owner_id=%s AND effect_key=%s",
            (Jsonb(result), owner, effect),
        )
        return result
    except (httpx.HTTPError, ValueError):
        await core.query(
            "UPDATE effects SET state='UNKNOWN' WHERE owner_id=%s AND effect_key=%s", (owner, effect)
        )
        raise HTTPException(503, "VISION_PROVIDER_UNAVAILABLE") from None
