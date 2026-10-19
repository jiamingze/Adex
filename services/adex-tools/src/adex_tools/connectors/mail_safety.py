"""Keep obvious authentication messages out of ordinary agent mailbox context."""

SENSITIVE_SUBJECTS = (
    "verification code",
    "security code",
    "one-time",
    "one time",
    "sign-in code",
    "login code",
    "password reset",
    "reset your password",
    "magic link",
    "验证码",
    "动态口令",
    "重置密码",
    "登录链接",
    "登入連結",
)


def safe_metadata(headers):
    """Conservative metadata filter, not a claim of complete secret detection."""
    subject = " ".join(
        str(h.get("value", "")) for h in headers if str(h.get("name", "")).lower() == "subject"
    )
    if any(term in subject.casefold() for term in SENSITIVE_SUBJECTS):
        return [{"name": "Subject", "value": "[安全验证邮件：请在原邮箱查看]"}], True
    # Ignore unsolicited provider fields; metadata must not include body or URLs.
    return [h for h in headers if str(h.get("name", "")).lower() in ("subject", "from", "message-id")], False
