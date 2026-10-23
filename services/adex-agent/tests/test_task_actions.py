from uuid import uuid4
import pytest
from adex_agent.actions.contracts import validate_action
from adex_agent.actions.planner import plan_task


def snapshot():
    return {
        "request": "把新闻任务改到晚上七点",
        "now": "2026-10-22T09:00:00+08:00",
        "schedules": [
            {"id": str(uuid4()), "title": "新闻", "revision": 3, "status": "ACTIVE", "kind": "DAILY"}
        ],
        "todos": [],
    }


def test_tool_registry_rejects_unknown_arguments_and_unobserved_targets():
    data = snapshot()
    with pytest.raises(ValueError):
        validate_action({"tool": "shell", "arguments": {"command": "rm"}}, data)
    with pytest.raises(ValueError):
        validate_action(
            {"tool": "schedule.update", "target_id": str(uuid4()), "arguments": {"title": "x"}}, data
        )
    with pytest.raises(ValueError):
        validate_action(
            {
                "tool": "schedule.update",
                "target_id": data["schedules"][0]["id"],
                "arguments": {"owner_id": str(uuid4())},
            },
            data,
        )
    call = validate_action(
        {
            "tool": "schedule.update",
            "target_id": data["schedules"][0]["id"],
            "arguments": {"local_time": "19:00"},
        },
        data,
    )
    assert call["arguments"]["revision"] == 3


def test_duplicate_names_require_clarification_instead_of_guessing():
    data = snapshot()
    data["schedules"].append({**data["schedules"][0], "id": str(uuid4())})
    result = validate_action(
        {
            "tool": "schedule.update",
            "target_id": data["schedules"][0]["id"],
            "arguments": {"local_time": "19:00"},
        },
        data,
    )
    assert result["tool"] == "clarify"


async def test_malformed_proposal_is_repaired_once_without_dispatch():
    calls = []

    class Runtime:
        async def invoke(self, key, owner, messages):
            calls.append(messages)
            yield {
                "type": "completed",
                "content": "not json"
                if len(calls) == 1
                else '{"tool":"clarify","message":"你指哪一条新闻任务？"}',
            }

    result = await plan_task(Runtime(), "owner", "key", snapshot())
    assert result["tool"] == "clarify" and len(calls) == 2
    assert "校验失败" in calls[1][-1]["content"]


def test_frequency_changes_cannot_silently_ignore_incompatible_timing():
    data = snapshot()
    for arguments in ({"kind": "INTERVAL"}, {"kind": "ONCE", "local_time": "19:00"}):
        with pytest.raises(ValueError):
            validate_action(
                {"tool": "schedule.update", "target_id": data["schedules"][0]["id"], "arguments": arguments},
                data,
            )


async def test_chrome_search_repair_preserves_goal_without_schedule_fields():
    import json

    request = "帮我打开Mac上的浏览器Chrome浏览器然后搜一下CET版结果给我"
    calls = []

    class Runtime:
        async def invoke(self, key, owner, messages):
            calls.append(messages)
            yield {
                "type": "completed",
                "content": json.dumps(
                    {
                        "tool": "computer.start",
                        "arguments": {
                            "goal": request,
                            "app_name": "Chrome",
                            **({"query": "CET版"} if len(calls) == 1 else {}),
                        },
                    },
                    ensure_ascii=False,
                ),
            }

    result = await plan_task(
        Runtime(), "owner", "chrome-repair", {"request": request, "todos": [], "schedules": []}
    )
    assert result["tool"] == "computer.start"
    assert result["arguments"] == {"goal": request, "app_name": "Chrome"}
    assert "extra_forbidden" in calls[1][-1]["content"]
    assert calls[1][-2]["role"] == "assistant"


async def test_failed_parameters_do_not_invent_a_schedule_requirement():
    class Runtime:
        async def invoke(self, *args):
            yield {"type": "completed", "content": "{}"}

    result = await plan_task(Runtime(), "owner", "failure", {"request": "打开Chrome搜索CET版"})
    assert "事项及时间" not in result["message"]
    assert "尚未执行" in result["message"]
