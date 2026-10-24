from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from adex_agent.skills.registry import REGISTRY, SkillRegistry
from adex_agent.skills.travel import requested_days
from adex_agent.execution.context import ContextService


async def test_trading_skill_observes_terminal_without_claiming_execution():
    plan = REGISTRY.resolve("MT5看一下XAUUSD的1分钟、5分钟、4小时图")
    assert plan.skill.id == "trading.mt5-research"
    assert plan.search_queries == ()
    core = SimpleNamespace(call=AsyncMock(return_value={
        "mode": "TERMINAL_READ_ONLY", "symbol": "XAUUSD", "broker_executed": False,
        "frames": {name: [{"close": i} for i in range(120)] for name in ("M1", "M5", "H4")},
    }))
    messages = await ContextService(core).messages({
        "owner_id": str(uuid4()), "messages": [{"role": "user", "content": "MT5分析XAUUSD"}],
    })
    assert "TERMINAL_READ_ONLY" in messages[0]["content"]
    assert "不具备实盘提交接口" in messages[0]["content"]
    assert core.call.await_args.args[3] == "/internal/trading/context"


async def test_trading_read_failure_is_not_fake_market_evidence():
    core = SimpleNamespace(call=AsyncMock(side_effect=RuntimeError("private detail")))
    messages = await ContextService(core).messages({
        "owner_id": str(uuid4()), "messages": [{"role": "user", "content": "MT5分析XAUUSD"}],
    })
    assert "BLOCKED_EXTERNAL" in messages[0]["content"]
    assert "private detail" not in messages[0]["content"]


async def test_trading_skill_has_no_required_web_search_batches():
    core = SimpleNamespace(call=AsyncMock(side_effect=[
        {"mode": "TERMINAL_READ_ONLY", "frames": {}},
        {"items": [], "fetched_at": "fixture"},
    ]))
    await ContextService(core).messages({
        "owner_id": str(uuid4()), "messages": [{"role": "user", "content": "MT5分析XAUUSD最新消息"}],
    }, search=True)
    assert core.call.await_count == 2


def test_skill_permissions_fail_closed():
    definition = REGISTRY.definitions["travel.plan"]
    with pytest.raises(ValueError, match="UNSUPPORTED"):
        SkillRegistry((replace(definition, capabilities=("payment:write",)),))
    with pytest.raises(ValueError, match="DUPLICATE"):
        SkillRegistry((definition, definition))


@pytest.mark.parametrize(
    "text,expected",
    [
        ("四天三晚", 4),
        ("十一天", 11),
        ("二十一天", 21),
        ("第十二天轻松些", None),
        ("安排7天去普吉岛", 7),
        ("两日游", 2),
        ("明天天气", None),
        ("99天", None),
    ],
)
def test_explicit_days(text, expected):
    assert requested_days(text) == expected


def test_skill_selection_and_continuation():
    original = "帮我安排七天普吉岛行程"
    plan = REGISTRY.resolve(original)
    assert plan.skill.id == "travel.plan"
    assert "第7天" in plan.policy
    assert REGISTRY.resolve("解释数据库事务") is None
    assert REGISTRY.resolve("预订酒店").requested_action == "order"
    assert REGISTRY.resolve("预约普吉岛景点").requested_action == "reservation"
    messages = [{"role": "user", "content": original}, {"role": "user", "content": "第二天改轻松一点"}]
    assert "第7天" in REGISTRY.resolve_context(messages).policy
    assert "第3天" in REGISTRY.resolve_context([messages[0], {"role": "user", "content": "改成三天"}]).policy
    messages.append({"role": "user", "content": "解释数据库事务"})
    assert REGISTRY.resolve_context(messages) is None
    assert REGISTRY.resolve_context([{"role": "assistant", "content": original}, messages[1]]) is None


async def test_travel_collects_two_grounded_batches_and_keeps_booking_disabled():
    core = SimpleNamespace(
        call=AsyncMock(
            side_effect=[
                {"items": [{"url": "https://example.com/guide"}], "fetched_at": "one"},
                {"items": [{"url": "https://example.com/hours"}], "fetched_at": "two"},
            ]
        )
    )
    cards = []
    messages = await ContextService(core).messages(
        {"owner_id": str(uuid4()), "messages": [{"role": "user", "content": "帮我安排七天普吉岛行程"}]},
        search=True,
        cards=cards,
    )
    assert core.call.await_count == 2
    assert cards[0]["data"]["skill_version"] == "1.0.0"
    assert len(cards[0]["data"]["items"]) == 2
    assert "第7天" in messages[0]["content"]
    assert "不能声称已经预约" in messages[0]["content"]


async def test_optional_search_failure_preserves_first_evidence():
    core = SimpleNamespace(
        call=AsyncMock(
            side_effect=[{"items": [{"url": "https://example.com"}]}, RuntimeError("budget exhausted")]
        )
    )
    cards = []
    await ContextService(core).messages(
        {"owner_id": str(uuid4()), "messages": [{"role": "user", "content": "规划五天旅游行程"}]},
        search=True,
        cards=cards,
    )
    assert cards[0]["data"]["partial"] is True
    assert cards[0]["data"]["items"]


async def test_frozen_skill_plan_replays_without_new_tool_calls():
    from adex_agent.execution.runtime import Runtime

    stored = {}

    async def query(sql, args, one=False):
        if sql.startswith("INSERT"):
            stored.update(owner_id=args[1], context_hash=args[2], messages=args[3].obj)
        return stored or None

    owner = uuid4()
    core = SimpleNamespace(query=query, call=AsyncMock(return_value={"items": [], "fetched_at": "fixture"}))
    runtime = Runtime.__new__(Runtime)
    runtime.core = core
    context = {
        "owner_id": str(owner),
        "memory_revision": 1,
        "messages": [{"role": "user", "content": "规划五天旅游行程"}],
    }
    first = await runtime.interactive_messages("skill-turn", owner, context, search=True)
    assert "travel.plan@1.0.0" in first[0]["content"]
    runtime.messages = AsyncMock(side_effect=AssertionError("frozen plan must be reused"))
    assert await runtime.interactive_messages("skill-turn", owner, context, search=True) == first
    assert core.call.await_count == 2
