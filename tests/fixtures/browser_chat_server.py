"""Synthetic inline browser gallery. Loopback only; no accounts, DB or real publishing.

uv run --project services/adex-tools python tests/fixtures/browser_chat_server.py
Open /demo/login, /demo/review or /demo/done. Never enter real credentials.
"""

import asyncio
import json
from functools import partial
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer
from urllib.parse import urlparse
from product_gallery_server import GalleryHandler, DATA, ROOT, CONVERSATION, iso
from adex_tools.browser.process import BrowserProcess
from adex_tools.browser.login import login_form
from adex_tools.browser.policy import approval_summary

RUN = "00000000-0000-4000-8000-000000000002"
ACTION = "00000000-0000-4000-8000-000000000003"
STAGES = {}
DATA["/conversations"]["items"] = [
    {"id": CONVERSATION, "title": "Adex 介绍文章 · 发布演示", "updated_at": iso()}
]
TITLE = "Adex：让计划变成行动"
BODY = "这是演示文章，不会发布到任何真实平台。\n\nAdex 把聊天、日历、待办和笔记放在同一个工作空间。你可以在对话里整理想法，把值得保留的内容转成笔记，也可以把需要持续跟进的事情交给后台任务。\n\n网页操作由你掌握最后一步：助手先准备内容，需要登录时在当前会话接管，发表前核对标题、正文和目标网站。操作后核验回执，不用一句‘已完成’代替实际结果。\n\n开源项目欢迎一起参与。以上全部为合成演示数据。"


async def setup():
    actor = await BrowserProcess.start()
    try:
        await actor.call(
            {"url": "https://example.com/fixture-login", "_test_fixture": True}
        )
        login = await actor.call({"action": "mode", "mode": "HUMAN", "human": True})
        login.update(login_form=login_form(login), status="HUMAN", profile_revision=0)
        STAGES["login"] = {
            "run_id": RUN,
            "conversation_id": CONVERSATION,
            "status": "WAITING_INPUT",
            "session": login,
        }
    finally:
        await actor.close()
    actor = await BrowserProcess.start()
    try:
        view = await actor.call(
            {"url": "https://example.com/fixture", "_test_fixture": True}
        )
        for name, text in [("标题", TITLE), ("正文", BODY)]:
            node = next(
                n for n in view["nodes"] if n.get("name") == name and n.get("id")
            )
            view = await actor.call(
                {
                    "action": "type",
                    "element_id": node["id"],
                    "text": text,
                    "observation_id": view["observation_id"],
                }
            )
        button = next(
            n
            for n in view["nodes"]
            if n.get("name") == "发布" and n.get("role") == "button"
        )
        view = await actor.call(
            {
                "action": "click",
                "element_id": button["id"],
                "observation_id": view["observation_id"],
            }
        )
        view = await actor.call({"action": "observe", "screenshot": True})
        pending = view["pending"]
        review = {**view, "status": "WAITING_APPROVAL", "action_id": ACTION}
        STAGES["review"] = {
            "run_id": RUN,
            "conversation_id": CONVERSATION,
            "status": "WAITING_INPUT",
            "session": review,
            "action": {
                "id": ACTION,
                "kind": "browser.request",
                "state": "PENDING",
                "request_hash": "TEST_FIXTURE_HASH",
                "request": {
                    "origin_conversation_id": CONVERSATION,
                    "summary": approval_summary(pending),
                    "payload": pending["preview"],
                },
            },
        }
        final = await actor.call(
            {
                "action": "release",
                "request_id": pending["id"],
                "digest": pending["digest"],
                "allow": True,
            }
        )
        final.update(status="AGENT", business_receipts=[final["receipt"]])
        STAGES["done"] = {
            "run_id": RUN,
            "conversation_id": CONVERSATION,
            "status": "COMPLETED",
            "session": final,
        }
    finally:
        await actor.close()
    for stage in STAGES.values():
        stage["session"].update(
            id=RUN,
            run_id=RUN,
            conversation_id=CONVERSATION,
            progress_events=[
                {"step": 1, "text": "打开演示网站", "at": iso()},
                {"step": 2, "text": "检查页面并准备内容", "at": iso()},
            ],
        )
        stage["session"].pop("_storage", None)


class InlineHandler(GalleryHandler):
    def stage(self):
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        return (
            cookie.get("adex_browser_demo").value
            if cookie.get("adex_browser_demo")
            else "login"
        )

    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith("/demo/"):
            stage = path.rsplit("/", 1)[-1]
            if stage not in STAGES:
                return self.reply({}, 404)
            # Return a canonical fixture cookie, never reflect URL text into a header.
            cookie = {
                "login": "adex_browser_demo=login; Path=/; SameSite=Lax",
                "review": "adex_browser_demo=review; Path=/; SameSite=Lax",
                "done": "adex_browser_demo=done; Path=/; SameSite=Lax",
            }.get(stage)
            if cookie is None:
                return self.reply({}, 404)
            self.send_response(302)
            self.send_header("Set-Cookie", cookie)
            self.send_header("Location", "/c/" + CONVERSATION)
            self.end_headers()
            return
        if path == "/api/v1/browser/runs/" + RUN:
            return self.reply(STAGES[self.stage()])
        if path == f"/api/v1/conversations/{CONVERSATION}/messages":
            return self.reply(
                {
                    "items": [
                        {
                            "id": "fixture-user",
                            "role": "user",
                            "content": "帮我在演示网站发表一篇 Adex 介绍，发表前让我确认。",
                            "seq": 1,
                            "created_at": iso(),
                            "turn_id": "fixture-user",
                        },
                        {
                            "id": "fixture-assistant",
                            "role": "assistant",
                            "content": "我会准备文章，在需要登录或确认时请你处理。整个过程都留在这条对话里。",
                            "seq": 2,
                            "created_at": iso(),
                            "turn_id": "fixture-user",
                            "cards": [
                                {
                                    "schema_version": 1,
                                    "type": "task_status",
                                    "card_id": "fixture-browser-card",
                                    "conversation_id": CONVERSATION,
                                    "message_id": "fixture-assistant",
                                    "actions": [],
                                    "data": {"kind": "BROWSER", "run_id": RUN},
                                }
                            ],
                        },
                    ],
                    "turns": [],
                    "event_seq": 0,
                }
            )
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if (
            path == f"/api/v1/browser/sessions/{RUN}/control"
            or path == f"/api/v1/actions/{ACTION}/approve"
        ):
            # UI-only demo; actual login/publish safety is tested with the isolated backend.
            body = json.loads(
                self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}"
            )
            stage = (
                "done"
                if "/actions/" in path
                else "review"
                if body.get("action") == "secure_login"
                else self.stage()
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header(
                "Set-Cookie", f"adex_browser_demo={stage}; Path=/; SameSite=Lax"
            )
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {
                        "auto_resumed": True,
                        "remembered": bool(body.get("remember_login")),
                    }
                ).encode()
            )
            return
        return super().do_POST()


if __name__ == "__main__":
    asyncio.run(setup())
    ThreadingHTTPServer(
        ("127.0.0.1", 18119), partial(InlineHandler, directory=str(ROOT))
    ).serve_forever()
