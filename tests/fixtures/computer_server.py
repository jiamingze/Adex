"""Loopback-only synthetic computer approval UI; never invokes the native runner."""

from functools import partial
from http.server import ThreadingHTTPServer
from urllib.parse import urlparse
from experience_server import CONVERSATION, DATA, ROOT, Handler, iso

ACTION = {
    "id": "00000000-0000-4000-8000-000000000017",
    "kind": "computer.step",
    "state": "PENDING",
    "request_hash": "TEST_FIXTURE",
    "expires_at": iso(1),
    "request": {
        "origin_conversation_id": CONVERSATION,
        "payload": {
            "app": "计算器",
            "control": "加",
            "action": "press",
            "element_id": "0.1",
            "text": "",
        },
    },
}
DATA["/actions"] = {"items": [ACTION]}
DATA["/conversations"] = {
    "items": [
        {"id": CONVERSATION, "title": "TEST_FIXTURE Mac 操作", "updated_at": iso(0)}
    ]
}


class ComputerHandler(Handler):
    def do_GET(self):
        if (
            urlparse(self.path).path
            == "/api/v1/conversations/" + CONVERSATION + "/messages"
        ):
            return self.reply(
                {
                    "items": [
                        {
                            "id": "fixture-computer-message",
                            "role": "assistant",
                            "seq": 1,
                            "content": "TEST_FIXTURE：请确认下一步操作。此演示不会操作电脑。",
                            "cards": [
                                {
                                    "schema_version": 1,
                                    "type": "computer_approval",
                                    "card_id": "fixture-computer-card",
                                    "conversation_id": CONVERSATION,
                                    "message_id": "fixture-computer-message",
                                    "actions": [],
                                    "data": {"action_id": ACTION["id"]},
                                }
                            ],
                        }
                    ],
                    "turns": [],
                    "event_seq": 0,
                }
            )
        return super().do_GET()

    def do_POST(self):
        if self.path in [
            "/api/v1/actions/" + ACTION["id"] + "/" + d for d in ("approve", "revoke")
        ]:
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            ACTION["state"] = (
                "APPROVED" if self.path.endswith("/approve") else "REVOKED"
            )
            return self.reply({"status": ACTION["state"], "fixture": True})
        return super().do_POST()


if __name__ == "__main__":
    print("TEST_FIXTURE http://127.0.0.1:18118; no native execution", flush=True)
    ThreadingHTTPServer(
        ("127.0.0.1", 18118), partial(ComputerHandler, directory=str(ROOT))
    ).serve_forever()
