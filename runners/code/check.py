"""No business data/keys; invoked with network=none, CPU/RAM/PID/time limits."""

import json
from pathlib import Path
from playwright.sync_api import sync_playwright

source = Path("/input/game.html").read_text()
if len(source) > 128000:
    raise SystemExit(2)
with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=["--disable-dev-shm-usage", "--disable-background-networking"],
    )
    context = browser.new_context(service_workers="block")
    context.route("**/*", lambda route: route.abort())
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)[:200]))
    page.set_content(source, wait_until="domcontentloaded", timeout=6000)
    page.wait_for_timeout(500)
    print(
        json.dumps(
            {
                "status": "PASS" if not errors else "FAILED",
                "errors": errors,
                "has_canvas": page.locator("canvas").count() > 0,
                "body_text": page.locator("body").inner_text()[:500],
            }
        )
    )
    browser.close()
