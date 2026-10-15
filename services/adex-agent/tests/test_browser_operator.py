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
