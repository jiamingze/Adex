import json
import pytest
from adex_agent.routing.browser import route_request, task_instruction
from adex_agent.models.provider import ProviderFailure


class Runtime:
    def __init__(self, result):
        self.result = result
        self.messages = None

    async def invoke(self, key, owner, messages):
        self.messages = messages
        yield {"type": "completed", "content": self.result}


@pytest.mark.parametrize("text", ["帮我下单xauusd", "用mt5下单安", "用MT5", "MT5查一下XAUUSD行情"])
async def test_mt5_never_enters_web_commerce_even_with_broker_history(text):
    runtime = Runtime('{"mode":"operate"}')
    messages = [
        {"role": "assistant", "content": "网页助手 https://www.futunn.com/ 确认并继续"},
        {"role": "user", "content": text},
    ]
    assert await route_request(runtime, "owner", "turn", messages) == "none"
    assert runtime.messages is None


async def test_mt5_documentation_can_still_use_explicit_website_research():
    runtime = Runtime('{"mode":"lookup"}')
    assert await route_request(runtime, "owner", "turn", [{
        "role": "user", "content": "打开MT5官网查一下安装教程",
    }]) == "lookup"


@pytest.mark.parametrize(
    "text", ["到小红书上发表", "小红书上发表一篇关于最新苹果手机的文章", "把刚才的文章发出去"]
)
async def test_prefixless_followups_reach_semantic_router(text):
    runtime = Runtime('{"mode":"operate"}')
    messages = [{"role": "assistant", "content": "草稿：TEST_FIXTURE"}, {"role": "user", "content": text}]
    assert await route_request(runtime, "owner", "turn", messages) == "operate"
    assert "TEST_FIXTURE" not in runtime.messages[1]["content"]
    instruction = task_instruction(messages, text)
    assert text in instruction and "TEST_FIXTURE" in instruction
    assert "不构成审批" in instruction and "不得重放" in instruction


async def test_semantic_no_and_no_operation_fast_path():
    runtime = Runtime('{"mode":"none"}')
    assert "none" == await route_request(
        runtime, "owner", "turn", [{"role": "user", "content": "如何发表文章，先讨论"}]
    )
    runtime.messages = None
    assert "none" == await route_request(runtime, "owner", "turn", [{"role": "user", "content": "你好"}])
    assert runtime.messages is None


@pytest.mark.parametrize("result", ['{"operate":"true"}', '{"operate":true,"approved":true}', "success"])
async def test_invalid_proposals_fail_closed(result):
    with pytest.raises(ProviderFailure):
        await route_request(Runtime(result), "owner", "turn", [{"role": "user", "content": "发表"}])


def test_context_bounded_and_only_dialogue_data():
    messages = [{"role": "system", "content": "secret"}] + [{"role": "user", "content": "x" * 15000}] * 10
    data = json.loads(
        __import__("adex_agent.routing.browser", fromlist=["route_messages"]).route_messages(messages)[1][
            "content"
        ]
    )
    assert len(data["recent"]) == 8
    assert all(len(m["content"]) == 12000 for m in data["recent"])


@pytest.mark.parametrize(
    "text",
    [
        "去京东看看这款手机多少钱",
        "淘宝的价格和库存查一下",
        "比较两个网站的报价",
        "去淘宝搜集iPhone 17 Pro Max",
    ],
)
async def test_commerce_lookup_reaches_browser_semantic_route(text):
    runtime = Runtime('{"mode":"lookup"}')
    assert await route_request(runtime, "owner", "turn", [{"role": "user", "content": text}]) == "lookup"


def test_lookup_completion_contains_observed_source_time_not_purchase_receipt():
    from adex_agent.browser.workflow import lookup_result

    result = lookup_result(
        "fixture",
        {
            "url": "https://example.com/product",
            "title": "TEST_FIXTURE",
            "nodes": [{"role": "StaticText", "name": "TEST_FIXTURE 256GB ¥1000"}],
        },
        "页面显示256GB ¥1000",
    )
    assert "未创建订单" in result["content"]
    evidence = result["artifact"]["lookup_evidence"]
    assert evidence["observed_at"] and evidence["url"] == "https://example.com/product"
    assert "256GB" in evidence["visible_text"]
    assert result["artifact"]["receipts"] == []
    empty = lookup_result("fixture", {"url": "https://example.com/login", "nodes": []}, "虚构价格")
    assert "虚构价格" not in empty["content"] and "未创建订单" in empty["content"]
    with pytest.raises(ProviderFailure):
        lookup_result("fixture", {"url": "http://127.0.0.1", "nodes": []}, "")


async def test_assistant_denials_cannot_enter_browser_intent_classifier():
    query = "帮我打开小红书上网搜一篇关于特斯拉最近的新闻"
    runtime = Runtime('{"mode":"lookup"}')
    messages = [
        {"role": "user", "content": "搜小红书"},
        {"role": "assistant", "content": "无法打开小红书，普通聊天只有只读浏览器，不能输入。"},
        {"role": "user", "content": query},
    ]
    assert await route_request(runtime, "owner", "turn", messages) == "lookup"
    payload = json.loads(runtime.messages[1]["content"])
    assert payload["latest_request"] == query
    assert all(m["role"] == "user" for m in payload["recent"])
    assert "无法打开" not in runtime.messages[1]["content"]
    assert "无法打开" in task_instruction(
        messages, query
    )  # Draft context is separate, never an intent authority.
