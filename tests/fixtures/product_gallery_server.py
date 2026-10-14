"""Synthetic product gallery. Loopback only; no accounts, DB or providers.

Run: pnpm --dir apps/web build && uv run python tests/fixtures/product_gallery_server.py
"""

from functools import partial
from http.server import ThreadingHTTPServer
from urllib.parse import urlparse

from experience_server import CONVERSATION, DATA, ROOT, Handler, iso

DATA["/me"]["username"] = "演示用户"
DATA["/conversations"]["items"] = [
    {"id": CONVERSATION, "title": "设计一个可靠的个人助手", "updated_at": iso(-1)},
]
DATA["/notifications"]["items"][0]["body"] = (
    "今日科技简报已整理：开源模型、开发工具与航天动态，回到会话查看详细内容。"
)
DATA["/notifications"]["items"][1]["body"] = (
    "关注的开源项目发布了新版本，已整理主要变化与升级建议。"
)
DATA["/notes/fixture-note"].update(
    title="个人助手 · 产品设计笔记",
    content="目标\n让日历、待办和对话成为一个连续的工作流。\n\n核心体验\n• 今日：先看到需要关注的事，再查看接下来的安排。\n• 待办：重要性与紧急程度独立标记。\n• 聊天：将有价值的回复整理为笔记。\n\n可靠性\n操作前审批，执行后验证；后台任务可以恢复。\n\n下一步\n验证移动端交互，收集反馈，再迭代。",
)
DATA["/notes"]["items"][0].update(
    title=DATA["/notes/fixture-note"]["title"],
    preview="让日历、待办和对话成为一个连续的工作流。",
)
MESSAGES = [
    {"role": "user", "content": "帮我梳理一个可靠的个人助手应该怎么设计。"},
    {
        "role": "assistant",
        "content": "可以从三个层次开始：\n\n### 把每天的事组织起来\n把日历、优先待办和后台结果放在同一个入口。\n\n| 场景 | 设计重点 |\n| --- | --- |\n| 日常对话 | 流式回答、可中止、上下文记忆 |\n| 定时工作 | 持久化任务、失败恢复、结果回填 |\n| 外部操作 | 明确审批、幂等执行、验证回执 |\n\n**把讨论结论转成笔记，方便后续查阅。**",
    },
]


class GalleryHandler(Handler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == f"/api/v1/conversations/{CONVERSATION}/messages":
            return self.reply(
                {
                    "items": [
                        {
                            **message,
                            "id": f"gallery-message-{i}",
                            "seq": i + 1,
                            "turn_id": f"gallery-turn-{i}",
                            "created_at": iso(-1),
                        }
                        for i, message in enumerate(MESSAGES)
                    ],
                    "turns": [],
                    "event_seq": 0,
                }
            )
        if path.startswith("/api/v1") or path.startswith("/assets/"):
            return super().do_GET()
        raw = (
            (ROOT / "index.html")
            .read_bytes()
            .replace(
                b"</body>",
                '<span style="position:fixed;right:12px;top:52px;z-index:9999;pointer-events:none;font:10px system-ui;color:#64748b;background:#f1f5f9;padding:3px 7px;border-radius:9px">演示数据 · Synthetic demo</span></body>'.encode(),
            )
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


if __name__ == "__main__":
    print(
        "TEST_FIXTURE gallery: http://127.0.0.1:18117; no external execution",
        flush=True,
    )
    ThreadingHTTPServer(
        ("127.0.0.1", 18117), partial(GalleryHandler, directory=str(ROOT))
    ).serve_forever()
