"""Generic browser policy; no website-specific selectors or flow scripts."""

from email.parser import BytesParser
from email.policy import default as email_policy
import hashlib
import json
import re
from urllib.parse import parse_qsl, urlsplit
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

SECRET = re.compile(
    r"password|passwd|secret|token|cookie|authorization|captcha|credential|signature|csrf|xsrf|session|otp|one.time|验证码|密码|cvv|card.?number",
    re.I,
)
CRITICAL = re.compile(
    r"发布|发表|付款|支付|下单|提交订单|确认购买|删除|发送|publish|post now|pay|place order|buy now|checkout|delete|send",
    re.I,
)


class BrowserStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal[
        "navigate", "click", "type", "select", "scroll", "back", "upload", "switch_tab", "handoff", "done"
    ]
    element_id: str = Field(default="", max_length=100)
    text: str = Field(default="", max_length=16000)
    url: str = Field(default="", max_length=2000)
    file_id: str = Field(default="", max_length=40)
    reason: str = Field(default="", max_length=400)


def redact(value, key=""):
    if SECRET.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): redact(v, str(k)) for k, v in list(value.items())[:100]}
    if isinstance(value, list):
        return [redact(v) for v in value[:100]]
    return str(value)[:16000] if value is not None else None


def request_preview(url, method, data, content_type=""):
    parsed = urlsplit(url)
    safe_url = parsed._replace(query="").geturl()
    parsed_body = True
    try:
        if "multipart/form-data" in content_type:
            message = BytesParser(policy=email_policy).parsebytes(
                ("Content-Type: " + content_type + "\r\nMIME-Version: 1.0\r\n\r\n").encode() + data
            )
            fields = {}
            for part in list(message.iter_parts())[:30]:
                name = part.get_param("name", header="content-disposition") or "field"
                value = part.get_payload(decode=True) or b""
                fields[name] = (
                    {
                        "filename": part.get_filename(),
                        "bytes": len(value),
                        "sha256": hashlib.sha256(value).hexdigest(),
                    }
                    if part.get_filename()
                    else value.decode("utf-8", errors="replace")[:16000]
                )
            fields = redact(fields)
            return {
                "destination": safe_url,
                "method": method,
                "query": redact(dict(parse_qsl(parsed.query))),
                "fields": fields,
                "body_sha256": hashlib.sha256(data).hexdigest(),
                "reviewable": True,
            }
        fields = (
            json.loads(data.decode())
            if "json" in content_type
            else dict(parse_qsl(data.decode()))
            if "urlencoded" in content_type
            else {"content_type": content_type, "bytes": len(data)}
        )
    except (ValueError, UnicodeError):
        parsed_body = False
        fields = {"content_type": content_type, "bytes": len(data)}
    return {
        "destination": safe_url,
        "method": method,
        "query": redact(dict(parse_qsl(parsed.query))),
        "fields": redact(fields),
        "body_sha256": hashlib.sha256(data).hexdigest(),
        "reviewable": parsed_body
        and ("json" in content_type or "urlencoded" in content_type or method in ("GET", "HEAD", "OPTIONS")),
    }


def request_digest(url, method, data):
    return hashlib.sha256(method.encode() + b"\0" + url.encode() + b"\0" + data).hexdigest()


def receipt_id(value):
    if not isinstance(value, dict):
        return None
    if value.get("success") is False or value.get("error"):
        return None
    for key in ("order_id", "orderId", "orderNo", "note_id", "noteId", "post_id", "postId", "reservation_id"):
        item = value.get(key)
        if isinstance(item, (str, int)) and 3 <= len(str(item)) <= 100:
            return str(item)
    for key in ("data", "result"):
        found = receipt_id(value.get(key))
        if found:
            return found
    return None


def approval_summary(pending):
    """Display only: never used as authority to approve or verify an operation."""
    gesture = pending.get("gesture", "")
    kind = (
        "发布内容"
        if re.search("发布|发表|publish|post now", gesture, re.I)
        else "提交订单"
        if re.search("下单|购买|place order|buy now|checkout", gesture, re.I)
        else "付款请求"
        if re.search("付款|支付|pay", gesture, re.I)
        else "访问新网站"
        if pending.get("grant_read_host")
        else "网页请求"
    )
    nodes = pending.get("before", {}).get("nodes", [])
    fields = [
        {"label": node.get("name") or "输入内容", "value": node.get("value", "")}
        for node in nodes
        if node.get("role") in ("textbox", "combobox", "searchbox")
        and node.get("value")
        and not node.get("protected")
    ][:20]
    texts = [node.get("name", "") for node in nodes if node.get("role") in ("StaticText", "heading")]
    facts = []
    for index, text in enumerate(texts):
        if re.search(
            r"实付|合计|总计|总额|运费|价格|应付|¥|￥|颜色|尺码|规格|数量|收货|配送|卖家|店铺|商品|total|shipping|price|quantity|size|seller",
            text,
            re.I,
        ):
            facts.append(" ".join(texts[index : index + 3])[:400])
    return {
        "kind": kind,
        "page_url": pending.get("before", {}).get("url", ""),
        "fields": fields,
        "facts": facts[:12],
    }
