"""Approvals HTTP adapter; scopes are checked before invoking capabilities."""

from uuid import UUID
from fastapi import APIRouter, Request, HTTPException
from fastapi.encoders import jsonable_encoder
from adex_tools.dependencies import core
from adex_tools.api.schemas import CalendarRequest, CalendarExecution

router = APIRouter()


@router.get("/internal/approvals")
async def approvals(request: Request):
    claims = core.require(request, "app", "approval:read")
    rows = await core.query(
        "SELECT * FROM approvals WHERE owner_id=%s ORDER BY created_at DESC LIMIT 100",
        (UUID(claims["owner"]),),
    )

    return jsonable_encoder({"items": rows})


@router.post("/internal/approvals")
async def approval(request: Request, body: CalendarRequest):
    from adex_tools.approvals.calendar import create_approval

    claims = core.require(request, "app", "approval:write")
    return jsonable_encoder(await create_approval(core, UUID(claims["owner"]), body.model_dump(mode="json")))


@router.post("/internal/approvals/{approval_id}/{action}")
async def approval_action(request: Request, approval_id: UUID, action: str):
    from adex_tools.approvals.calendar import act

    if action not in ("approve", "revoke", "reconcile"):
        raise HTTPException(400, "INVALID_ACTION")
    claims = core.require(request, "app", "approval:write", approval_id)
    if action == "reconcile":
        from adex_tools.approvals.calendar import reconcile

        return await reconcile(core, UUID(claims["owner"]), approval_id)
    return await act(core, UUID(claims["owner"]), approval_id, action)


@router.post("/internal/calendar/execute")
async def calendar_execute(request: Request, body: CalendarExecution):
    from adex_tools.approvals.calendar import act

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
