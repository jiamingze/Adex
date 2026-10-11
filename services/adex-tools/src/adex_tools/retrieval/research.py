import os
from urllib.parse import urlparse
from datetime import datetime, timezone
import ipaddress
import httpx
from adex_tools.retrieval.search import web_search


def public_url(value):
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.port not in (None, 443):
        return False
    host = parsed.hostname.lower()
    if (
        host in ("localhost", "metadata.google.internal")
        or "." not in host
        or host.endswith((".local", ".internal", ".localhost"))
    ):
        return False
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        return True


async def research(query):
    bundles = []
    for suffix in ("", " primary sources evidence limitations"):
        bundles.append(await web_search((query + suffix)[:300]))
    items = []
    seen = set()
    for bundle in bundles:
        for item in bundle["items"]:
            if item["url"] not in seen:
                seen.add(item["url"])
                items.append(item)
    urls = [item["url"] for item in items if public_url(item["url"])][:3]
    if urls:
        try:
            async with httpx.AsyncClient(timeout=20, trust_env=False, follow_redirects=False) as client:
                response = await client.post(
                    "https://api.tavily.com/extract",
                    headers={"Authorization": "Bearer " + os.environ["TAVILY_API_KEY"]},
                    json={"urls": urls, "extract_depth": "basic", "format": "text"},
                )
                response.raise_for_status()
                if len(response.content) > 2_000_000:
                    raise ValueError()
                extracted = {
                    row["url"]: row.get("raw_content", "")[:12000]
                    for row in response.json().get("results", [])
                }
            for item in items:
                if item["url"] in extracted:
                    item["extracted_text"] = extracted[item["url"]]
                    item["evidence_level"] = "EXTRACTED_PAGE"
        except (httpx.HTTPError, ValueError, KeyError):
            pass  # Keep timestamped snippets; do not pretend extraction succeeded.
    return {"provider": "tavily", "items": items, "fetched_at": datetime.now(timezone.utc).isoformat()}
