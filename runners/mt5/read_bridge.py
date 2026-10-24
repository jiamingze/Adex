"""Trusted Wine-side read/preflight bridge. Deliberately exposes no order_send."""

import json
import re
import sys
from datetime import datetime, timezone


def checked(value, mt5):
    if value is None:
        # Do not turn disconnected/history errors into an empty successful account.
        raise ValueError("MT5_READ_FAILED:" + str(mt5.last_error()[0]))
    return value


def handle(body, mt5):
    if set(body) - {"command", "symbol", "bars", "order"}:
        raise ValueError("MT5_INVALID_FIELDS")
    command = body.get("command")
    if command not in {"snapshot", "check"}:
        raise ValueError("MT5_COMMAND_NOT_ALLOWED")
    symbol = body.get("symbol", "XAUUSD")
    count = body.get("bars", 120)
    if not isinstance(symbol, str) or not re.fullmatch(r"[A-Za-z0-9_.#-]{1,40}", symbol):
        raise ValueError("MT5_INVALID_SYMBOL")
    if type(count) is not int or not 10 <= count <= 500:
        raise ValueError("MT5_INVALID_BAR_COUNT")
    if not mt5.initialize(path=r"C:\Program Files\MetaTrader 5\terminal64.exe", timeout=15000):
        raise ValueError("BLOCKED_EXTERNAL:MT5_INITIALIZE:" + str(mt5.last_error()[0]))
    try:
        terminal = checked(mt5.terminal_info(), mt5)
        if not terminal.connected:
            raise ValueError("BLOCKED_EXTERNAL:MT5_DISCONNECTED")
        account = checked(mt5.account_info(), mt5)
        info = checked(mt5.symbol_info(symbol), mt5)
        tick = checked(mt5.symbol_info_tick(symbol), mt5)
        if command == "check":
            order = body.get("order", {})
            required = {"kind", "volume", "entry", "sl", "tp"}
            if set(order) != required or order["kind"] not in {
                "BUY_LIMIT", "SELL_LIMIT", "BUY_STOP", "SELL_STOP"
            }:
                raise ValueError("MT5_INVALID_ORDER")
            from decimal import Decimal

            values = {key: Decimal(str(order[key])) for key in required - {"kind"}}
            if any(not x.is_finite() or x <= 0 for x in values.values()):
                raise ValueError("MT5_INVALID_ORDER_VALUES")
            volume = values["volume"]
            if volume > Decimal("0.01") or volume < Decimal(str(info.volume_min)) or volume % Decimal(str(info.volume_step)):
                raise ValueError("MT5_VOLUME_NOT_SUPPORTED")
            request = {
                "action": mt5.TRADE_ACTION_PENDING, "symbol": symbol,
                "type": getattr(mt5, "ORDER_TYPE_" + order["kind"]),
                "volume": float(volume), "price": float(values["entry"]),
                "sl": float(values["sl"]), "tp": float(values["tp"]),
                "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_RETURN,
            }
            result = checked(mt5.order_check(request), mt5)
            return {"mode": "PREFLIGHT_ONLY", "broker_executed": False, "retcode": result.retcode,
                    "check_passed": result.retcode == 0, "comment": result.comment}
        frames = {}
        for name in ("M1", "M5", "H4"):
            rates = checked(mt5.copy_rates_from_pos(symbol, getattr(mt5, "TIMEFRAME_" + name), 0, count), mt5)
            if len(rates) < 10:
                raise ValueError("BLOCKED_EXTERNAL:MT5_HISTORY_NOT_READY:" + name)
            frames[name] = [
                {key: float(row[key]) if key in {"open", "high", "low", "close"} else int(row[key])
                 for key in ("time", "open", "high", "low", "close", "tick_volume", "spread")}
                for row in rates
            ]
        orders = checked(mt5.orders_get(symbol=symbol), mt5)
        return {
            "mode": "TERMINAL_READ_ONLY", "broker_executed": False,
            "observed_at_utc": datetime.now(timezone.utc).isoformat(),
            "broker_time_basis": "RAW_TERMINAL_EPOCH_OFFSET_NOT_INFERRED",
            "connected": True,
            "account_mode": "DEMO" if account.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO else "NON_DEMO",
            "account_mask": "***" + str(account.login)[-4:],
            "symbol": symbol, "bid": tick.bid, "ask": tick.ask, "tick_time_raw": tick.time,
            "specification": {key: getattr(info, key) for key in (
                "digits", "point", "trade_tick_size", "volume_min", "volume_step", "volume_max",
                "trade_stops_level", "trade_freeze_level", "trade_mode", "trade_contract_size")},
            "frames": frames,
            "orders": [{key: getattr(o, key) for key in (
                "ticket", "magic", "type", "volume_current", "price_open", "sl", "tp", "time_expiration")}
                for o in orders],
        }
    finally:
        mt5.shutdown()


def main():
    try:
        import MetaTrader5 as mt5

        raw = sys.stdin.buffer.read(16385)
        if len(raw) > 16384:
            raise ValueError("MT5_REQUEST_TOO_LARGE")
        print(json.dumps({"ok": True, "result": handle(json.loads(raw), mt5)}, allow_nan=False))
    except Exception as error:
        # Unknown exceptions may contain private terminal paths; expose type only.
        code = str(error) if isinstance(error, ValueError) else type(error).__name__
        print(json.dumps({"ok": False, "code": code[:200]}))


if __name__ == "__main__":
    main()
