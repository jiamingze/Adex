import pytest
from adex_agent.browser.workflow import parse_step
from adex_agent.models.provider import ProviderFailure


def test_planner_cannot_approve_execute_or_supply_secrets():
    for text in [
        '{"action":"approve"}',
        '{"action":"click","approved":true}',
        '{"action":"evaluate","text":"fetch()"}',
    ]:
        with pytest.raises(ProviderFailure):
            parse_step(text)
    assert parse_step('```json\n{"action":"handoff"}\n```')["action"] == "handoff"


def test_completion_reports_only_verified_receipt_fields_not_invented_links():
    from adex_agent.browser.workflow import completed_message

    text = completed_message(
        [{"provider_receipt": "TEST_NOTE", "test_fixture": True, "title": "TEST_FIXTURE Adex"}]
    )
    assert "TEST_FIXTURE" in text and "提交标题" in text and "https://" not in text
    text = completed_message(
        [
            {
                "provider_receipt": "TEST_NOTE",
                "title": "TEST_FIXTURE Adex",
                "permalink": "https://example.com/note/TEST_NOTE",
                "permalink_verified": False,
            }
        ]
    )
    assert "未单独打开核验" in text


@pytest.mark.parametrize(
    "code",
    ["BROWSER_APPROVAL_REQUIRED", "BROWSER_APPROVAL_OR_HANDOFF_REQUIRED", "BROWSER_CONTROL_MODE_CHANGED"],
)
async def test_network_approval_race_suspends_same_run_without_retrying_step(code):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from fastapi import HTTPException
    from adex_agent.browser.workflow import BrowserWorkflow

    observations = iter(
        [
            {"status": "AGENT", "observation_id": "before", "nodes": []},
            {"status": "WAITING_APPROVAL", "observation_id": "after", "action_id": "approval"},
        ]
    )
    calls = []

    async def call(service, scope, method, path, body, **kwargs):
        calls.append(path)
        if path.endswith("/ensure"):
            return {"id": "session"}
        if path.endswith("/observe"):
            return next(observations)
        raise HTTPException(409, code)

    worker = SimpleNamespace(
        core=SimpleNamespace(call=call),
        runtime=None,
        checkpoints=SimpleNamespace(save_checkpoint=AsyncMock(return_value="checkpoint")),
        run_write=AsyncMock(),
    )
    workflow = BrowserWorkflow(worker)
    workflow.plan = AsyncMock(return_value={"action": "click", "element_id": "observed-button"})
    result = await workflow.run(
        {
            "id": "run",
            "owner_id": "owner",
            "origin_conversation_id": "conversation",
            "epoch": 2,
            "attempt_id": "attempt",
            "instruction": "publish",
            "request": {"browser_url": "https://example.com/"},
        },
        {"memory_revision": 1},
    )
    assert result["phase"] == "browser_waiting"
    assert result["artifact"]["action_id"] == "approval"
    assert calls.count("/internal/browser/operator/session/step") == 1


async def test_unchanged_page_stops_repeated_clicks_even_if_model_reason_changes():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from adex_agent.browser.workflow import BrowserWorkflow

    steps = []

    async def call(service, scope, method, path, body, **kwargs):
        if path.endswith("/ensure"):
            return {"id": "session"}
        if path.endswith("/step"):
            steps.append(body["step"]["action"])
        return {"status": "AGENT", "observation_id": "unchanged", "nodes": []}

    worker = SimpleNamespace(
        core=SimpleNamespace(call=call),
        runtime=None,
        checkpoints=SimpleNamespace(save_checkpoint=AsyncMock(return_value="checkpoint")),
        run_write=AsyncMock(),
    )
    workflow = BrowserWorkflow(worker)
    workflow.plan = AsyncMock(
        side_effect=[{"action": "click", "element_id": "button", "reason": str(i)} for i in range(3)]
    )
    result = await workflow.run(
        {
            "id": "run",
            "owner_id": "owner",
            "origin_conversation_id": "conv",
            "epoch": 1,
            "attempt_id": "attempt",
            "instruction": "lookup",
            "request": {"browser_url": "https://example.com/"},
        },
        {"memory_revision": 1},
    )
    assert steps == ["click", "click", "handoff"]
    assert result["phase"] == "browser_waiting"
