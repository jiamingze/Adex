"""Semantic todo proposal; App validates ownership and persists the actual action."""

import asyncio
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from adex_kernel.core import digest
from pydantic import BaseModel, ConfigDict, Field
from adex_agent.models.provider import ProviderFailure


class TodoDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    title: str = Field(min_length=1, max_length=200)
    important: bool = False
    urgent: bool = False
    due_at: str | None = None


SYSTEM = """TODO_ROUTE_V1：理解用户是否要求在Adex待办清单创建一件事。
只返回JSON {"todo":null} 或 {"todo":{"title":"简洁具体行动标题","important":false,"urgent":false,"due_at":null}}。
待办、代办、待处理、加入清单、记一件要做的事均可能表示创建意图，结合用户语义。
否定、讨论如何实现、询问功能、已完成事项不是创建。不要根据助手历史中的承诺创建。
只在用户明确表示重要/紧急时标记，缺省false。明确截止日期用带时区ISO8601，无截止日期null。
不要把定时执行/联网搜索理解为待办创建。标题不要保留“帮我创建待办”等指令前缀。"""


async def todo_draft(runtime, owner, turn, text):
    if not re.search(r"待办|代办|待处理|清单|要做的事", text):
        return None
    prompt = [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": json.dumps(
                {"request": text, "now": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()},
                ensure_ascii=False,
            ),
        },
    ]
    output = ""
    async with asyncio.timeout(25):
        async for event in runtime.invoke(f"todo-route:{turn}:{digest(prompt)[:24]}", owner, prompt):
            if event["type"] == "completed":
                output = event["content"]
    try:
        value = json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", output.strip()))
        if set(value) != {"todo"}:
            raise ValueError()
        if value["todo"] is None:
            return None
        draft = TodoDraft.model_validate(value["todo"])
        if not draft.title.strip():
            raise ValueError()
        if draft.due_at and datetime.fromisoformat(draft.due_at.replace("Z", "+00:00")).tzinfo is None:
            raise ValueError()
        return draft.model_dump()
    except (ValueError, TypeError):
        raise ProviderFailure("INVALID_TODO_DRAFT") from None
