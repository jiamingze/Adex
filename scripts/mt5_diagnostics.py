"""Read installed MT5 or preflight a JSON order without submitting it.

Run with: uv run --project services/adex-tools python scripts/mt5_diagnostics.py
"""

import argparse
import asyncio
import json
from pathlib import Path
from adex_tools.trading.bridge import Mt5ReadBridge
from adex_tools.trading.contracts import Order


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--preflight", type=Path, help="JSON Order file; checks only, never submits")
    args = parser.parse_args()
    order = Order.model_validate_json(args.preflight.read_text()) if args.preflight else None
    try:
        result = await Mt5ReadBridge().call(args.symbol, order=order)
    except (ValueError, TimeoutError) as error:
        raise SystemExit(str(error)) from error
    if order:
        print(json.dumps(result))
    else:
        # Do not print balances, tickets, full account IDs or raw account data.
        print(json.dumps({
            "mode": result["mode"], "connected": result["connected"],
            "account_mode": result["account_mode"], "symbol": result["symbol"],
            "broker_executed": result["broker_executed"],
            "frame_counts": {key: len(value) for key, value in result["frames"].items()},
            "pending_order_count": len(result["orders"]),
            "broker_time_basis": result["broker_time_basis"],
        }, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
