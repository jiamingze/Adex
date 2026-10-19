import re

from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ConfigDict, Field, model_validator


# Shared with intent routing: accepting a duration must never depend on a second regex.
RELATIVE_TIME = re.compile(
    r"(?<![一二三四五六七八九十两\d])([一二三四五六七八九十两\d]{1,8})\s{0,16}(分钟|小时|秒|minutes?|mins?|hours?|hrs?)\s{0,16}(?:(?:之|以)?后)"
)


class ScheduleDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    instruction: str = Field(min_length=1, max_length=16000)
    kind: Literal["ONCE", "DAILY", "INTERVAL"]
    timezone: str
    first_fire_at: str
    local_time: str | None = None
    interval_seconds: int | None = Field(default=None, ge=60, le=31536000)

    @model_validator(mode="after")
    def validate_rule(self):
        try:
            ZoneInfo(self.timezone)
        except Exception:
            raise ValueError("Invalid IANA timezone") from None
        instant = datetime.fromisoformat(self.first_fire_at.replace("Z", "+00:00"))
        if instant.tzinfo is None:
            raise ValueError("Timezone offset required")
        if self.kind == "DAILY":
            from datetime import time

            if not self.local_time:
                raise ValueError("Daily time required")
            time.fromisoformat(self.local_time)
        if self.kind == "INTERVAL" and self.interval_seconds is None:
            raise ValueError("Interval required")
        return self


def daily_chat_draft(text):
    """Bounded Chinese daily time parser; ambiguous rules require clarification."""
    import re

    if not re.search(r"每天|每日|每晚|每早", text):
        return None
    match = re.search(
        r"(?:每天|每日|每晚|每早)\s{0,16}(上午|早上|早晨|晚上|下午)?\s{0,16}([零一二三四五六七八九十两\d]{1,3})(?:点|:|：)([零一二三四五六七八九十\d]{1,3}分?|半)?",
        text,
    )
    if not match:
        return None

    def number(value):
        if value.isdigit():
            return int(value)
        digits = {
            "零": 0,
            "一": 1,
            "二": 2,
            "两": 2,
            "三": 3,
            "四": 4,
            "五": 5,
            "六": 6,
            "七": 7,
            "八": 8,
            "九": 9,
        }
        if "十" in value:
            a, b = value.split("十", 1)
            return (digits.get(a, 1) * 10) + digits.get(b, 0)
        return digits.get(value, -1)

    hour = number(match[2])
    minute = 30 if match[3] == "半" else number(match[3].removesuffix("分")) if match[3] else 0
    if (match[1] in ("晚上", "下午") or "每晚" in text) and 1 <= hour < 12:
        hour += 12
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        return None
    instruction = text[match.end() :].lstrip("，, ：:").removeprefix("帮我").strip()
    if not instruction:
        return None
    instruction = re.sub(
        r"^(?:帮我)?(?:创建|设置|安排|新建)(?:一个)?定时任务[，, ：:]*", "", instruction
    ).strip()
    instruction = re.sub(r"spacx", "SpaceX", instruction, flags=re.I)
    return {
        "title": instruction[:80],
        "instruction": instruction,
        "kind": "DAILY",
        "timezone": "Asia/Shanghai",
        "local_time": f"{hour:02d}:{minute:02d}",
    }


def relative_chat_draft(text):
    """Relative duration stays relative until App anchors it to durable turn time."""
    import re

    match = RELATIVE_TIME.search(text)
    if not match:
        return None
    raw = match[1]
    digits = dict(zip("一二三四五六七八九", range(1, 10))) | {"两": 2}
    if raw.isdigit():
        count = int(raw)
    elif "十" in raw:
        a, b = raw.split("十", 1)
        count = digits.get(a, 1) * 10 + digits.get(b, 0)
    else:
        count = digits.get(raw, 0)
    unit = match[2].lower()
    seconds = count * (1 if unit == "秒" else 3600 if unit == "小时" or unit.startswith("h") else 60)
    instruction = text[match.end() :].strip(" ，,：:")
    instruction = re.sub(r"^(?:请|帮我|给我|给)", "", instruction).strip()
    if not 1 <= seconds <= 31536000 or not instruction:
        return None
    return {
        "title": instruction[:80],
        "instruction": instruction,
        "kind": "ONCE",
        "timezone": "Asia/Shanghai",
        "delay_seconds": seconds,
    }


INTERVAL_TIME = re.compile(
    r"每(?:隔)?\s{0,16}([一二三四五六七八九十两\d]{1,8})\s{0,16}(分钟|小时|minutes?|mins?|hours?|hrs?|h)(?![a-z])",
    re.I,
)


def interval_chat_draft(text):
    """Interval proposals use Automation occurrences, never a separate polling loop."""
    match = INTERVAL_TIME.search(text)
    if not match:
        return None
    raw = match[1]
    digits = dict(zip("一二三四五六七八九", range(1, 10))) | {"两": 2}
    if raw.isdigit():
        count = int(raw)
    elif "十" in raw:
        a, b = raw.split("十", 1)
        count = digits.get(a, 1) * 10 + digits.get(b, 0)
    else:
        count = digits.get(raw, 0)
    unit = match[2].lower()
    seconds = count * (3600 if unit == "小时" or unit.startswith("h") else 60)
    instruction = text[match.end() :].strip(" ，,：:")
    instruction = re.sub(r"^(?:请|帮我|给我)", "", instruction).strip()
    if not 60 <= seconds <= 31536000 or not instruction:
        return None
    return {
        "title": instruction[:80],
        "instruction": instruction,
        "kind": "INTERVAL",
        "timezone": "Asia/Shanghai",
        "interval_seconds": seconds,
        "notification_policy": "CHANGES_ONLY"
        if any(term in text for term in ("巡检", "有变化", "变化再通知", "有更新"))
        else "EVERY_RUN",
    }


async def semantic_chat_draft(runtime, owner, turn, text):
    """Resolve nonstandard timing as a proposal only; App owns validation and writes."""
    import asyncio
    import json
    from adex_kernel.text import strip_json_fence

    messages = [
        {
            "role": "system",
            "content": 'SCHEDULE_CHAT_V1: 识别定时执行请求，只返回JSON {"draft":null} 或 {"draft":{'
            '"title":"简洁标题","instruction":"实际执行内容，不含创建承诺",'
            '"kind":"ONCE/DAILY/INTERVAL","timezone":"Asia/Shanghai",'
            '"first_fire_at":"带时区ISO8601未来时间","local_time":"DAILY的HH:mm",'
            '"interval_seconds":600}}。省略不适用的字段。否定、讨论功能、时间不明确返回null。'
            "INTERVAL至少60秒。当前时间为" + datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        },
        {"role": "user", "content": text},
    ]
    try:
        async with asyncio.timeout(25):
            output = ""
            async for event in runtime.invoke("schedule-chat:" + str(turn), owner, messages):
                if event["type"] == "completed":
                    output = event["content"]
        parsed = json.loads(strip_json_fence(output))
        if set(parsed) != {"draft"} or parsed["draft"] is None:
            return None
        draft = ScheduleDraft.model_validate(parsed["draft"])
        if datetime.fromisoformat(draft.first_fire_at.replace("Z", "+00:00")) <= datetime.now(
            ZoneInfo("UTC")
        ):
            return None
        return draft.model_dump(exclude_none=True)
    except (ValueError, TypeError, TimeoutError):
        return None
