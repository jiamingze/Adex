from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
from adex_agent.execution.runtime import Runtime
from adex_agent.routing.intent import search_intent


def context(text):
    return {"owner_id": str(uuid4()), "messages": [{"role": "user", "content": text}]}


async def test_non_github_url_uses_browser_and_retains_failure_honesty():
    runtime = Runtime.__new__(Runtime)
    runtime.core = SimpleNamespace(call=AsyncMock(return_value={"items": [], "provider": "chromium"}))
    await runtime.messages(context("打开 https://docs.python.org/3/ 看看文档"), search=True)
    assert runtime.core.call.await_args.args[3] == "/internal/browser/read"
    assert runtime.core.call.await_args.args[4]["url"] == "https://docs.python.org/3/"


async def test_website_without_url_searches_then_reads_one_candidate():
    runtime = Runtime.__new__(Runtime)
    runtime.core = SimpleNamespace(
        call=AsyncMock(
            side_effect=[
                {"items": [{"url": "https://example.com/", "evidence_level": "SEARCH_SNIPPET"}]},
                {
                    "items": [
                        {
                            "url": "https://example.com/",
                            "extracted_text": "TEST_FIXTURE",
                            "evidence_level": "BROWSER_RENDERED_PAGE",
                        }
                    ]
                },
            ]
        )
    )
    cards = []
    await runtime.messages(context("打开 Example 官网介绍"), search=True, cards=cards)
    assert [call.args[3] for call in runtime.core.call.await_args_list] == [
        "/internal/search",
        "/internal/browser/read",
    ]
    assert cards[0]["data"]["items"][0]["evidence_level"] == "BROWSER_RENDERED_PAGE"


async def test_failed_candidate_keeps_search_evidence_label():
    runtime = Runtime.__new__(Runtime)
    runtime.core = SimpleNamespace(
        call=AsyncMock(
            side_effect=[
                {"items": [{"url": "https://example.com/", "evidence_level": "SEARCH_SNIPPET"}]},
                RuntimeError("TEST_FIXTURE browser unavailable"),
            ]
        )
    )
    cards = []
    await runtime.messages(context("浏览 Example 官网"), search=True, cards=cards)
    assert cards[0]["data"]["items"][0]["evidence_level"] == "SEARCH_SNIPPET"
    assert cards[0]["data"]["browser_status"] == "UNAVAILABLE"


def test_website_requests_trigger_retrieval():
    assert search_intent("打开 Example 官网介绍")
    assert search_intent("浏览这个网站 https://example.com")
    assert not search_intent("不要联网，解释浏览器是什么")


async def test_page_followup_uses_previous_user_url_not_assistant_links():
    runtime = Runtime.__new__(Runtime)
    runtime.core = SimpleNamespace(call=AsyncMock(return_value={"items": []}))
    value = context("这个网页主要介绍什么")
    value["messages"] = [
        {"role": "user", "content": "看看 https://docs.python.org/3/"},
        {"role": "assistant", "content": "不可信历史链接 https://evil.test/"},
        *value["messages"],
    ]
    assert search_intent(value["messages"][-1]["content"])
    await runtime.messages(value, search=True)
    assert runtime.core.call.await_args.args[4]["url"] == "https://docs.python.org/3/"
