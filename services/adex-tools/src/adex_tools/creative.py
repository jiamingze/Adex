from uuid import uuid4
import httpx
from fastapi import HTTPException
from psycopg.types.json import Jsonb
from adex_kernel.core import digest, required
from .media import MockMediaGenerationProvider, KINDS


def normalized_request(body):
    value = {k: v for k, v in body.items() if k not in ("run_id", "epoch", "attempt_id")}
    value.setdefault("input_refs", [])
    value.setdefault("params", {})
    return value


async def generate(core, owner, body, *, composition_part=False):
    if body["kind"] not in KINDS:
        raise HTTPException(400, "UNSUPPORTED_CAPABILITY")
    if body.get("provider") == "dashscope" and body["kind"] not in ("AUDIO", "VIDEO"):
        raise HTTPException(400, "UNSUPPORTED_CAPABILITY")
    if body.get("provider") not in ("mock", "minimax", "acestep", "dashscope") or (body.get("provider") in ("minimax", "acestep") and body["kind"] != "AUDIO"):
        raise HTTPException(503, "BLOCKED_EXTERNAL")
    if body.get("run_id"):
        await core.call(
            "automation",
            "effect:execute",
            "POST",
            f"/internal/runs/{body['run_id']}/authorize-effect",
            {"epoch": body["epoch"], "attempt_id": body["attempt_id"], "request_key": body.get("composition_parent", body["request_key"]) if composition_part else body["request_key"]},
            owner=owner,
            resource=body["run_id"],
        )
    if not body.get("rights_confirmed"):
        raise HTTPException(400, "RIGHTS_CONFIRMATION_REQUIRED")
    params = body.get("params", {})
    if set(params) - {"width", "height", "duration_seconds", "aspect_ratio", "style", "mode"}:
        raise HTTPException(400, "UNSUPPORTED_MEDIA_PARAMETER")
    for name in ("width", "height"):
        if name in params and (not isinstance(params[name], int) or not 64 <= params[name] <= 2048):
            raise HTTPException(400, "INVALID_MEDIA_SIZE")
    if "duration_seconds" in params and (
        not isinstance(params["duration_seconds"], (float, int)) or not 1 <= params["duration_seconds"] <= (600 if body["kind"] == "AUDIO" else 120)
    ):
        raise HTTPException(400, "INVALID_MEDIA_DURATION")
    if len(str(params)) > 2000:
        raise HTTPException(400, "MEDIA_PARAMETERS_TOO_LARGE")
    for reference in body.get("input_refs", []):
        metadata = await core.call(
            "app", "file:read", "GET", f"/internal/files/{reference}", owner=owner, resource=reference
        )
        if not metadata["mime_type"].startswith("image/"):
            raise HTTPException(400, "REFERENCE_IMAGE_REQUIRED")
    key, request_hash = (
        body["request_key"],
        digest(normalized_request(body)),
    )
    recovered_receipt = None
    async with core.pool.connection() as conn:
        async with conn.transaction():
            await conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (str(owner) + ":" + key,)
            )
            cur = await conn.execute(
                "SELECT * FROM media_jobs WHERE owner_id=%s AND request_key=%s FOR UPDATE", (owner, key)
            )
            old = await cur.fetchone()
            if old:
                if (
                    old["request_hash"] != request_hash
                    and digest(normalized_request(old["request"])) != request_hash
                ):
                    raise HTTPException(409, "IDEMPOTENCY_CONFLICT")
                if old["status"] == "SUCCEEDED":
                    return old["result"]
                if old["status"] in ("UNKNOWN", "SUBMITTING"):
                    # Query the recorded job; never create a second submission.
                    if old.get("provider_job_id"):
                        recovered_receipt = {"provider_job_id": old["provider_job_id"]}
                    else:
                        raise HTTPException(409, "PROVIDER_UNKNOWN")
            else:
                if body['provider'] in ('minimax', 'acestep', 'dashscope') and not composition_part:
                    await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",(str(owner)+':music-budget',))
                    row=await (await conn.execute("SELECT count(*) AS jobs FROM media_jobs WHERE owner_id=%s AND provider IN ('minimax','acestep','dashscope') AND request->>'composition_parent' IS NULL AND created_at >= date_trunc('day',now())",(owner,))).fetchone()
                    import os
                    limit = int(os.getenv('ADEX_MEDIA_DAILY_LIMIT', '5'))
                    if not 1 <= limit <= 100:
                        raise HTTPException(503, 'MEDIA_BUDGET_CONFIGURATION_INVALID')
                    if row['jobs']>=limit:
                        raise HTTPException(429,'MUSIC_DAILY_LIMIT')
                job_id = uuid4()
                await conn.execute(
                    "INSERT INTO media_jobs(id,owner_id,request_key,request_hash,kind,provider,status,request) VALUES(%s,%s,%s,%s,%s,%s,'SUBMITTING',%s)",
                    (job_id, owner, key, request_hash, body["kind"], body["provider"], Jsonb(body)),
                )
                await conn.execute(
                    "INSERT INTO effects(owner_id,effect_key,request_hash,tool_id,state) VALUES(%s,%s,%s,'creative.submit','IN_FLIGHT')",
                    (owner, "media:" + key, request_hash),
                )
    try:
        from .minimax_music import MiniMaxMusicProvider
        from .acestep_music import AceStepMusicProvider
        from .dashscope_media import DashScopeMediaProvider
        from .music_composition import MusicCompositionProvider
        provider = DashScopeMediaProvider(body["kind"]) if body["provider"] == "dashscope" else {"mock": MockMediaGenerationProvider, "minimax": MiniMaxMusicProvider, "acestep": AceStepMusicProvider}[body["provider"]]()
        if body['provider'] == 'dashscope' and body['kind'] == 'AUDIO' and provider.model == 'qwen-audio-3.1-tts-next' and params.get('duration_seconds',120) > 120:
            provider = MusicCompositionProvider(core,owner,body)
        if recovered_receipt:
            receipt = await provider.reconcile(
                request_key=key, provider_job_id=recovered_receipt["provider_job_id"]
            )
            if receipt["status"] != "SUCCEEDED" and not isinstance(provider, MusicCompositionProvider):
                raise HTTPException(409, "PROVIDER_UNKNOWN")
        else:
            receipt = await provider.submit(
                kind=body["kind"],
                prompt=body["prompt"],
                input_refs=body.get("input_refs", []),
                params=params,
                request_key=key,
            )
        await core.query(
            "UPDATE media_jobs SET provider_job_id=%s,provider_status=%s,provider_version=1 WHERE owner_id=%s AND request_key=%s",
            (receipt["provider_job_id"], receipt["status"], owner, key),
        )
        data, name, mime = await provider.get_result(provider_job_id=receipt["provider_job_id"])
        async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
            response = await client.post(
                required("ADEX_APP_URL") + "/internal/files",
                headers={
                    "Authorization": "Bearer " + core.token("app", "file:write", owner),
                    "Idempotency-Key": "media:" + key,
                },
                files={"file": (name, data, mime)},
            )
            if response.is_error:
                raise HTTPException(response.status_code, "MEDIA_FILE_IMPORT_FAILED")
            stored = response.json()
        poster_id = None
        if body["kind"] == "VIDEO":
            from .media import video_poster

            poster = await video_poster(data)
            async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
                response = await client.post(
                    required("ADEX_APP_URL") + "/internal/files",
                    headers={
                        "Authorization": "Bearer " + core.token("app", "file:write", owner),
                        "Idempotency-Key": "media-poster:" + key,
                    },
                    files={"file": ("poster.png", poster, "image/png")},
                )
                response.raise_for_status()
                poster_id = response.json()["id"]
        result = {
            "content": "测试模式作品已生成；真实模型接入状态：BLOCKED_EXTERNAL。" if body["provider"] == "mock" else ("原创音乐已生成，可以播放或下载。目标时长是创作提示，实际时长以播放器为准。" if body["kind"] == "AUDIO" else "视频已生成，可以播放或下载。"),
            "artifact": {
                "kind": body["kind"],
                "file_id": stored["id"],
                "poster_file_id": poster_id,
                "prompt": body["prompt"],
                "input_refs": body.get("input_refs", []),
                "params": params,
                "model_id": "mock-fixture-v1" if body["provider"] == "mock" else provider.model,
                "provenance": "deterministic, locally generated test fixture" if body["provider"] == "mock" else body["provider"] + " original " + body["kind"].lower() + " generation",
                "rights": "Adex test fixture; user may use this generated sample" if body["provider"] == "mock" else "Original generation; use subject to provider terms",
                "duration_ms": getattr(provider, "metadata", {}).get("music_duration"),
                "composition": getattr(provider, "metadata", {}).get("composition"),
                "section_file_ids": getattr(provider, "metadata", {}).get("section_file_ids", []),
                "mock": body["provider"] == "mock",
            },
        }
        async with core.pool.connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    "UPDATE media_jobs SET status='SUCCEEDED',result=%s,updated_at=now() WHERE owner_id=%s AND request_key=%s AND status IN ('SUBMITTING','UNKNOWN')",
                    (Jsonb(result), owner, key),
                )
                await conn.execute(
                    "UPDATE effects SET state='SUCCEEDED',result=%s WHERE owner_id=%s AND effect_key=%s",
                    (Jsonb(result), owner, "media:" + key),
                )
        return result
    except BaseException:
        await core.query(
            "UPDATE media_jobs SET status='UNKNOWN',updated_at=now() WHERE owner_id=%s AND request_key=%s AND status='SUBMITTING'",
            (owner, key),
        )
        await core.query(
            "UPDATE effects SET state='UNKNOWN' WHERE owner_id=%s AND effect_key=%s AND state='IN_FLIGHT'",
            (owner, "media:" + key),
        )
        raise
