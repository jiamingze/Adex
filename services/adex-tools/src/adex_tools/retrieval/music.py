from datetime import datetime, timezone
from urllib.parse import urlparse
import httpx
from fastapi import HTTPException


async def catalog_search(query):
    try:
        async with httpx.AsyncClient(timeout=15, trust_env=False, follow_redirects=False) as client:
            response = await client.get(
                "https://itunes.apple.com/search",
                params={"term": query, "media": "music", "entity": "song", "limit": 12, "country": "TW"},
            )
            response.raise_for_status()
            if len(response.content) > 1_000_000:
                raise ValueError()
            rows = response.json()["results"]
        items = []
        for row in rows:
            url = row.get("trackViewUrl", "")
            if urlparse(url).hostname not in ("music.apple.com", "itunes.apple.com"):
                continue
            items.append(
                {
                    "provider": "apple-catalog",
                    "track_id": str(row["trackId"]),
                    "title": row["trackName"],
                    "artists": [row["artistName"]],
                    "album": row.get("collectionName"),
                    "duration_ms": row.get("trackTimeMillis"),
                    "artwork_url": row.get("artworkUrl100"),
                    "source_url": url,
                    "availability": "PROVIDER_OPEN",
                    "playback_url": None,
                }
            )
        return {
            "items": items,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "license": "Metadata only; playback opens official provider",
        }
    except (httpx.HTTPError, ValueError, KeyError):
        raise HTTPException(503, "MUSIC_CATALOG_UNAVAILABLE") from None
