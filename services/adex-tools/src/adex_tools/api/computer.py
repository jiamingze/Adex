"""Transport scopes precede host grants and execution."""

from uuid import UUID
from fastapi import APIRouter, Request
from adex_tools.dependencies import core
from adex_tools.computer.contracts import ComputerExecution, ComputerStep
from adex_tools.computer.service import ComputerService

router = APIRouter()


@router.get("/internal/computer/status")
async def status(request: Request):
    claims = core.require(request, "app", "computer:read")
    return await ComputerService(core).status(UUID(claims["owner"]))


@router.post("/internal/computer/observe")
async def observe(request: Request, body: ComputerExecution):
    claims = core.require(request, "agent", "computer:operate", body.run_id)
    return await ComputerService(core).observe(UUID(claims["owner"]), body.model_dump())


@router.post("/internal/computer/step")
async def step(request: Request, body: ComputerStep):
    claims = core.require(request, "agent", "computer:operate", body.run_id)
    return await ComputerService(core).step(UUID(claims["owner"]), body.model_dump(mode="json"))
