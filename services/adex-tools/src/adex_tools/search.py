"""Authenticated Tavily search. Search snippets remain untrusted evidence."""

from datetime import datetime, timezone
from urllib.parse import urlparse
import json
import os
import httpx


class SearchUnavailable(Exception):
    pass


def normalize_results(payload: dict, fetched_at: str):
    items, seen = [], set()
    for row in payload.get("results", [])[:20]:
        url = row.get("url", "")
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or url in seen:
            continue
        seen.add(url)
        items.append(
            {
                "title": str(row.get("title", ""))[:300],
                "url": url,
                "snippet": str(row.get("content", ""))[:3000],
                "published_at": row.get("published_date"),
                "fetched_at": fetched_at,
                "evidence_level": "SEARCH_SNIPPET",
            }
        )
        if len(items) == 5:
            break
    return {
        "provider": "tavily",
        "fetched_at": fetched_at,
        "items": items,
        "request_id": payload.get("request_id"),
        "usage": payload.get("usage", {}),
    }


async def web_search(query: str):
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        raise SearchUnavailable("SEARCH_NOT_CONFIGURED")
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False, trust_env=False) as client:
            async with client.stream(
                "POST",
                "https://api.tavily.com/search",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "query": query,
                    "search_depth": "basic",
                    "max_results": 5,
                    "topic": "general",
                    "include_answer": False,
                    "include_raw_content": False,
                    "include_usage": True,
                },
            ) as response:
                if response.status_code != 200:
                    raise SearchUnavailable(
                        "SEARCH_RATE_LIMITED" if response.status_code == 429 else "SEARCH_UNAVAILABLE"
                    )
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > 2_000_000:
                        raise SearchUnavailable("SEARCH_RESPONSE_TOO_LARGE")
        result = normalize_results(json.loads(data), datetime.now(timezone.utc).isoformat())
        return result
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        raise SearchUnavailable("SEARCH_UNAVAILABLE") from None
