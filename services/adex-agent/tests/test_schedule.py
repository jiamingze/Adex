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


@pytest.mark.parametrize("text", ["每天晚上19点发我最新的新闻", "每天晚上7点发给我最新的新闻"])
def test_daily_delivery_colloquial_request(text):
    from adex_agent.routing.intent import schedule_intent
    from adex_agent.routing.schedule import daily_chat_draft

    assert schedule_intent(text)
    draft = daily_chat_draft(text)
    assert draft["kind"] == "DAILY"
    assert draft["local_time"] == "19:00"


def test_ten_minute_delivery_request():
    from adex_agent.routing.intent import schedule_intent
    from adex_agent.routing.schedule import relative_chat_draft

    text = "10分钟后发我下最新的新闻"
    assert schedule_intent(text)
    assert relative_chat_draft(text)["delay_seconds"] == 600


@pytest.mark.parametrize(
    "text,seconds",
    [
        ("1分钟之后帮我整一下重要的新闻", 60),
        ("1分钟之后帮我整理一下重要的新闻", 60),
        ("2分钟之后帮我搜一下今天最新的全球新闻", 120),
        ("10分钟之后发我最新新闻", 600),
        ("十分钟之后提醒我喝水", 600),
    ],
)
def test_relative_route_and_parser_share_duration_grammar(text, seconds):
    from adex_agent.routing.intent import schedule_intent
    from adex_agent.routing.schedule import relative_chat_draft

    assert schedule_intent(text)
    assert relative_chat_draft(text)["delay_seconds"] == seconds


def test_negated_relative_after_variant_is_not_created():
    from adex_agent.routing.intent import schedule_intent

    assert not schedule_intent("不要1分钟之后提醒我")


@pytest.mark.parametrize(
    "text,seconds",
    [
        ("每10min帮我巡检网站是否有新公告", 600),
        ("每隔十分钟帮我检查最新新闻，有变化再通知我", 600),
        ("每2小时发我一次行业新闻", 7200),
    ],
)
def test_interval_chat_routes_to_durable_scheduler(text, seconds):
    from adex_agent.routing.intent import schedule_intent
    from adex_agent.routing.schedule import interval_chat_draft

    assert schedule_intent(text)
    draft = interval_chat_draft(text)
    assert draft["kind"] == "INTERVAL"
    assert draft["interval_seconds"] == seconds
    assert draft["instruction"]


def test_interval_invalid_or_negated_is_not_a_success():
    from adex_agent.routing.intent import schedule_intent
    from adex_agent.routing.schedule import interval_chat_draft

    assert not schedule_intent("不要每10min帮我巡检")
    assert interval_chat_draft("每0分钟帮我巡检") is None
    assert interval_chat_draft("每10分钟") is None


@pytest.mark.asyncio
async def test_semantic_draft_rejects_claims_and_owner_injection():
    import json
    from adex_agent.routing.schedule import semantic_chat_draft

    class Runtime:
        result = {
            "draft": {
                "title": "新闻",
                "instruction": "整理新闻",
                "kind": "INTERVAL",
                "timezone": "Asia/Shanghai",
                "first_fire_at": "2099-01-01T08:00:00+08:00",
                "interval_seconds": 600,
            }
        }

        async def invoke(self, *args):
            yield {"type": "completed", "content": json.dumps(self.result)}

    runtime = Runtime()
    assert (await semantic_chat_draft(runtime, "owner", "turn", "隔十分钟巡检"))["interval_seconds"] == 600
    runtime.result["draft"]["owner_id"] = "someone-else"
    assert await semantic_chat_draft(runtime, "owner", "turn", "巡检") is None
    runtime.result = {"content": "已创建任务"}
    assert await semantic_chat_draft(runtime, "owner", "turn", "巡检") is None


@pytest.mark.parametrize("text", ["10min后发我最新新闻", "十分钟以后帮我整理新闻"])
def test_colloquial_delay_units(text):
    from adex_agent.routing.intent import schedule_intent
    from adex_agent.routing.schedule import relative_chat_draft

    assert schedule_intent(text)
    assert relative_chat_draft(text)["delay_seconds"] == 600
