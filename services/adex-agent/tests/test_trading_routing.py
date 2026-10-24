"""Regression for the actual interactive entry point, not just browser classification."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from adex_agent.execution.interactive import InteractiveTurnService


@pytest.mark.parametrize("text", ["帮我下单xauusd", "用mt5下单安", "用MT5"])
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
