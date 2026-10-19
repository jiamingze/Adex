"""Alternate public discovery after a blocked search page; never external action success."""

from urllib.parse import urlsplit, parse_qs


async def blocked_search_fallback(core, run, view, session_id):
    if (
        run.get("request", {}).get("params", {}).get("browser_mode") != "lookup"
        or not view.get("access_block")
        or view.get("status") != "AGENT"
        or view.get("action_id")
    ):
        return None
    parsed = urlsplit(view.get("url", ""))
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"google.com", "www.google.com", "www.google.com.hk"}
        or parsed.path != "/search"
        or parsed.username
        or parsed.password
    ):
        return None
    query = parse_qs(parsed.query).get("q", [""])[0].strip()[:300]
    if not query:
        return None
    try:
        result = await core.call(
            "tools", "search:read", "POST", "/internal/search", {"query": query}, owner=run["owner_id"]
        )
    except Exception:
        return None
    items = [
        item
        for item in result.get("items", [])[:5]
        if isinstance(item, dict) and item.get("url", "").startswith("https://")
    ]
    if not items:
        return None

    # Treat excerpts as quoted untrusted text, never instructions or price/order receipts.
    def quoted(text):
        return "> " + str(text).replace("\n", "\n> ")[:1000]

    content = "Google 当前要求网站验证，已自动改用其他联网搜索渠道。以下是搜索摘要，尚未逐页核实：\n\n"
    content += "\n\n".join(
        quoted(item.get("title", "")) + "\n" + quoted(item.get("snippet", "")) + "\n" + item["url"]
        for item in items
    )
    return {
        "schema_version": 1,
        "phase": "result",
        "content": content,
        "artifact": {
            "browser_session_id": session_id,
            "search_fallback": {
                "blocked_provider": "google",
                "provider": result.get("provider"),
                "fetched_at": result.get("fetched_at"),
                "items": items,
            },
            "receipts": [],
        },
        "completed_steps": ["alternate_search"],
        "pending_effects": [],
        "usage": result.get("usage", {}),
    }
