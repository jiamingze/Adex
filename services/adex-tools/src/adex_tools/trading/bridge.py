"""Bounded local MT5 subprocess; no shell, arbitrary methods or credential transport."""

import asyncio
import json
import os
from pathlib import Path
from .contracts import Order


class Mt5ReadBridge:
    def __init__(self, root: Path | None = None):
        self.root = root or Path(__file__).resolve().parents[5]

    async def call(self, symbol: str = "XAUUSD", bars: int = 120, order: Order | None = None) -> dict:
        import fcntl

        folder = self.root / ".local-data/mt5"
        folder.mkdir(parents=True, mode=0o700, exist_ok=True)
        with (folder / "terminal.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ValueError("MT5_TERMINAL_BUSY") from error
            try:
                return await self._call(symbol, bars, order)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    async def _call(self, symbol, bars, order):
        import re

        if (
            not re.fullmatch(r"[A-Za-z0-9_.#-]{1,40}", symbol)
            or type(bars) is not int
            or not 10 <= bars <= 500
        ):
            raise ValueError("MT5_INVALID_REQUEST")
        prefix = Path.home() / "Library/Application Support/net.metaquotes.wine.metatrader5"
        wine = Path("/Applications/MetaTrader 5.app/Contents/SharedSupport/wine/bin/wine")
        python = prefix / "drive_c/adex-python/python.exe"
        runner = self.root / "runners/mt5/read_bridge.py"
        if not all(p.is_file() for p in (wine, python, runner)):
            raise ValueError("BLOCKED_EXTERNAL:MT5_BRIDGE_NOT_INSTALLED")
        body = {"command": "check" if order else "snapshot", "symbol": symbol, "bars": bars}
        if order:
            body["order"] = Order.model_validate(order.model_dump()).model_dump(mode="json")
        process = await asyncio.create_subprocess_exec(
            str(wine),
            str(python),
            "Z:" + str(runner).replace("/", "\\"),
            env={**os.environ, "WINEPREFIX": str(prefix), "WINEDEBUG": "-all"},
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            output, _ = await asyncio.wait_for(process.communicate(json.dumps(body).encode()), 45)
        except BaseException:
            if process.returncode is None:
                process.kill()
            await process.wait()
            raise
        if process.returncode or len(output) > 2_000_000:
            raise ValueError("BLOCKED_EXTERNAL:MT5_BRIDGE_FAILED")
        result = json.loads(output)
        if not result.get("ok"):
            raise ValueError(result.get("code", "MT5_BRIDGE_ERROR"))
        return result["result"]
