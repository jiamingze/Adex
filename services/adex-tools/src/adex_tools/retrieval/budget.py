"""Atomic per-owner tool reservations; cache is never the authority."""

from fastapi import HTTPException
from adex_tools.dependencies import core


async def reserve_search(owner, count=1):
    from datetime import datetime, timezone

    row = await core.query(
        "INSERT INTO search_budgets(owner_key,day,calls) VALUES(%s,%s,%s) ON CONFLICT(owner_key,day) DO UPDATE SET calls=search_budgets.calls+excluded.calls WHERE search_budgets.calls+excluded.calls<=80 RETURNING calls",
        (str(owner), datetime.now(timezone.utc).date(), count),
        one=True,
    )
    if not row:
        raise HTTPException(429, "SEARCH_BUDGET_EXCEEDED")
