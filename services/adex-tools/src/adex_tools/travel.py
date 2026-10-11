from datetime import date, datetime, timezone, timedelta
import httpx
from fastapi import HTTPException
from .search import web_search


async def plan_evidence(city, start, end):
    first = date.fromisoformat(start)
    last = date.fromisoformat(end)
    if last < first or (last - first).days > 14:
        raise HTTPException(400, "INVALID_TRAVEL_DATES")
    async with httpx.AsyncClient(timeout=15, trust_env=False, follow_redirects=False) as client:
        geocode = await client.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 5, "language": "zh", "format": "json"},
        )
        geocode.raise_for_status()
        locations = geocode.json().get("results", [])
        if not locations:
            raise HTTPException(422, "CITY_NOT_FOUND")
        location = locations[0]  # Explicitly show ambiguity candidates to the user.
        weather = {"status": "FORECAST_OUT_OF_RANGE"}
        if date.today() <= first <= last <= date.today() + timedelta(days=15):
            response = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": location["latitude"],
                    "longitude": location["longitude"],
                    "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                    "timezone": location.get("timezone", "auto"),
                    "start_date": start,
                    "end_date": end,
                },
            )
            if response.status_code == 200:
                weather = {"status": "AVAILABLE", "daily": response.json().get("daily", {})}
    hotel = await web_search(f"{city} hotel official family location")
    poi = await web_search(f"{city} attractions official travel")
    return {
        "city": location,
        "city_candidates": locations,
        "dates": {"start": start, "end": end},
        "weather": weather,
        "hotels": hotel["items"],
        "pois": poi["items"],
        "inventory_verified": False,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "geo_source": "https://open-meteo.com/",
        "map_url": f"https://www.openstreetmap.org/?mlat={location['latitude']}&mlon={location['longitude']}#map=12/{location['latitude']}/{location['longitude']}",
    }
