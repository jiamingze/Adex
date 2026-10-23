"""Render only observed search evidence, independent of free-form completion prose."""

import re
from urllib.parse import quote, urlsplit


def plain(value, limit):
    return re.sub(r"\s+", " ", str(value)).strip()[:limit]


def markdown(value):
    return re.sub(r"([\\`*_[\]<>])", r"\\\1", value)


def observed_results(nodes):
    results = []
    for index, node in enumerate(nodes):
        parsed = urlsplit(node.get("url", ""))
        host = parsed.hostname or ""
        if (
            node.get("role") != "AXLink"
            or not node.get("title")
            or parsed.scheme not in {"http", "https"}
            or not host
            or host == "google.com"
            or host.endswith(".google.com")
        ):
            continue
        title, fragments = node["title"], []
        prefix = str(node.get("id", "")) + "."
        for following in nodes[index + 1 : index + 81]:
            child = str(following.get("id", "")).startswith(prefix)
            if following.get("role") == "AXHeading" and child:
                title = following.get("title") or title
            if child:
                continue
            if following.get("role") == "AXLink":
                break
            value = plain(following.get("value") or following.get("title") or "", 1200)
            if (
                following.get("role") == "AXStaticText"
                and len(value) >= 8
                and value not in fragments
                and not value.startswith("http")
            ):
                fragments.append(value)
        title = re.sub(r"\s+https?://.*$", "", title)
        results.append({"title": title, "url": node["url"], "snippet": " ".join(fragments)[:1200]})
    return results[:10]


def search_report(query, results, observed_at):
    rows, seen = [], set()
    for result in results:
        url = result.get("url", "")
        parsed = urlsplit(url)
        if parsed.scheme not in {"https", "http"} or not parsed.hostname or url in seen:
            continue
        seen.add(url)
        title = markdown(plain(result.get("title") or parsed.hostname, 130))
        link = quote(url, safe=":/?&=%#@+;,!~*-._")
        snippet = markdown(plain(result.get("snippet", ""), 180))
        rows.append(f"{len(rows) + 1}. **[{title}]({link})**" + (f"\n   {snippet}" if snippet else ""))
        if len(rows) == 5:
            break
    if not rows:
        return "搜索页面尚未返回可核实的结果，请稍后重试。"
    return (
        f"### “{markdown(plain(query, 200))}”的搜索结果\n\n"
        + "\n\n".join(rows)
        + f"\n\n来源：本机 Chrome · Google 搜索\n\n查询时间：{observed_at}。以上为搜索页摘要。"
    )
