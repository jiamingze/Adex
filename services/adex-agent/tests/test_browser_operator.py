import pytest
from adex_agent.browser.workflow import parse_step
from adex_agent.models.provider import ProviderFailure
from adex_agent.routing.intent import browser_operation_intent


def test_generic_operation_intent_not_site_flows():
    assert browser_operation_intent("帮我在一个新的网站购买一双鞋")
    assert browser_operation_intent("帮我把这篇文章发布到网站")
    assert not browser_operation_intent("怎么在淘宝下单，先讨论方案")
    assert not browser_operation_intent("帮我写一篇购物指南")


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
