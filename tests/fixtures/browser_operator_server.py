"""TEST_FIXTURE: synthetic browser UI only, loopback; never deploy."""

import asyncio
from functools import partial
from http.server import ThreadingHTTPServer
from product_gallery_server import DATA, CONVERSATION, ROOT, GalleryHandler

SESSION = "00000000-0000-4000-8000-000000000002"
VIEW = {
    "id": SESSION,
    "run_id": SESSION,
    "conversation_id": CONVERSATION,
    "status": "HUMAN",
    "run_status": "WAITING_INPUT",
    "current_url": "https://example.com/fixture",
    "url": "https://example.com/fixture",
    "title": "TEST_FIXTURE · 网页发布演示",
    "revision": 1,
    "action_id": None,
    "nodes": [
        {"id": "title", "role": "textbox", "name": "标题"},
        {"id": "body", "role": "textbox", "name": "正文"},
    ],
    "tabs": [],
    "profile_revision": 0,
}


async def preview():
    from adex_tools.browser.process import BrowserProcess

    actor = await BrowserProcess.start()
    try:
        await actor.call({"url": "https://example.com/fixture", "_test_fixture": True})
        result = await actor.call({"action": "observe", "screenshot": True})
        VIEW["screenshot"] = result["screenshot"]
    finally:
        await actor.close()


DATA["/browser/sessions"] = {"availability": "CONFIGURED_UNVERIFIED", "items": [VIEW]}
DATA["/browser/sessions/" + SESSION] = VIEW
DATA["/browser/accounts"] = {"items": []}
if __name__ == "__main__":
    asyncio.run(preview())
    ThreadingHTTPServer(
        ("127.0.0.1", 18118), partial(GalleryHandler, directory=str(ROOT))
    ).serve_forever()
