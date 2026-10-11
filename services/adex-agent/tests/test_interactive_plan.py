from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock
import pytest
from adex_agent.execution.runtime import Runtime
from adex_agent.models.provider import ProviderFailure


async def test_recovery_freezes_search_evidence_and_rejects_changed_memory():
    owner = uuid4()
    stored = {}

    async def query(sql, args, one=False):
        if sql.startswith("INSERT"):
            stored.update(owner_id=args[1], context_hash=args[2], messages=args[3].obj)
        else:
            return stored or None

    runtime = Runtime.__new__(Runtime)
    runtime.core = SimpleNamespace(query=query)
    runtime.messages = AsyncMock(return_value=[{"role": "system", "content": "search timestamp one"}])
    context = {"owner_id": str(owner), "memory_revision": 1}
    first = await runtime.interactive_messages("turn-one", owner, context, search=True)
    runtime.messages.return_value = [{"role": "system", "content": "different search"}]
    assert await runtime.interactive_messages("turn-one", owner, context, search=True) == first
    assert (
        await runtime.interactive_messages(
            "turn-one", owner, {**context, "summary": "newer extractive summary"}, search=True
        )
        == first
    )
    assert runtime.messages.await_count == 1
    with pytest.raises(ProviderFailure):
        await runtime.interactive_messages("turn-one", owner, {**context, "memory_revision": 2}, search=True)


async def test_travel_prompt_provides_relative_days_and_grounded_quotes():
    runtime = Runtime.__new__(Runtime)
    runtime.core = SimpleNamespace(call=AsyncMock(return_value={"items": [], "fetched_at": "fixture"}))
    context = {"owner_id": str(uuid4()), "messages": [{"role": "user", "content": "帮我安排上海到普吉岛的四天三晚行程"}]}
    messages = await runtime.messages(context, search=True)
    system = messages[0]["content"]
    assert "直接在当前回复" in system
    assert "不假定当前月份" in system
    assert "参考价也不能编造" in system
    assert "本轮真实证据URL" in system
    assert runtime.core.call.await_args.args[3] == "/internal/search"


async def test_recent_search_is_dated_and_uses_real_search_tool():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    runtime = Runtime.__new__(Runtime)
    runtime.core = SimpleNamespace(call=AsyncMock(return_value={"items": [], "fetched_at": "fixture"}))
    context = {"owner_id": str(uuid4()), "messages": [{"role": "user", "content": "帮我搜一下近期周杰伦的演唱会"}]}
    messages = await runtime.messages(context, search=True)
    today = datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d')
    assert today in runtime.core.call.await_args.args[4]['query']
    assert today in messages[0]['content']
    assert runtime.core.call.await_args.args[3] == '/internal/search'


async def test_failed_tool_protocol_history_is_not_replayed():
    runtime = Runtime.__new__(Runtime)
    runtime.core = SimpleNamespace()
    context = {'owner_id':str(uuid4()),'messages':[
        {'role':'user','content':'帮我搜索演唱会'},
        {'role':'assistant','content':'[minimax:tool_call](http://localhost/) <invoke name="fake">'},
        {'role':'user','content':'继续'}]}
    messages = await runtime.messages(context)
    assert not any(m['role']=='assistant' for m in messages)
    assert messages[-1]['content']=='继续'
