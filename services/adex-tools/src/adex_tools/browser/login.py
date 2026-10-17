"""Read-only login affordances derived from the current actual page, never invented forms."""

import re
from urllib.parse import urlsplit
from adex_tools.browser.policy import CRITICAL

LOGIN = re.compile(r"登录|登入|sign\s*in|log\s*in|继续|下一步|验证|验证码|continue|next|verify", re.I)
ACCOUNT = re.compile(
    r"账号|账户|手机|电话|邮箱|用户名|验证码|password|phone|email|user.?name|account|verification|otp", re.I
)


def access_block(view):
    text = "\n".join(
        n.get("name", "") for n in view.get("nodes", []) if n.get("role") in ("heading", "StaticText")
    )
    if re.search(
        r"(?:^|[\s_-])(?:安全验证|京东验证|人机验证|security verification|verify you are human)(?:$|[\s_-])",
        view.get("title", ""),
        re.I,
    ):
        return {
            "code": "WEBSITE_VERIFICATION_REQUIRED",
            "message": "网站要求完成安全验证，尚未取得查询结果；请在网站页面完成验证后继续。",
            "availability": "BLOCKED_EXTERNAL",
        }
    status = (view.get("network") or {}).get("document_status")
    if status in (403, 429) or re.search(
        r"IP存在风险|检测到.{0,12}异常流量|访问过于频繁|操作太频繁", text, re.I
    ):
        return {
            "code": "NETWORK_ACCESS_RESTRICTED",
            "message": "网站拒绝当前访问或要求降低访问频率；尚未取得查询结果。",
            "availability": "BLOCKED_EXTERNAL",
        }
    if re.search(r"安全限制|访问受限|拒绝访问|access denied|access blocked", text, re.I) and re.search(
        r"IP.{0,12}(风险|封禁|blocked)|异常流量|网络环境|unusual traffic|network.{0,12}blocked", text, re.I
    ):
        return {
            "code": "NETWORK_ACCESS_RESTRICTED",
            "message": "网站限制了当前浏览器的访问，尚未进入可登录页面。",
            "availability": "BLOCKED_EXTERNAL",
        }
    return None


def login_form(view):
    if access_block(view):
        return None
    url = urlsplit(view.get("url", ""))
    if url.scheme != "https" or not url.hostname:
        return None
    nodes = view.get("nodes", [])
    fields = [
        {
            "id": n["id"],
            "label": n.get("name") or "网站输入框",
            "secret": bool(n.get("protected")),
            "type": n.get("input_type", "text"),
        }
        for n in nodes
        if n.get("id")
        and n.get("role") in ("textbox", "searchbox")
        and n.get("frame_origin", f"https://{url.netloc}") == f"https://{url.netloc}"
        and (
            n.get("protected")
            or ACCOUNT.search(n.get("name", ""))
            or n.get("input_type") in ("email", "tel")
            or n.get("autocomplete") == "username"
        )
    ][:6]
    buttons = [
        {"id": n["id"], "label": n.get("name", "")}
        for n in nodes
        if n.get("id")
        and n.get("role") == "button"
        and LOGIN.search(n.get("name", ""))
        and (
            not CRITICAL.search(n.get("name", ""))
            or re.fullmatch(r"发送(?:短信)?验证码|send (?:verification )?code", n.get("name", ""), re.I)
        )
    ][:6]
    if not fields or not buttons:
        return None
    buttons.sort(key=lambda b: bool(re.search(r"获取|发送|send|request", b["label"], re.I)))
    notices = [
        n.get("name", "")
        for n in nodes
        if n.get("role") == "StaticText"
        and re.search(r"协议|条款|隐私|terms|privacy", n.get("name", ""), re.I)
    ][:4]
    return {
        "origin": f"https://{url.netloc}",
        "observation_id": view.get("observation_id", ""),
        "fields": fields,
        "buttons": buttons,
        "notices": notices,
    }
