"""Authenticated connector and action transport adapters."""

from typing import Literal
from uuid import UUID
from adex_tools.connectors.contracts import (
    OAuthStart,
    OAuthCallback,
    Query,
    ActionDraft,
    Decision,
    Execution,
    SyncExecution,
)
from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from adex_tools.dependencies import core
from adex_tools.connectors.service import ConnectorService
from adex_tools.approvals.actions import ActionService

router = APIRouter()


@router.get("/internal/connectors")
async def connections(request: Request):
    c = core.require(request, "app", "connector:read")
    return jsonable_encoder(await ConnectorService(core).list(UUID(c["owner"])))


@router.post("/internal/connectors/google/authorize")
async def authorize(request: Request, body: OAuthStart):
    c = core.require(request, "app", "connector:write")
    return await ConnectorService(core).authorize(
        UUID(c["owner"]), body.session_binding, body.service, body.access
    )


@router.post("/internal/connectors/google/callback")
async def callback(request: Request, body: OAuthCallback):
    c = core.require(request, "app", "connector:write")
    return jsonable_encoder(
        await ConnectorService(core).callback(UUID(c["owner"]), body.session_binding, body.state, body.code)
    )


@router.post("/internal/connectors/{connection_id}/revoke")
async def revoke(request: Request, connection_id: UUID):
    c = core.require(request, "app", "connector:write", connection_id)
    return await ConnectorService(core).revoke(UUID(c["owner"]), connection_id)


@router.post("/internal/connectors/{connection_id}/query")
async def query(request: Request, connection_id: UUID, body: Query):
    c = core.require(request, "app", "connector:read", connection_id)
    return await ConnectorService(core).query(
        UUID(c["owner"]), connection_id, body.model_dump(exclude_none=True)
    )


@router.post("/internal/connectors/sync")
async def sync(request: Request, body: SyncExecution):
    c = core.require(request, "agent", "connector:sync", body.connection_id)
    await core.call(
        "automation",
        "effect:execute",
        "POST",
        f"/internal/runs/{body.run_id}/authorize-effect",
        body.model_dump(mode="json"),
        owner=c["owner"],
        resource=body.run_id,
    )
    return await ConnectorService(core).sync(
        UUID(c["owner"]), body.connection_id, body.run_id, body.query.model_dump(exclude_none=True)
    )


@router.get("/internal/actions")
async def actions(request: Request):
    c = core.require(request, "app", "approval:read")
    return jsonable_encoder(await ActionService(core).list(UUID(c["owner"])))


@router.post("/internal/actions")
async def draft(request: Request, body: ActionDraft):
    c = core.require(request, "app", "approval:write")
    return jsonable_encoder(await ActionService(core).create(UUID(c["owner"]), body))


@router.post("/internal/actions/{action_id}/{decision}")
async def decide(
    request: Request, action_id: UUID, decision: Literal["approve", "revoke", "reconcile"], body: Decision
):
    c = core.require(request, "app", "approval:write", action_id)
    service = ActionService(core)
    value = (
        await service.reconcile(UUID(c["owner"]), action_id)
        if decision == "reconcile"
        else await service.decide(UUID(c["owner"]), action_id, decision, body.request_hash)
    )
    return jsonable_encoder(value)


@router.post("/internal/actions/execute")
async def execute(request: Request, body: Execution):
    c = core.require(request, "agent", "action:execute", body.approval_id)
    return await ActionService(core).execute(UUID(c["owner"]), body.approval_id, body)


@router.post("/internal/connectors/context")
async def agent_context(request: Request, body: Query):
    from datetime import datetime, timedelta, timezone
    from fastapi import HTTPException

    c = core.require(request, "agent", "connector:context")
    owner = UUID(c["owner"])
    service = ConnectorService(core)
    rows = (await service.list(owner))["items"]
    observations, blocked = [], []
    now = datetime.now(timezone.utc)
    selected = body.query  # Fixed service selector, not arbitrary provider query.
    if selected not in ("calendar", "gmail"):
        raise HTTPException(400, "INVALID_CONNECTOR_SERVICE")
    interval = {"start": now.isoformat(), "end": (now + timedelta(days=7)).isoformat()}
    for row in [x for x in rows if x["service"] == selected and x["status"] == "ACTIVE"][:1]:
        try:
            value = await service.query(
                owner, row["id"], interval if selected == "calendar" else {"query": "in:inbox"}
            )
            observations.append(
                {
                    "connection_id": str(row["id"]),
                    "service": selected,
                    "window": interval if selected == "calendar" else "latest inbox metadata, at most ten",
                    "data": value,
                }
            )
        except HTTPException as exc:
            blocked.append({"service": selected, "code": exc.detail})
    return {"observations": observations, "blocked": blocked, "writes_require_approval": True}
