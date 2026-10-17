import pytest
from pydantic import ValidationError
from adex_agent.routing.schedule import ScheduleDraft


def test_daily_requires_timezone_and_time():
    base = dict(
        title="daily",
        instruction="task",
        kind="DAILY",
        timezone="Asia/Shanghai",
        first_fire_at="2026-10-11T00:00:00Z",
    )
    with pytest.raises(ValidationError):
        ScheduleDraft(**base)
    assert ScheduleDraft(**base, local_time="08:00").kind == "DAILY"


def test_interval_cannot_bypass_minimum_frequency():
    with pytest.raises(ValidationError):
        ScheduleDraft(
            title="fast",
            instruction="task",
            kind="INTERVAL",
            timezone="UTC",
            first_fire_at="2026-10-11T00:00:00Z",
            interval_seconds=1,
        )


def test_relative_schedule_is_one_shot_and_not_browser_lookup():
    from adex_agent.routing.intent import schedule_intent
    from adex_agent.routing.schedule import relative_chat_draft

    for text, seconds in [
        ("1分钟后给整理一条最新的新闻", 60),
        ("十分钟后提醒我喝水", 600),
        ("2小时后帮我汇总新闻", 7200),
    ]:
        assert schedule_intent(text)
        draft = relative_chat_draft(text)
        assert draft["kind"] == "ONCE"
        assert draft["delay_seconds"] == seconds
        assert draft["instruction"]
    assert relative_chat_draft("一分钟后") is None
    assert not schedule_intent("不要一分钟后提醒我")
