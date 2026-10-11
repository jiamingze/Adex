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
