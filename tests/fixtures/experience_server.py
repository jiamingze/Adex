"""TEST_FIXTURE only: isolated UI data, no database/provider access or external writes.

Run after pnpm --dir apps/web build. Bind loopback; never deploy this server.
"""

import json
import time
from uuid import uuid5, NAMESPACE_URL
from datetime import datetime, timedelta, timezone
from functools import partial
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2] / "apps/web/dist"
CONVERSATION = "00000000-0000-4000-8000-000000000001"
now = datetime.now(timezone.utc)


def iso(delta=0):
    return (now + timedelta(hours=delta)).isoformat()


tasks = [
    {
        "id": "focus",
        "title": "准备周五的产品评审",
        "important": True,
        "urgent": True,
        "status": "TODO",
        "revision": 1,
        "due_at": iso(1),
        "run_id": None,
        "conversation_id": None,
    },
    {
        "id": "plan",
        "title": "安排周末的短途旅行",
        "important": True,
        "urgent": False,
        "status": "TODO",
        "revision": 1,
        "due_at": iso(48),
        "run_id": None,
        "conversation_id": None,
    },
    {
        "id": "reply",
        "title": "回复活动邀请",
        "important": False,
        "urgent": True,
        "status": "TODO",
        "revision": 1,
        "due_at": None,
        "run_id": None,
        "conversation_id": None,
    },
]
DATA = {
    "/me": {"username": "体验测试", "is_guest": False},
    "/capabilities": {
        "chat_model": "TEST_FIXTURE",
        "music_provider": "mock",
        "video_provider": "mock",
        "music_model": "",
        "music_max_seconds": 600,
    },
    "/conversations": {"items": []},
    "/notifications": {
        "items": [
            {
                "id": "fixture-recent-result",
                "title": "任务已完成",
                "body": "TEST_FIXTURE 今日简报已整理：三条值得关注的科技动态，点击查看来源和详细内容。",
                "created_at": iso(-2),
                "read": True,
                "run_id": "fixture-result-run",
                "conversation_id": CONVERSATION,
            },
            {
                "id": "fixture-monitor-result",
                "title": "监控发现新信息",
                "body": "TEST_FIXTURE 监控发现新的发布记录，已把变化整理到原会话。",
                "created_at": iso(-3),
                "read": False,
                "conversation_id": CONVERSATION,
            },
            {
                "id": "fixture-expired-result",
                "title": "任务已完成",
                "body": "TEST_FIXTURE 过期未读结果不应显示在今日",
                "created_at": iso(-25),
                "read": False,
                "conversation_id": CONVERSATION,
            },
        ]
    },
    "/matrix": {"items": tasks},
    "/automations": {
        "items": [
            {
                "id": "brief",
                "title": "每日科技简报",
                "instruction": "整理科技动态",
                "kind": "DAILY",
                "status": "ACTIVE",
                "timezone": "Asia/Shanghai",
                "next_fire_at": iso(8),
                "revision": 1,
                "origin_conversation_id": CONVERSATION,
            }
        ]
    },
    "/tasks": {
        "items": [
            {
                "id": "research",
                "instruction": "整理一份个人助手产品调研报告",
                "status": "RUNNING",
                "error_code": None,
                "created_at": iso(-1),
                "checkpoint_ref": None,
                "origin_conversation_id": CONVERSATION,
            }
        ]
    },
    "/actions": {
        "items": [
            {
                "id": "review",
                "kind": "gmail.send",
                "connection_id": "mail",
                "state": "PENDING",
                "request_hash": "TEST_FIXTURE",
                "expires_at": iso(24),
                "request": {
                    "origin_conversation_id": CONVERSATION,
                    "payload": {
                        "to": "review@example.test",
                        "subject": "确认周五评审时间",
                        "text": "请确认周五下午的评审安排。",
                    },
                },
                "result": None,
            }
        ]
    },
    "/signals": {
        "items": [
            {
                "id": "signal",
                "kind": "CALENDAR_CONFLICT",
                "importance": 95,
                "suggestion": "周五两项安排时间重叠，可以提前调整其中一项。",
                "reasons": ["PROVIDER_EVENTS_OVERLAP"],
                "correlation_key": "TEST_FIXTURE",
                "conversation_id": CONVERSATION,
                "run_id": "research",
                "evidence": {"source": "TEST_FIXTURE"},
            }
        ]
    },
    "/artifacts": {
        "items": [
            {
                "id": "report",
                "title": "个人助手产品调研",
                "kind": "RESEARCH",
                "revision": 1,
            },
            {"id": "trip", "title": "周末旅行计划", "kind": "TRAVEL", "revision": 2},
        ]
    },
    "/notes": {
        "items": [
            {
                "id": "fixture-note",
                "title": "周末的几个想法",
                "preview": "给自己留一点时间，去公园走走。",
                "pinned": True,
                "revision": 1,
                "updated_at": "2026-10-14T08:00:00Z",
            }
        ],
        "has_more": False,
    },
    "/notes/fixture-note": {
        "id": "fixture-note",
        "title": "周末的几个想法",
        "content": "给自己留一点时间，去公园走走。\n\n这是一条 TEST_FIXTURE 笔记。",
        "pinned": True,
        "revision": 1,
        "updated_at": "2026-10-14T08:00:00Z",
    },
    "/connectors": {"items": [], "availability": "BLOCKED_EXTERNAL"},
    "/notification-preferences": {
        "enabled": True,
        "push_enabled": False,
        "min_importance": 70,
        "quiet_start": "22:00",
        "quiet_end": "08:00",
        "timezone": "Asia/Shanghai",
    },
    "/settings": {
        "settings": {"memory_enabled": True, "email_notifications": False, "email": ""}
    },
    "/usage": {
        "model": {"daily_call_limit": 0, "states": []},
        "storage": {"used_bytes": 0, "quota_bytes": 104857600},
    },
    "/monitors": {"items": []},
    "/memories": {
        "items": [{"id": "pref", "content": "喜欢简洁的中文回答", "revision": 1}]
    },
}


class Handler(SimpleHTTPRequestHandler):
    def reply(self, data, status=200):
        raw = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/v1"):
            path = parsed.path.removeprefix("/api/v1")
            cookie = SimpleCookie(self.headers.get("Cookie", ""))
            fault = cookie.get("fixture_fault")
            if path == f"/conversations/{CONVERSATION}/messages":
                return self.reply(
                    {
                        "items": [
                            {
                                "id": f"fixture-message-{i}",
                                "role": "user" if i % 2 == 0 else "assistant",
                                "content": f"TEST_FIXTURE 滚动位置验证，第 {i} 条。\n\n"
                                + "这是一段用于滚动测试的内容。" * 12,
                                "seq": i + 1,
                                "turn_id": f"fixture-turn-{i}",
                                "created_at": now.isoformat(),
                            }
                            for i in range(40)
                        ],
                        "turns": [],
                        "event_seq": 0,
                    }
                )
            if fault and fault.value == "calendar-plan" and path == "/connectors":
                return self.reply(
                    {
                        "items": [
                            {
                                "id": "fixture-calendar",
                                "service": "calendar",
                                "status": "ACTIVE",
                                "scopes": [],
                            }
                        ],
                        "availability": "TEST_FIXTURE",
                    }
                )
            if (
                fault
                and fault.value == "notes-read-timeout"
                and path.startswith("/notes/")
            ):
                time.sleep(
                    12
                )  # Cached conversion must open without waiting on this read.
            if fault and fault.value == "matrix-timeout" and path == "/matrix":
                time.sleep(12)  # TEST_FIXTURE: exceed the client's read deadline.
            if fault and fault.value == "actions" and path == "/actions":
                return self.reply({"code": "TEST_FIXTURE_UNAVAILABLE"}, 503)
            return self.reply(DATA.get(path, {"items": []}))
        if parsed.path.startswith("/assets/"):
            return super().do_GET()
        raw = (ROOT / "index.html").read_bytes()
        if parse_qs(parsed.query).get("keyboard_controls") == ["1"]:
            # TEST_FIXTURE controls verify the event contract, not a physical keyboard.
            raw = raw.replace(
                b"</body>",
                """<aside style='position:fixed;top:56px;right:4px;z-index:9999;background:white;border:1px solid #ddd;font-size:10px;padding:4px'>
            TEST_FIXTURE <button onclick="window.dispatchEvent(new Event('keyboardWillShow'))">模拟键盘显示</button>
            <button onclick="window.dispatchEvent(new Event('keyboardWillHide'))">模拟键盘收起</button></aside></body>""".encode(),
            )
        self.send_response(200)
        fault = parse_qs(parsed.query).get("fault", [""])[0]
        if fault:
            self.send_header(
                "Set-Cookie", f"fixture_fault={fault}; Path=/; SameSite=Strict"
            )
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        if self.path == "/api/v1/auth/guest":
            return self.reply(
                {"token": "TEST_FIXTURE", "username": "体验测试", "is_guest": False}
            )
        if self.path == "/api/v1/notes/from-message":
            body = json.loads(
                self.rfile.read(int(self.headers.get("Content-Length", "0")))
            )
            if body.get("conversation_id") != CONVERSATION:
                return self.reply({"code": "NOT_FOUND"}, 404)
            identifier = str(uuid5(NAMESPACE_URL, "TEST_FIXTURE:" + body["message_id"]))
            key = "/notes/" + identifier
            if key not in DATA:
                DATA[key] = {
                    "id": identifier,
                    "title": "TEST_FIXTURE 技术方案笔记",
                    "content": "TEST_FIXTURE 整理后的笔记正文；不是实际模型执行。",
                    "pinned": False,
                    "revision": 1,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                DATA["/notes"]["items"].insert(
                    0, {**DATA[key], "preview": DATA[key]["content"]}
                )
            return self.reply(DATA[key])
        if self.path == "/api/v1/notes":
            fault = SimpleCookie(self.headers.get("Cookie", "")).get("fixture_fault")
            if fault and fault.value == "notes-save-delay":
                time.sleep(2)
            body = json.loads(
                self.rfile.read(int(self.headers.get("Content-Length", "0")))
            )
            key = "/notes/" + body["id"]
            if key not in DATA:
                DATA[key] = {
                    **body,
                    "revision": 1,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                DATA["/notes"]["items"].insert(
                    0, {**DATA[key], "preview": body["content"][:160]}
                )
            return self.reply(DATA[key])
        if self.path == "/api/v1/connectors/fixture-calendar/query":
            # Explicit synthetic calendar read: never reads a personal account.
            today = (
                datetime.now()
                .astimezone()
                .replace(hour=9, minute=0, second=0, microsecond=0)
            )
            return self.reply(
                {
                    "events": [
                        {
                            "id": "fixture-morning",
                            "summary": "TEST_FIXTURE 今日晨会",
                            "location": "TEST_FIXTURE 会议室A",
                            "start": {"dateTime": today.isoformat()},
                            "end": {
                                "dateTime": (today + timedelta(hours=1)).isoformat()
                            },
                        },
                        {
                            "id": "fixture-tomorrow",
                            "summary": "TEST_FIXTURE 明日会议",
                            "organizer": "TEST_FIXTURE 邀请人",
                            "location": "TEST_FIXTURE 会议室 A",
                            "start": {
                                "dateTime": (today + timedelta(days=1)).isoformat()
                            },
                            "end": {
                                "dateTime": (
                                    today + timedelta(days=1, hours=1)
                                ).isoformat()
                            },
                        },
                    ],
                    "partial": False,
                    "provider": "TEST_FIXTURE",
                }
            )
        return self.reply({"code": "TEST_FIXTURE_WRITE_DISABLED"}, 403)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/v1/notes/"):
            return self.reply({"code": "TEST_FIXTURE_WRITE_DISABLED"}, 403)
        key = parsed.path.removeprefix("/api/v1")
        note = DATA.get(key)
        if note is None:
            return self.reply({"code": "NOTE_NOT_FOUND"}, 404)
        if parse_qs(parsed.query).get("revision") != [str(note["revision"])]:
            return self.reply({"code": "REVISION_CONFLICT"}, 409)
        del DATA[key]
        DATA["/notes"]["items"] = [
            row for row in DATA["/notes"]["items"] if row["id"] != note["id"]
        ]
        return self.reply({"deleted": True})

    def do_PATCH(self):
        if self.path.startswith("/api/v1/notes/"):
            fault = SimpleCookie(self.headers.get("Cookie", "")).get("fixture_fault")
            if fault and fault.value == "notes-save-delay":
                time.sleep(2)
            key = self.path.removeprefix("/api/v1")
            note = DATA.get(key)
            if note is None:
                return self.reply({"code": "NOTE_NOT_FOUND"}, 404)
            body = json.loads(
                self.rfile.read(int(self.headers.get("Content-Length", "0")))
            )
            if note["revision"] != body["revision"]:
                return self.reply({"code": "REVISION_CONFLICT"}, 409)
            note.update(
                {
                    **body,
                    "revision": note["revision"] + 1,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            DATA["/notes"]["items"] = [
                {**note, "preview": note["content"][:160]}
                if row["id"] == note["id"]
                else row
                for row in DATA["/notes"]["items"]
            ]
            return self.reply(note)
        identifier = self.path.removeprefix("/api/v1/matrix/")
        task = next((t for t in tasks if t["id"] == identifier), None)
        if task is None:
            return self.reply({"code": "TEST_FIXTURE_WRITE_DISABLED"}, 403)
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        if body.get("revision") != task["revision"]:
            return self.reply({"code": "REVISION_CONFLICT"}, 409)
        task.update(body)
        task["revision"] += 1
        return self.reply(task)


if __name__ == "__main__":
    print(
        "TEST_FIXTURE UI only at http://127.0.0.1:18117 — no real providers/data",
        flush=True,
    )
    ThreadingHTTPServer(
        ("127.0.0.1", 18117), partial(Handler, directory=str(ROOT))
    ).serve_forever()
