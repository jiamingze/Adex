"""Compile explicit travel requests; ambiguous constraints remain visible assumptions."""

import re
from .contracts import SkillDefinition, SkillPlan

_NUMBERS = {
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
    "十": 10,
}


def requested_days(text: str) -> int | None:
    matches = list(
        re.finditer(
            r"(?<![\d第一二两三四五六七八九十])(\d{1,2}|[一二两三四五六七八九]?十[一二三四五六七八九]?|[一二两三四五六七八九])\s*(?:天(?!气)|日游)",
            text,
        )
    )
    match = matches[-1] if matches else None
    if not match:
        return None
    number = match[1]
    if number.isdigit():
        value = int(number)
    elif "十" in number:
        tens, units = number.split("十")
        value = _NUMBERS.get(tens, 1) * 10 + _NUMBERS.get(units, 0)
    else:
        value = _NUMBERS.get(number)
    return value if value and 1 <= value <= 30 else None


def compile_travel(definition: SkillDefinition, text: str) -> SkillPlan:
    days = requested_days(text)
    action = (
        "order"
        if re.search(r"下单|订酒店|预订酒店|订房|付款|购买.*票", text)
        else ("reservation" if re.search(r"预约|订票|预订", text) else "plan")
    )
    policy = (
        f"用户明确天数为{days}天，必须覆盖第1天至第{days}天，不能固定输出四天。"
        if days
        else "天数未明确时给出合理草案并标注假设，不默认用户要求四天。"
    )
    if action != "plan":
        policy += "\n本轮包含交易请求：预约/下单接口未接入，只能规划与查证，必须明确未创建预约或订单。"
    # Bounded sequential retrieval: each request passes Tools' existing per-owner
    # budget/auth gate. No browsing checkout, parallel paid fanout or new privileges.
    base = text[:220]
    queries = (
        base + " 官方旅游指南 景点 地理区域 路线",
        base + " 官方 景点营业时间 预约要求 交通 出行时间",
    )
    return SkillPlan(definition, queries, policy, action)
