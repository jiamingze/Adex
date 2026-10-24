"""Domain selection and bounded terminal evidence; never a trade authorization."""

import re
from .contracts import SkillPlan


def trading_intent(text: str) -> bool:
    return bool(re.search(r"(?<![A-Za-z0-9])(?:MT5|XAUUSD)(?![A-Za-z0-9])|MetaTrader", text, re.I))


def compile_trading(definition, text):
    return SkillPlan(
        definition,
        (),
        "当前只读接入品种为XAUUSD；其他品种不能用黄金数据替代。仅使用已授权本机终端证据；缺失则明确BLOCKED_EXTERNAL。",
    )


async def terminal_context(core, owner):
    observed = await core.call(
        "tools", "trading:read", "POST", "/internal/trading/context", {"symbol": "XAUUSD"}, owner=owner
    )
    # The full read stays in Tools; only bounded bars enter model context. No
    # password, account login, server or personal identity is returned by bridge.
    return {**observed, "frames": {k: v[-30:] for k, v in observed["frames"].items()}}
