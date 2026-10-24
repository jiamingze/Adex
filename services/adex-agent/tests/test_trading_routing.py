"""Regression for the actual interactive entry point, not just browser classification."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from adex_agent.execution.interactive import InteractiveTurnService


def trading_followup_messages(latest):
    return [
        {"role": "user", "content": "帮我下一个黄金交易"},
        {"role": "assistant", "content": "请提供方向并确认是否打开ChatGPT客户端"},
        {"role": "user", "content": "有没有挂单建议"},
        {"role": "user", "content": "你跳ChatGPT的客户端把截图信息给他让他给你建议"},
        {"role": "user", "content": latest},
    ]


@pytest.mark.parametrize("latest", ["有没有挂单建议", "浏览器都行你决定", "你来决定，继续分析"])
async def test_trade_followups_never_return_to_generic_computer_or_confirmation(monkeypatch, latest):
    for module, name in [("adex_agent.actions.planner", "task_action"), ("adex_agent.routing.browser", "route_request")]:
        monkeypatch.setattr(f"{module}.{name}", AsyncMock(side_effect=AssertionError("wrong route")))
    class Runtime:
        working = AsyncMock(side_effect=lambda context: context)
        interactive_messages = AsyncMock(return_value=[])
    body = SimpleNamespace(model=None, context={"messages": trading_followup_messages(latest)},
                           invocation_key="followup-fixture", owner_id="fixture", web_search=False)
    core = SimpleNamespace(query=AsyncMock(return_value={"cards": []}))
    events = [json.loads(e) async for e in InteractiveTurnService(core, Runtime()).events(body)]
    assert events[-1]["type"] == "completed"
    assert "请提供" not in events[-1]["content"] and "请确认" not in events[-1]["content"]
    assert not any(e["type"] == "task.action.requested" for e in events)


async def test_workflow_explanation_needs_no_browser_or_market_reread():
    body = SimpleNamespace(model=None, context={"messages": [
        {"role": "user", "content": "帮我下一个黄金交易"},
        {"role": "user", "content": "你知道怎么下单吗，说明下单流程"},
    ]})
    events = [json.loads(e) async for e in InteractiveTurnService(None, SimpleNamespace()).events(body)]
    assert events[0]["type"] == "completed" and "研究步骤无需逐次确认" in events[0]["content"]
    assert "尚未接入实盘" in events[0]["content"]


@pytest.mark.parametrize("text", ["帮我下单xauusd", "用mt5下单安", "用MT5", "帮我下一单黄金的交易", "帮我做多黄金", "做空伦敦金", "下个现货黄金挂单"])
async def test_native_mt5_precedes_generic_planners_and_returns_terminal_progress(monkeypatch, text):
    for module, name in [
        ("adex_agent.actions.planner", "task_action"),
        ("adex_agent.routing.browser", "route_request"),
        ("adex_agent.routing.productivity", "todo_draft"),
    ]:
        monkeypatch.setattr(f"{module}.{name}", AsyncMock(side_effect=AssertionError("wrong route")))
    messages = [
        {"role": "assistant", "content": "网页助手 https://www.futunn.com/"},
        {"role": "user", "content": text},
    ]
    class Runtime:
        working = AsyncMock(side_effect=lambda context: context)
        interactive_messages = AsyncMock(return_value=[])
        async def invoke(self, *args):
            yield {"type": "completed", "content": "MT5订单尚未提交"}
    body = SimpleNamespace(model=None, context={"messages": messages}, invocation_key="mt5-fixture",
                           owner_id="fixture-owner", web_search=False)
    core = SimpleNamespace(query=AsyncMock(return_value={"cards": []}))
    events = [json.loads(e) async for e in InteractiveTurnService(core, Runtime()).events(body)]
    assert events[-1]["type"] == "completed"
    assert not any(e["type"] in {"task.requested", "task.action.requested"} for e in events)
    progress = " ".join(e.get("text", "") for e in events)
    assert "MT5" in progress
    assert not any(word in progress for word in ("景点", "路线", "网页"))


async def test_recurring_mt5_read_request_keeps_existing_scheduler_route(monkeypatch):
    action = {"tool": "schedule.create", "arguments": {"title": "TEST_FIXTURE XAUUSD监控"}}
    planner = AsyncMock(return_value=action)
    monkeypatch.setattr("adex_agent.actions.planner.task_action", planner)
    body = SimpleNamespace(model=None, context={"messages": [{
        "role": "user", "content": "每10分钟帮我监控MT5上的XAUUSD价格",
    }]})
    events = [json.loads(e) async for e in InteractiveTurnService(None, SimpleNamespace()).events(body)]
    assert events == [{"type": "task.action.requested", "action": action}]
    planner.assert_awaited_once()
