"""Workspace HTTP adapter; scopes are checked before invoking capabilities."""

from adex_tools.workspace import service
from fastapi import APIRouter, Request
from adex_tools.dependencies import core
from adex_tools.api.schemas import FileExtract, GameSource, TextArtifact

router = APIRouter()


@router.post("/internal/files/extract")
async def file_extract(request: Request, body: FileExtract):
    claims = core.require(request, "agent", "file:read", body.file_id)
    return await service.file_extract(core, claims, body)


@router.post("/internal/game/check")
async def check_game(request: Request, body: GameSource):
    claims = core.require(request, "agent", "code:check")
    return await service.check_game(core, claims, body)


@router.post("/internal/artifacts/import")
async def import_artifact(request: Request, body: TextArtifact):
    claims = core.require(request, "agent", "artifact:write")
    return await service.import_artifact(core, claims, body)
