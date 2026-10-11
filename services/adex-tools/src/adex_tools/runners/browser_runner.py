"""Credential-free bounded subprocess. Reads public pages; never submits forms."""

import asyncio
import ipaddress
import json
import socket
import sys
from datetime import datetime, timezone
from urllib.parse import urlsplit
from adex_tools.runners.browser import allowed_url


async def run(body):
    from playwright.async_api import async_playwright

    hosts = tuple(body["hosts"])
    pinned = {}
    for host in hosts:
        if not host or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789.-" for char in host):
            continue
        try:
            addresses = {
                row[4][0]
                for row in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM, family=socket.AF_INET)
            }
            if addresses and all(ipaddress.ip_address(ip).is_global for ip in addresses):
                pinned[host] = sorted(addresses)[0]
        except OSError:
            pass
    if urlsplit(body["url"]).hostname not in pinned:
        return {"error": "BROWSER_DNS_BLOCKED"}
    rules = (
        ", ".join(f"MAP {host} {address}" for host, address in pinned.items())
        + ", MAP * ~NOTFOUND, EXCLUDE 127.0.0.1, EXCLUDE localhost"
    )
    items = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            chromium_sandbox=True,
            args=[
                "--disable-background-networking",
                "--disable-quic",
                "--no-proxy-server",
                "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                f"--host-resolver-rules={rules}",
            ],
        )
        try:
            context = await browser.new_context(accept_downloads=False, service_workers="block")

            async def intercept(route):
                request = route.request
                if (
                    request.method != "GET"
                    or not allowed_url(request.url, pinned)
                    or request.resource_type in ("image", "media", "font")
                ):
                    await route.abort()
                else:
                    await route.continue_()

            await context.route("**/*", intercept)
            await context.route_web_socket("**/*", lambda websocket: websocket.close())
            page = await context.new_page()
            urls = [body["url"]]
            # This application's public source paths; no login or GitHub account is used.
            if urlsplit(body["url"]).path.rstrip("/") == "/jiamingze/Adex" and any(
                word in body.get("query", "").lower() for word in ("语音", "voice", "speech", "asr")
            ):
                urls += [
                    "https://github.com/jiamingze/Adex/blob/main/apps/ios/ios/App/CapApp-SPM/Sources/CapApp-SPM/AdexBridge.swift",
                    "https://github.com/jiamingze/Adex/blob/main/apps/web/src/VoiceInput.tsx",
                ]
            for url in urls[:3]:
                try:
                    response = await page.goto(url, wait_until="domcontentloaded", timeout=12000)
                    if not response or response.status >= 400 or not allowed_url(page.url, pinned):
                        continue
                    text = await page.locator("body").inner_text(timeout=4000)
                    if len(text.strip()) < 40:
                        continue
                    code = page.locator('textarea[aria-label="File content"]')
                    if await code.count():
                        text = await code.input_value()
                    timestamp = datetime.now(timezone.utc).isoformat()
                    items.append(
                        {
                            "url": page.url,
                            "title": await page.title(),
                            "snippet": text[:160],
                            "extracted_text": text[: (4000 if url == urls[0] else 9000)],
                            "fetched_at": timestamp,
                            "evidence_level": "BROWSER_RENDERED_PAGE",
                        }
                    )
                except Exception:
                    continue
            return {
                "provider": "chromium",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "items": items,
                **({"error": "BROWSER_UNAVAILABLE"} if not items else {}),
            }
        finally:
            await browser.close()


if __name__ == "__main__":
    try:
        result = asyncio.run(run(json.loads(sys.stdin.buffer.read(4096))))
    except Exception:
        result = {"error": "BROWSER_UNAVAILABLE"}
    print(json.dumps(result, ensure_ascii=False))
