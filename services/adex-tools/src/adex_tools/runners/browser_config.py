"""Trusted deployment browser settings; never supplied by a model or website."""

import os
from urllib.parse import urlsplit


def upstream_proxy(value=None):
    raw = os.getenv("ADEX_BROWSER_UPSTREAM_PROXY", "") if value is None else value
    if not raw:
        return None
    try:
        parsed = urlsplit(raw)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in ("127.0.0.1", "::1")
            or parsed.username
            or parsed.password
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
            or not parsed.port
        ):
            raise ValueError()
        return parsed.hostname, parsed.port
    except ValueError:
        raise ValueError("BROWSER_UPSTREAM_PROXY_INVALID") from None


def browser_channel():
    value = os.getenv("ADEX_BROWSER_CHANNEL", "chromium")
    if value not in ("chromium", "chrome"):
        raise ValueError("BROWSER_CHANNEL_INVALID")
    return value
