import httpx
from adex_tools.retrieval.weather import forecast_weather


async def test_forecast_uses_actual_provider_dates_and_rounds_coordinates(monkeypatch):
    def handle(request):
        assert request.url.params["latitude"] == "31.23"
        assert request.url.params["longitude"] == "121.48"
        assert request.url.params["timezone"] == "auto"
        return httpx.Response(
            200,
            json={
                "daily": {"time": ["2026-10-18", "2026-10-19"], "temperature_2m_max": [20, 21]},
                "timezone": "Asia/Shanghai",
            },
        )

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handle))
    )
    value = await forecast_weather(31.234567, 121.47891)
    assert value["daily"]["time"] == ["2026-10-18", "2026-10-19"]
    assert value["availability"] == "AVAILABLE" and value["fetched_at"]
