"""Usage HTTP adapter; scopes are checked before invoking capabilities."""

from uuid import UUID
from fastapi import APIRouter, Request
from adex_tools.dependencies import core

router = APIRouter()


@router.get("/internal/usage")
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
