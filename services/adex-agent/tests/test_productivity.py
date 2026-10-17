import json
import pytest
from adex_agent.routing.productivity import todo_draft
from adex_agent.models.provider import ProviderFailure


class Runtime:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    async def invoke(self, *args):
        self.calls += 1
        yield {"type": "completed", "content": json.dumps(self.result)}


@pytest.mark.asyncio
async def test_todo_semantics_and_no_invented_owner():
    runtime = Runtime({"todo": {"title": "准备项目周报", "important": True, "urgent": False, "due_at": None}})
    result = await todo_draft(runtime, "owner", "turn", "把准备项目周报加入我的待办，很重要")
    assert result["title"] == "准备项目周报" and result["important"]
    runtime.result["todo"]["owner_id"] = "another-user"
    with pytest.raises(ProviderFailure):
        await todo_draft(runtime, "owner", "turn", "创建待办")
    runtime.result = {"todo": None}
    assert await todo_draft(runtime, "owner", "turn", "不要创建待办") is None
    assert await todo_draft(runtime, "owner", "turn", "你好") is None
    assert runtime.calls == 3


def test_unspecified_priority_is_deferred_to_app():
    from adex_agent.routing.productivity import TodoDraft

    draft = TodoDraft(title="准备周报")
    assert draft.important is None and draft.urgent is None and draft.due_at is None
    assert TodoDraft(title="买零食", important=False, urgent=True).important is False
