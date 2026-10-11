"""Retrieval HTTP adapter; scopes are checked before invoking capabilities."""

from uuid import UUID
from fastapi import APIRouter, Request, HTTPException
from adex_tools.dependencies import core
from adex_tools.retrieval.search import web_search, SearchUnavailable
from adex_tools.api.schemas import Search, TravelRequest, VisionRequest, WeatherRequest, BrowserRead
from adex_tools.retrieval.budget import reserve_search

router = APIRouter()


@router.post("/internal/search")
async def search(request: Request, body: Search):
    claims = core.require(request, "agent", "search:read")
    UUID(claims["owner"])
    await reserve_search(claims["owner"])
    try:
        return await web_search(body.query)
    except SearchUnavailable as exc:
        raise HTTPException(503, detail=str(exc)) from None


@router.get("/internal/catalog")
async def catalog(request: Request):
    core.require(request, "agent", "search:read")
    return {
        "tools": [{"id": "web.search", "side_effect": "READ", "availability": "AUTHENTICATED_API"}],
        "external_write_tools": "CALDAV_APPROVAL_REQUIRED",
    }


@router.post("/internal/music/search")
async def music(request: Request, body: Search):
    core.require(request, "app", "music:read")
    from adex_tools.retrieval.music import catalog_search

    return await catalog_search(body.query)


@router.post("/internal/monitor/search")
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


@router.post("/internal/research")
async def research_search(request: Request, body: Search):
    claims = core.require(request, "agent", "search:read")
    await reserve_search(claims["owner"], 3)
    from adex_tools.retrieval.research import research

    try:
        return await research(body.query)
    except SearchUnavailable as exc:
        raise HTTPException(503, str(exc)) from None


@router.post("/internal/travel")
async def travel(request: Request, body: TravelRequest):
    claims = core.require(request, "agent", "travel:read")
    await reserve_search(claims["owner"], 2)
    from adex_tools.retrieval.travel import plan_evidence

    try:
        return await plan_evidence(body.city, body.start, body.end)
    except ValueError:
        raise HTTPException(400, "INVALID_TRAVEL_DATES") from None


@router.post("/internal/vision")
async def vision(request: Request, body: VisionRequest):
    claims = core.require(request, "agent", "vision:read", body.file_id)
    await reserve_search(claims["owner"])
    from adex_tools.retrieval.vision import understand

    return await understand(core, UUID(claims["owner"]), body.file_id, body.prompt)


@router.post("/internal/music/catalog")
async def agent_music(request: Request, body: Search):
    core.require(request, "agent", "music:read")
    from adex_tools.retrieval.music import catalog_search

    return await catalog_search(body.query)


@router.post("/internal/monitor/weather")
async def monitor_weather(request: Request, body: WeatherRequest):
    core.require(request, "automation", "monitor:read")
    from adex_tools.retrieval.weather import current_weather

    return await current_weather(body.latitude, body.longitude)


@router.post("/internal/browser/read")
async def browser_read(request: Request, body: BrowserRead):
    from adex_tools.runners.browser import read_page

    claims = core.require(request, "agent", "search:read")
    UUID(claims["owner"])
    await reserve_search(claims["owner"])
    return await read_page(body.url, body.query)
