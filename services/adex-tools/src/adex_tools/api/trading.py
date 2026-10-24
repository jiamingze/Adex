"""Owner-bound terminal observations; no trading execution HTTP endpoint."""

import asyncio
import os
from uuid import UUID
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from adex_tools.dependencies import core
from adex_tools.computer.service import ComputerService
from adex_tools.trading.bridge import Mt5ReadBridge

router = APIRouter()
_terminal_lock = asyncio.Lock()


class TradingQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str = Field(default="XAUUSD", pattern=r"^[A-Za-z0-9_.#-]{1,40}$")


@router.post("/internal/trading/context")
async def context(request: Request, body: TradingQuery):
    claims = core.require(request, "agent", "trading:read")
    ComputerService(core).grant(UUID(claims["owner"]))
    if (
        os.getenv("ADEX_COMPUTER_TEST_FIXTURE") == "true"
        and os.getenv("ADEX_MT5_TEST_READ_ALLOWED") != "true"
    ):
        raise HTTPException(503, "BLOCKED_EXTERNAL:MT5_DISABLED_IN_FIXTURE")
    # This host's terminal session is shared. Serialize local calls; no DB locks
    # are held across terminal IPC. Cross-process exclusion is in the bridge port.
    if _terminal_lock.locked():
        raise HTTPException(429, "MT5_TERMINAL_BUSY")
    async with _terminal_lock:
        try:
            return await Mt5ReadBridge().call(body.symbol)
        except (ValueError, TimeoutError) as error:
            raise HTTPException(503, "BLOCKED_EXTERNAL:MT5_READ_UNAVAILABLE") from error
