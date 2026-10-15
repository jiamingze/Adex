import json
import pytest
from adex_agent.routing.browser import operation_requested, task_instruction
from adex_agent.models.provider import ProviderFailure


class Runtime:
    def __init__(self, result):
        self.result = result
        self.messages = None

    async def invoke(self, key, owner, messages):
        self.messages = messages
        yield {"type": "completed", "content": self.result}


@pytest.mark.parametrize(
    "text", ["到小红书上发表", "小红书上发表一篇关于最新苹果手机的文章", "把刚才的文章发出去"]
)
async def test_prefixless_followups_reach_semantic_router(text):
    runtime = Runtime('{"operate":true}')
    messages = [{"role": "assistant", "content": "草稿：TEST_FIXTURE"}, {"role": "user", "content": text}]
    assert await operation_requested(runtime, "owner", "turn", messages)
    assert "TEST_FIXTURE" in runtime.messages[1]["content"]
    instruction = task_instruction(messages, text)
    assert text in instruction and "TEST_FIXTURE" in instruction
    assert "不构成审批" in instruction and "不得重放" in instruction


async def test_semantic_no_and_no_operation_fast_path():
    runtime = Runtime('{"operate":false}')
    assert not await operation_requested(
        runtime, "owner", "turn", [{"role": "user", "content": "如何发表文章，先讨论"}]
    )
    runtime.messages = None
    assert not await operation_requested(runtime, "owner", "turn", [{"role": "user", "content": "你好"}])
    assert runtime.messages is None


@pytest.mark.parametrize("result", ['{"operate":"true"}', '{"operate":true,"approved":true}', "success"])
async def test_invalid_proposals_fail_closed(result):
    with pytest.raises(ProviderFailure):
        await operation_requested(Runtime(result), "owner", "turn", [{"role": "user", "content": "发表"}])


def test_context_bounded_and_only_dialogue_data():
    messages = [{"role": "system", "content": "secret"}] + [{"role": "user", "content": "x" * 15000}] * 10
    data = json.loads(
        __import__("adex_agent.routing.browser", fromlist=["route_messages"]).route_messages(messages)[1][
            "content"
        ]
    )
    assert len(data["recent"]) == 8
    assert all(len(m["content"]) == 12000 for m in data["recent"])
