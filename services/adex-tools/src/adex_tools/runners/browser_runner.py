"""Bounded, credential-free public rendering; no forms or arbitrary script tool."""

import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urlsplit, urljoin
from adex_tools.runners.browser_policy import allowed_url, resolve_public_hosts
from adex_tools.runners.browser_proxy import BrowserEgress
from adex_tools.runners.browser_config import browser_channel


def related_links(links, page_url, hosts, query):
    origin = urlsplit(page_url).hostname
    tokens = re.findall(r"[a-z0-9]{3,}|[\u4e00-\u9fff]{2,}", query.lower())
    unique = {}
    for link in links[:100]:
        url = urljoin(page_url, link.get("href", ""))
        parsed = urlsplit(url)
        url = parsed._replace(fragment="").geturl()
        text = link.get("text", "").strip()[:120]
        if (
            not text
            or not allowed_url(url, hosts)
            or parsed.hostname != origin
            or parsed.query
            or url == page_url
            or re.search(
                r"login|logout|sign.?in|sign.?out|delete|checkout|subscribe|remove|cart", parsed.path, re.I
            )
        ):
            continue
        score = sum(token in (text + " " + parsed.path).lower() for token in tokens)
        score += int(bool(re.search(r"documentation|docs|readme|about|介绍|文档", text, re.I)))
        unique.setdefault(url, {"url": url, "title": text, "score": score})
    return sorted(unique.values(), key=lambda item: -item["score"])[:12]


async def run(body):
    from playwright.async_api import async_playwright

    pinned = await asyncio.wait_for(asyncio.to_thread(resolve_public_hosts, body["hosts"]), 8)
    origin = urlsplit(body["url"]).hostname
    if origin not in pinned:
        return {"error": "BROWSER_DNS_BLOCKED"}
    egress = BrowserEgress(pinned)
    proxy = await asyncio.start_server(egress.handle, "127.0.0.1", 0, limit=8192)
    port = proxy.sockets[0].getsockname()[1]
    items = []
    failures = []
    requests = 0
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=True,
                channel=browser_channel(),
                chromium_sandbox=True,
                proxy={"server": f"http://127.0.0.1:{port}", "bypass": "<-loopback>"},
                args=[
                    "--disable-background-networking",
                    "--disable-quic",
                    "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                ],
            )
            try:
                context = await browser.new_context(accept_downloads=False, service_workers="block")
                context.on("page", lambda page: page.on("dialog", lambda dialog: dialog.dismiss()))

                async def intercept(route):
                    nonlocal requests
                    requests += 1
                    request = route.request
                    if (
                        requests > 120
                        or request.method != "GET"
                        or not allowed_url(request.url, pinned)
                        or request.resource_type in ("image", "media", "font")
                        or (request.is_navigation_request() and urlsplit(request.url).hostname != origin)
                    ):
                        await route.abort()
                    else:
                        await route.continue_()

                await context.route("**/*", intercept)
                await context.route_web_socket("**/*", lambda websocket: websocket.close())
                page = await context.new_page()
                queue = [body["url"]]
                seen = set()
                max_pages = min(3, max(1, body.get("max_pages", 3)))
                deadline = asyncio.get_running_loop().time() + 30
                while queue and len(seen) < max_pages and asyncio.get_running_loop().time() < deadline:
                    url = queue.pop(0)
                    if url in seen:
                        continue
                    seen.add(url)
                    try:
                        async with asyncio.timeout(
                            min(12, max(0.1, deadline - asyncio.get_running_loop().time()))
                        ):
                            response = await page.goto(url, wait_until="commit", timeout=10000)
                            if not response or response.status >= 400 or not allowed_url(page.url, pinned):
                                failures.append(
                                    {
                                        "url": url,
                                        "code": f"HTTP_{response.status}" if response else "NO_RESPONSE",
                                    }
                                )
                                continue
                            try:
                                await page.wait_for_load_state("domcontentloaded", timeout=2000)
                            except Exception:
                                pass
                            # A bounded load opportunity for JS-rendered public content;
                            # continuously polling sites must not hold the turn forever.
                            try:
                                await page.wait_for_load_state("networkidle", timeout=2000)
                            except Exception:
                                pass
                            text = await page.locator("body").inner_text(timeout=4000)
                            if len(text.strip()) < 40:
                                continue
                            code = page.locator('textarea[aria-label="File content"]')
                            if await code.count():
                                text = await code.input_value()
                            links = related_links(
                                await page.locator("a[href]").evaluate_all(
                                    "els => els.slice(0, 100).map(a => ({href: a.href, text: a.innerText}))"
                                ),
                                page.url,
                                pinned,
                                body.get("query", ""),
                            )
                            items.append(
                                {
                                    "url": page.url,
                                    "title": (await page.title())[:200],
                                    "snippet": text[:160],
                                    "extracted_text": text[:10000],
                                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                                    "evidence_level": "BROWSER_RENDERED_PAGE",
                                    "links": [{"url": link["url"], "title": link["title"]} for link in links],
                                }
                            )
                            if len(seen) == 1:
                                queue.extend(link["url"] for link in links if link["score"] > 0)
                    except Exception as error:
                        network = re.search(r"net::(ERR_[A-Z0-9_]+)", str(error))
                        failures.append(
                            {
                                "url": url,
                                "code": network.group(1)
                                if network
                                else "NAVIGATION_TIMEOUT"
                                if "Timeout" in type(error).__name__
                                else "NAVIGATION_FAILED",
                            }
                        )
                        continue
                return {
                    "provider": "chromium",
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "items": items,
                    "failures": failures,
                    **({"error": "BROWSER_UNAVAILABLE"} if not items else {}),
                }
            finally:
                await browser.close()
    finally:
        proxy.close()
        await egress.close()
        await proxy.wait_closed()


if __name__ == "__main__":
    try:
        result = asyncio.run(run(json.loads(sys.stdin.buffer.read(8192))))
    except Exception:
        result = {"error": "BROWSER_UNAVAILABLE"}
    print(json.dumps(result, ensure_ascii=False))
