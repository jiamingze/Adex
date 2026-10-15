"""Authenticated transport for the generic browser operator; no business orchestration."""

from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from adex_tools.dependencies import core
from adex_tools.browser.service import BrowserService
from adex_tools.browser.policy import BrowserStep

router = APIRouter()


class Execution(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: UUID
    epoch: int = Field(ge=1)
    attempt_id: UUID


class Ensure(Execution):
    conversation_id: UUID
    url: str = Field(min_length=1, max_length=2000)


class Step(Execution):
    observation_id: str = Field(max_length=100)
    command_key: str = Field(min_length=1, max_length=100)
    step: BrowserStep


class Control(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal[
        "dialog_accept",
        "dialog_dismiss",
        "switch_tab",
        "remember",
        "recover",
        "reject",
        "takeover",
        "observe",
        "click",
        "point",
        "type",
        "key",
        "scroll",
        "navigate",
        "back",
        "resume",
    ]
    dialog_id: str = Field(default="", max_length=100)
    profile_revision: int = Field(default=0, ge=0)
    element_id: str = Field(default="", max_length=100)
    text: str = Field(default="", max_length=16000)
    url: str = Field(default="", max_length=2000)
    x: int = Field(default=0, ge=0, le=1099)
    y: int = Field(default=0, ge=0, le=779)


@router.get("/internal/browser/sessions")
async def sessions(request: Request):
    c = core.require(request, "app", "browser:read")
    return jsonable_encoder(await BrowserService(core).list(UUID(c["owner"])))


@router.get("/internal/browser/sessions/{session}")
async def view(request: Request, session: UUID):
    c = core.require(request, "app", "browser:read", session)
    return jsonable_encoder(await BrowserService(core).view(UUID(c["owner"]), session))


@router.post("/internal/browser/sessions/{session}/control")
async def control(request: Request, session: UUID, body: Control):
    c = core.require(request, "app", "browser:control", session)
    return jsonable_encoder(
        await BrowserService(core).control(UUID(c["owner"]), session, body.model_dump(mode="json"))
    )


@router.post("/internal/browser/sessions/{session}/close")
async def close(request: Request, session: UUID):
    c = core.require(request, "app", "browser:control", session)
    return await BrowserService(core).close(UUID(c["owner"]), session)


@router.post("/internal/browser/operator/ensure")
async def ensure(request: Request, body: Ensure):
    c = core.require(request, "agent", "browser:operate", body.run_id)
    row = await BrowserService(core).ensure(UUID(c["owner"]), body.model_dump(mode="json"))
    return {"id": str(row["id"]), "status": row["status"]}


@router.post("/internal/browser/operator/{session}/observe")
async def observe(request: Request, session: UUID, body: Execution):
    c = core.require(request, "agent", "browser:operate", body.run_id)
    service = BrowserService(core)
    row = await service.own(UUID(c["owner"]), session)
    if row["status"] == "HUMAN":
        return {"id": str(session), "status": "HUMAN", "nodes": []}
    result = await service.observe(UUID(c["owner"]), session, body.model_dump(mode="json"))
    result.pop("screenshot", None)
    return jsonable_encoder(result)


@router.post("/internal/browser/operator/{session}/step")
async def step(request: Request, session: UUID, body: Step):
    c = core.require(request, "agent", "browser:operate", body.run_id)
    value = body.model_dump(mode="json")
    return jsonable_encoder(
        await BrowserService(core).step(
            UUID(c["owner"]),
            session,
            {k: value[k] for k in ("run_id", "epoch", "attempt_id")},
            value,
            body.command_key,
        )
    )


@router.get("/internal/browser/accounts")
async def accounts(request: Request):
    from adex_tools.browser.profiles import BrowserProfiles

    c = core.require(request, "app", "browser:read")
    return jsonable_encoder(await BrowserProfiles(core).list(UUID(c["owner"])))


@router.post("/internal/browser/accounts/{profile}/revoke")
async def revoke_profile(request: Request, profile: UUID):
    from adex_tools.browser.profiles import BrowserProfiles

    c = core.require(request, "app", "browser:control", profile)
    owner = UUID(c["owner"])
    rows = await BrowserProfiles(core).revoke(owner, profile)
    for row in rows:
        await BrowserService(core).close(owner, row["id"])
    return {"revoked": True, "runs": [str(row["run_id"]) for row in rows]}
