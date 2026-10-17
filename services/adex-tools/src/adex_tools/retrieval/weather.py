from datetime import datetime, timezone
import httpx


async def current_weather(latitude, longitude):
    async with httpx.AsyncClient(timeout=15, trust_env=False, follow_redirects=False) as client:
        response = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,precipitation,wind_speed_10m",
                "timezone": "UTC",
            },
        )
        response.raise_for_status()
        data = response.json()
    current = data["current"]
    return {
        "items": [
            {
                "temperature_2m": current["temperature_2m"],
                "precipitation": current["precipitation"],
                "wind_speed_10m": current["wind_speed_10m"],
            }
        ],
        "observation_time": current["time"],
        "units": data["current_units"],
        "source_url": "https://open-meteo.com/",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "latitude": latitude,
        "longitude": longitude,
    }


async def forecast_weather(latitude, longitude):
    """Read-only seven-day forecast, not model-generated weather or stale observations."""
    async with httpx.AsyncClient(
        timeout=12,
        trust_env=False,
        follow_redirects=False,
        headers={"User-Agent": "Adex/0.1 (+https://github.com/jiamingze/Adex)", "Accept": "application/json"},
    ) as client:
        response = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": round(latitude, 2),
                "longitude": round(longitude, 2),
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "timezone": "auto",
                "forecast_days": 7,
            },
        )
        response.raise_for_status()
        value = response.json()
    if not value.get("daily", {}).get("time"):
        raise ValueError("WEATHER_FORECAST_UNAVAILABLE")
    return {
        "daily": value["daily"],
        "units": value.get("daily_units", {}),
        "timezone": value.get("timezone"),
        "source_url": "https://open-meteo.com/",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "availability": "AVAILABLE",
    }
