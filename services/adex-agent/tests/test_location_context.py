from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from adex_agent.routing.location import current_location, relevant
from adex_agent.execution.context import ContextService


def position(**extra):
    return {
        "source": "device",
        "label": "TEST_FIXTURE 上海市徐汇区",
        "latitude": 31.23456,
        "longitude": 121.47891,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        **extra,
    }


def test_expired_invalid_and_future_positions_never_become_current():
    now = datetime.now(timezone.utc)
    for value in [
        position(observed_at=(now - timedelta(minutes=16)).isoformat()),
        position(observed_at=(now + timedelta(minutes=2)).isoformat()),
        position(latitude=float("nan")),
        position(source="ip"),
    ]:
        assert current_location(value, now) is None
    assert current_location(position())["latitude"] == 31.23
    assert relevant("附近有什么五星级酒店")


async def test_weather_receives_approximate_coordinates_but_model_does_not():
    core = SimpleNamespace(
        call=AsyncMock(
            return_value={"daily": {"time": ["TEST_FIXTURE"]}, "source_url": "https://open-meteo.com/"}
        )
    )
    messages = await ContextService(core).messages(
        {
            "owner_id": "owner",
            "messages": [{"role": "user", "content": "明天的天气怎么样"}],
            "client_location": position(),
        },
        search=False,
    )
    args = core.call.call_args
    assert args.args[3] == "/internal/weather/forecast"
    assert args.args[4] == {"latitude": 31.23, "longitude": 121.48}
    assert "徐汇区" in messages[0]["content"]
    assert "31.23" not in str(messages) and "121.48" not in str(messages)
    assert "用户本轮明确指定的地点优先" in messages[0]["content"]


async def test_location_cache_and_missing_location_do_not_guess():
    redis = SimpleNamespace(get=AsyncMock(), set=AsyncMock())
    context = {"client_location": position()}
    assert await ContextService(None, redis).working(context) is context
    redis.get.assert_not_awaited()
    core = SimpleNamespace(call=AsyncMock())
    messages = await ContextService(core).messages(
        {"messages": [{"role": "user", "content": "附近有酒店吗"}]}, search=False
    )
    core.call.assert_not_awaited()
    assert "先问城市" in messages[0]["content"]


async def test_manual_city_grounds_search_without_device_or_weather_permission():
    core = SimpleNamespace(call=AsyncMock(return_value={"items": []}))
    value = {
        "source": "manual",
        "label": "TEST_FIXTURE 上海",
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    await ContextService(core).messages(
        {
            "owner_id": "owner",
            "messages": [{"role": "user", "content": "明天的天气怎么样"}],
            "client_location": value,
        },
        search=True,
    )
    assert core.call.call_args.args[3] == "/internal/search"
    assert "上海" in core.call.call_args.args[4]["query"]
