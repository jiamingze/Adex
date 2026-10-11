from contextlib import asynccontextmanager
from uuid import UUID
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from adex_kernel.core import Core
from .search import web_search, SearchUnavailable

core = Core("tools")


@asynccontextmanager
async def lifespan(app):
    await core.start()
    yield
    await core.pool.close()


app = FastAPI(title="Adex Tools", lifespan=lifespan, docs_url=None, redoc_url=None)


@app.exception_handler(HTTPException)
async def error(request, exc):
    return JSONResponse({"code": exc.detail}, status_code=exc.status_code)


@app.get("/health/live")
async def live():
    return {"status": "UP", "service": "tools"}


@app.get("/health/ready")
async def ready():
    try:
        await core.query("SELECT 1")
        return {"status": "UP"}
    except Exception:
        return JSONResponse({"status": "DOWN"}, status_code=503)


class Search(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=300)


@app.post("/internal/search")
async def search(request: Request, body: Search):
    claims = core.require(request, "agent", "search:read")
    UUID(claims["owner"])
    await reserve_search(claims["owner"])
    try:
        return await web_search(body.query)
    except SearchUnavailable as exc:
        raise HTTPException(503, detail=str(exc)) from None


@app.get("/internal/catalog")
async def catalog(request: Request):
    core.require(request, "agent", "search:read")
    return {
        "tools": [{"id": "web.search", "side_effect": "READ", "availability": "AUTHENTICATED_API"}],
        "external_write_tools": "CALDAV_APPROVAL_REQUIRED",
    }


class Creative(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str
    prompt: str = Field(min_length=1, max_length=16000)
    request_key: str = Field(min_length=1, max_length=180)
    provider: str = "mock"
    rights_confirmed: bool = False
    input_refs: list[UUID] = Field(default_factory=list, max_length=3)
    params: dict = Field(default_factory=dict)
    run_id: UUID | None = None
    epoch: int | None = None
    attempt_id: UUID | None = None


@app.post("/internal/creative/generate")
async def creative(request: Request, body: Creative):
    from .creative import generate

    claims = core.require(request, "agent", "creative:write")
    return await generate(core, UUID(claims["owner"]), body.model_dump(mode="json"))


@app.post("/internal/music/search")
async def music(request: Request, body: Search):
    core.require(request, "app", "music:read")
    from .music import catalog_search

    return await catalog_search(body.query)


class CalendarRequest(BaseModel):
    origin_conversation_id: UUID | None = None
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    start: str = Field(max_length=60)
    end: str = Field(max_length=60)


@app.get("/internal/approvals")
async def approvals(request: Request):
    claims = core.require(request, "app", "approval:read")
    rows = await core.query(
        "SELECT * FROM approvals WHERE owner_id=%s ORDER BY created_at DESC LIMIT 100",
        (UUID(claims["owner"]),),
    )
    from fastapi.encoders import jsonable_encoder

    return jsonable_encoder({"items": rows})


@app.post("/internal/approvals")
async def approval(request: Request, body: CalendarRequest):
    from .calendar import create_approval
    from fastapi.encoders import jsonable_encoder

    claims = core.require(request, "app", "approval:write")
    return jsonable_encoder(await create_approval(core, UUID(claims["owner"]), body.model_dump(mode="json")))


@app.post("/internal/approvals/{approval_id}/{action}")
async def approval_action(request: Request, approval_id: UUID, action: str):
    from .calendar import act

    if action not in ("approve", "revoke", "reconcile"):
        raise HTTPException(400, "INVALID_ACTION")
    claims = core.require(request, "app", "approval:write", approval_id)
    if action == "reconcile":
        from .calendar import reconcile

        return await reconcile(core, UUID(claims["owner"]), approval_id)
    return await act(core, UUID(claims["owner"]), approval_id, action)


@app.post("/internal/monitor/search")
async def monitor_search(request: Request, body: Search):
    core.require(request, "automation", "monitor:read")
    await reserve_search("shared-monitor")
    try:
        result = await web_search(body.query)
        # Capture time belongs to observation metadata, not change fingerprint.
        for item in result["items"]:
            item.pop("fetched_at", None)
        return result
    except SearchUnavailable as exc:
        raise HTTPException(503, str(exc)) from None


@app.post("/internal/research")
async def research_search(request: Request, body: Search):
    claims = core.require(request, "agent", "search:read")
    await reserve_search(claims["owner"], 3)
    from .research import research

    try:
        return await research(body.query)
    except SearchUnavailable as exc:
        raise HTTPException(503, str(exc)) from None


async def reserve_search(owner, count=1):
    from datetime import datetime, timezone

    row = await core.query(
        "INSERT INTO search_budgets(owner_key,day,calls) VALUES(%s,%s,%s) ON CONFLICT(owner_key,day) DO UPDATE SET calls=search_budgets.calls+excluded.calls WHERE search_budgets.calls+excluded.calls<=80 RETURNING calls",
        (str(owner), datetime.now(timezone.utc).date(), count),
        one=True,
    )
    if not row:
        raise HTTPException(429, "SEARCH_BUDGET_EXCEEDED")


class FileExtract(BaseModel):
    file_id: UUID


@app.post("/internal/files/extract")
async def file_extract(request: Request, body: FileExtract):
    import asyncio
    import json
    import sys
    import os
    import tempfile
    from pathlib import Path
    import httpx

    claims = core.require(request, "agent", "file:read", body.file_id)
    with tempfile.TemporaryDirectory(prefix="adex-extract-") as directory:
        path = Path(directory) / "input"
        async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
            async with client.stream(
                "GET",
                os.environ["ADEX_APP_URL"] + f"/internal/files/{body.file_id}/content",
                headers={
                    "Authorization": "Bearer " + core.token("app", "file:read", claims["owner"], body.file_id)
                },
            ) as response:
                if response.is_error:
                    raise HTTPException(404, "FILE_NOT_AVAILABLE")
                size = 0
                with path.open("wb") as output:
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > 25 * 1024 * 1024:
                            raise HTTPException(413, "FILE_SIZE_LIMIT")
                        output.write(chunk)
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "adex_tools.extract_runner",
            str(path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env={"PATH": os.environ.get("PATH", ""), "LANG": "en_US.UTF-8"},
        )
        try:
            output, _ = await asyncio.wait_for(process.communicate(), 7)
        except BaseException:
            process.kill()
            await process.wait()
            raise HTTPException(422, "FILE_PROCESSING_LIMIT") from None
        if process.returncode or len(output) > 200000:
            raise HTTPException(422, "UNSUPPORTED_OR_INVALID_FILE")
        return json.loads(output)


class GameSource(BaseModel):
    source: str = Field(min_length=1, max_length=128000)


@app.post("/internal/game/check")
async def check_game(request: Request, body: GameSource):
    core.require(request, "agent", "code:check")
    from .code_runner import check_game

    return await check_game(body.source)


class TextArtifact(BaseModel):
    kind: str
    source: str = Field(min_length=1, max_length=128000)
    request_key: str = Field(min_length=1, max_length=180)


@app.post("/internal/artifacts/import")
async def import_artifact(request: Request, body: TextArtifact):
    import httpx
    import os

    claims = core.require(request, "agent", "artifact:write")
    suffix = {"RESEARCH": "md", "TRAVEL": "md", "GAME": "html", "DIAGRAM": "mmd"}.get(body.kind)
    if not suffix:
        raise HTTPException(400, "INVALID_ARTIFACT_KIND")
    if body.kind == "DIAGRAM":
        from .diagram import validate_diagram

        validate_diagram(body.source)
    async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
        response = await client.post(
            os.environ["ADEX_APP_URL"] + "/internal/files",
            headers={
                "Authorization": "Bearer " + core.token("app", "file:write", claims["owner"]),
                "Idempotency-Key": "artifact:" + body.request_key,
            },
            files={"file": ("artifact." + suffix, body.source.encode(), "text/plain")},
        )
        if response.is_error:
            raise HTTPException(response.status_code, "ARTIFACT_FILE_IMPORT_FAILED")
        return {
            "file_id": response.json()["id"],
            "source_format": suffix,
            "renderer_version": "mermaid-12.1.0-strict-v1" if suffix == "mmd" else None,
        }


class TravelRequest(BaseModel):
    city: str = Field(min_length=1, max_length=100)
    start: str = Field(max_length=10)
    end: str = Field(max_length=10)


@app.post("/internal/travel")
async def travel(request: Request, body: TravelRequest):
    claims = core.require(request, "agent", "travel:read")
    await reserve_search(claims["owner"], 2)
    from .travel import plan_evidence

    try:
        return await plan_evidence(body.city, body.start, body.end)
    except ValueError:
        raise HTTPException(400, "INVALID_TRAVEL_DATES") from None


@app.get("/internal/creative/capabilities")
async def creative_capabilities(request: Request):
    core.require(request, "app", "creative:read")
    from .media import MockMediaGenerationProvider

    return await MockMediaGenerationProvider().capabilities()


@app.post("/internal/creative/webhook")
async def creative_webhook(request: Request):
    import os
    import json
    from .webhooks import verify_signature

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


class VisionRequest(BaseModel):
    file_id: UUID
    prompt: str = Field(min_length=1, max_length=2000)


@app.post("/internal/vision")
async def vision(request: Request, body: VisionRequest):
    claims = core.require(request, "agent", "vision:read", body.file_id)
    await reserve_search(claims["owner"])
    from .vision import understand

    return await understand(core, UUID(claims["owner"]), body.file_id, body.prompt)


class CalendarExecution(BaseModel):
    approval_id: UUID
    run_id: UUID
    epoch: int
    attempt_id: UUID


@app.post("/internal/calendar/execute")
async def calendar_execute(request: Request, body: CalendarExecution):
    from .calendar import act

    claims = core.require(request, "agent", "calendar:execute", body.approval_id)
    await core.call(
        "automation",
        "effect:execute",
        "POST",
        f"/internal/runs/{body.run_id}/authorize-effect",
        body.model_dump(mode="json"),
        owner=claims["owner"],
        resource=body.run_id,
    )
    return await act(core, UUID(claims["owner"]), body.approval_id, "execute", body)


@app.post("/internal/music/catalog")
async def agent_music(request: Request, body: Search):
    core.require(request, "agent", "music:read")
    from .music import catalog_search

    return await catalog_search(body.query)


class WeatherRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


@app.post("/internal/monitor/weather")
async def monitor_weather(request: Request, body: WeatherRequest):
    core.require(request, "automation", "monitor:read")
    from .weather import current_weather

    return await current_weather(body.latitude, body.longitude)


@app.get("/internal/usage")
async def tool_usage(request: Request):
    claims = core.require(request, "app", "usage:read")
    rows = await core.query(
        "SELECT owner_key,calls FROM search_budgets WHERE owner_key IN (%s,'shared-monitor') AND day=(clock_timestamp() AT TIME ZONE 'UTC')::date",
        (claims["owner"],),
    )
    values = {row["owner_key"]: row["calls"] for row in rows}
    media = await core.query(
        "SELECT status,count(*) AS jobs FROM media_jobs WHERE owner_id=%s GROUP BY status",
        (UUID(claims["owner"]),),
    )
    return {
        "daily_tool_unit_limit": 80,
        "reserved_tool_units": values.get(claims["owner"], 0),
        "shared_monitor_units": values.get("shared-monitor", 0),
        "media_states": media,
        "billing_note": "Reserved units bound tool work; provider invoices remain authoritative",
    }


class BrowserRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(min_length=1,max_length=2000)
    query: str = Field(default="",max_length=300)


@app.post("/internal/browser/read")
async def browser_read(request: Request, body: BrowserRead):
    from .browser import read_page
    claims=core.require(request,"agent","search:read")
    UUID(claims["owner"])
    await reserve_search(claims["owner"])
    return await read_page(body.url,body.query)
