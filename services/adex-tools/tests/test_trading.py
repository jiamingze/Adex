"""No terminal access: proposal approval and broker constraint regression."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from adex_tools.trading.contracts import Order, Proposal, Snapshot
from adex_tools.trading.simulator import Simulator, proposal_hash


def bridge_module():
    import importlib.util
    from pathlib import Path
    source = Path(__file__).resolve().parents[3] / "runners/mt5/read_bridge.py"
    spec = importlib.util.spec_from_file_location("test_mt5_read_bridge", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_native_bridge_rejects_writes_before_opening_terminal():
    from types import SimpleNamespace
    from unittest.mock import Mock
    mt5 = SimpleNamespace(initialize=Mock())
    for body in [{"command": "order_send"}, {"command": "cancel"}, {"command": "snapshot", "code": "x"}]:
        with pytest.raises(ValueError):
            bridge_module().handle(body, mt5)
    mt5.initialize.assert_not_called()


def test_native_read_failure_is_not_an_empty_success():
    from types import SimpleNamespace
    from unittest.mock import Mock
    mt5 = SimpleNamespace(initialize=Mock(return_value=True),
                          terminal_info=Mock(return_value=None), last_error=lambda: (-1, "private"), shutdown=Mock())
    with pytest.raises(ValueError, match="MT5_READ_FAILED"):
        bridge_module().handle({"command": "snapshot"}, mt5)
    mt5.shutdown.assert_called_once()


def test_native_preflight_has_no_submit_or_cancel_side_effect():
    from types import SimpleNamespace
    from unittest.mock import Mock
    mt5 = SimpleNamespace(
        initialize=Mock(return_value=True), terminal_info=lambda: SimpleNamespace(connected=True),
        account_info=lambda: SimpleNamespace(),
        symbol_info=lambda symbol: SimpleNamespace(volume_min=0.01, volume_step=0.01),
        symbol_info_tick=lambda symbol: SimpleNamespace(),
        order_check=Mock(return_value=SimpleNamespace(retcode=0, comment="fixture")),
        order_send=Mock(side_effect=AssertionError("must never send")), shutdown=Mock(),
        TRADE_ACTION_PENDING=5, ORDER_TYPE_BUY_LIMIT=2, ORDER_TIME_GTC=0, ORDER_FILLING_RETURN=2,
    )
    result = bridge_module().handle({
        "command": "check", "order": {"kind": "BUY_LIMIT", "volume": "0.01",
                                     "entry": "2590", "sl": "2580", "tp": "2610"},
    }, mt5)
    assert result["mode"] == "PREFLIGHT_ONLY" and result["broker_executed"] is False
    mt5.order_check.assert_called_once()
    mt5.order_send.assert_not_called()
    mt5.shutdown.assert_called_once()


async def test_terminal_read_endpoint_enforces_host_owner_before_runner(monkeypatch):
    from types import SimpleNamespace
    from uuid import uuid4
    from unittest.mock import AsyncMock
    from fastapi import HTTPException
    monkeypatch.setenv("ADEX_TOOLS_KEY", "local-unit-fixture-key-" * 3)
    monkeypatch.setenv("ADEX_DB_URL", "postgresql://localhost/adex_test_unit")
    from adex_tools.api import trading
    owner = uuid4()
    monkeypatch.setenv("ADEX_COMPUTER_ENABLED", "true")
    monkeypatch.setenv("ADEX_COMPUTER_OWNER_ID", str(uuid4()))
    monkeypatch.setattr(trading, "core", SimpleNamespace(require=lambda *args: {"owner": str(owner)}))
    call = AsyncMock()
    monkeypatch.setattr(trading.Mt5ReadBridge, "call", call)
    with pytest.raises(HTTPException) as exc:
        await trading.context(None, trading.TradingQuery())
    assert exc.value.status_code == 403
    call.assert_not_called()


def snapshot():
    return Snapshot(
        account_ref="demo:1234", strategy_id=18, symbol="XAUUSD",
        observed_at=datetime.now(timezone.utc), bid="2600", ask="2601",
        tick_size="0.01", volume_min="0.01", volume_step="0.01",
        stops_distance="0.1", orders={"77": 18, "88": 99},
    )


def proposal(s, **changes):
    return Proposal(
        snapshot_hash=s.digest(), expires_at=datetime.now(timezone.utc) + timedelta(minutes=2),
        analysis="SETUP", cancel_tickets=["77"],
        new_orders=[Order(kind="BUY_LIMIT", volume="0.01", entry="2590", sl="2580", tp="2610")],
        **changes,
    )


def test_simulation_explicit_receipt_replays_without_duplicate_legs():
    s = snapshot()
    p = proposal(s)
    engine = Simulator()
    a = engine.execute(s, p, proposal_hash(p))
    assert a["mode"] == "SIMULATION" and a["broker_executed"] is False
    assert a["cancelled"] == ["77"] and len(a["created"]) == 1
    assert engine.execute(s, p, proposal_hash(p)) == a


def test_changed_snapshot_and_wrong_approval_fail_closed():
    s = snapshot()
    p = proposal(s)
    with pytest.raises(ValueError, match="APPROVAL"):
        Simulator().execute(s, p, "0" * 64)
    changed = s.model_copy(update={"bid": Decimal("2602")})
    with pytest.raises(ValueError, match="SNAPSHOT"):
        Simulator().execute(changed, p, proposal_hash(p))


def test_no_setup_is_cancel_only_but_unknown_changes_nothing():
    s = snapshot()
    p = proposal(s).model_copy(update={"analysis": "NO_SETUP", "new_orders": []})
    assert Simulator().execute(s, p, proposal_hash(p))["created"] == []
    p = p.model_copy(update={"analysis": "UNKNOWN"})
    with pytest.raises(ValueError, match="ANALYSIS"):
        Simulator().execute(s, p, proposal_hash(p))


@pytest.mark.parametrize("change,code", [
    ({"cancel_tickets": ["88"]}, "OWNERSHIP"),
    ({"expires_at": datetime.now(timezone.utc)-timedelta(seconds=1)}, "EXPIRED"),
    ({"new_orders": [Order(kind="BUY_LIMIT", volume="0.01", entry="2590", sl="2595", tp="2610")]}, "LEVELS"),
])
def test_invalid_proposals_do_not_execute(change, code):
    s = snapshot()
    p = proposal(s).model_copy(update=change)
    with pytest.raises(ValueError, match=code):
        Simulator().execute(s, p, proposal_hash(p))


def test_stale_quote_minimum_and_step_never_round_up():
    for change in [
        {"observed_at": datetime.now(timezone.utc)-timedelta(minutes=3)},
        {"volume_min": Decimal("0.1")}, {"volume_step": Decimal("0.03")},
    ]:
        s = snapshot().model_copy(update=change)
        p = proposal(s)
        with pytest.raises(ValueError):
            Simulator().execute(s, p, proposal_hash(p))
    for volume in ["0.02", "0", "NaN", "Infinity"]:
        with pytest.raises(ValueError):
            Order(kind="BUY_LIMIT", volume=volume, entry="2590", sl="2580", tp="2610")
