"""Domain selection and bounded terminal evidence; never a trade authorization."""

import re
from .contracts import SkillPlan


def trading_intent(text: str) -> bool:
    if re.search(r"(?<![A-Za-z0-9])(?:MT5|XAUUSD)(?![A-Za-z0-9])|MetaTrader", text, re.I):
        return True
    # Normalize common spot-gold language, not all uses of the word gold.
    # Physical purchases and explicitly different instruments keep their own
    # domain; they must never inherit XAUUSD pricing or order assumptions.
    if re.search(r"金条|金饰|首饰|项链|戒指|手镯|实物|ETF|期货|黄金时代|黄金分割", text, re.I):
        return False
    return bool(re.search(r"黄金|伦敦金", text)) and bool(
        re.search(
            r"交易|做多|做空|开仓|平仓|建仓|挂单|撤单|买入|卖出|止盈|止损|(?:下|开|买|卖|来).{0,12}(?:单|手)|\d+(?:\.\d+)?\s*手",
            text,
        )
    )


def native_mt5_request(text: str) -> bool:
    """Explicit terminal domain outranks commerce; past assistant sites grant nothing."""
    if not trading_intent(text):
        return False
    if re.search(r"下单|挂单|撤单|开仓|平仓|买入|卖出", text):
        return True
    # A website teaching MT5 is still a website, not a terminal operation.
    return not re.search(r"官网|网站|网页|教程|文档|下载|安装|https?://", text, re.I)


def trading_context_request(messages) -> str | None:
    """Carry only contiguous user trading/delegation turns; never assistant claims."""
    chain = []
    for message in [m for m in messages if m.get("role") == "user"][-8:]:
        text = str(message.get("content", ""))[:1500]
        if re.search(r"金条|金饰|首饰|项链|戒指|手镯|实物|ETF|期货", text, re.I):
            chain = []
        elif native_mt5_request(text):
            if chain and re.fullmatch(r"[用改成换到请\s]*(?:MT5|mt5)[啊安吧。！!\s]*", text):
                chain.append(text)
            else:
                chain = [text]
        elif chain and (
            re.search(
                r"挂单|止盈|止损|入场|手数|走势|K线|报价|订单草案|刚才的分析|下单流程|交易流程|怎么下单|如何下单",
                text,
                re.I,
            )
            or (re.search(r"ChatGPT", text, re.I) and re.search(r"分析|截图|建议|行情|数据", text))
            or re.fullmatch(
                r"(?:浏览器|网页|客户端|都行|你来决定|你决定|随便|继续分析|继续|可以|好的|好|就这样|吧|啊|，|、|。|\s)+",
                text,
            )
        ):
            chain.append(text)
        else:
            chain = []
    return "\n".join(chain) if chain else None


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
