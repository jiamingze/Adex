"""Admission and DNS pinning for credential-free public browser reads."""

import ipaddress
import os
import re
import socket
from urllib.parse import urlsplit
from fastapi import HTTPException

DEFAULT_HOSTS = (
    "github.com",
    "raw.githubusercontent.com",
    "github.githubassets.com",
    "avatars.githubusercontent.com",
)


def allowed_url(url, hosts=DEFAULT_HOSTS):
    try:
        value = urlsplit(url)
        return bool(
            len(url) <= 2000
            and not any(ord(c) <= 32 or c == "\\" for c in url)
            and value.scheme == "https"
            and value.hostname in hosts
            and value.port in (None, 443)
            and not value.username
            and not value.password
            and not value.fragment
        )
    except ValueError:
        return False


def admitted_hosts(url):
    mode = os.getenv("ADEX_BROWSER_MODE", "public")
    if mode not in ("public", "allowlist"):
        raise HTTPException(503, "BROWSER_POLICY_INVALID")
    configured = tuple(
        filter(
            None,
            (
                h.strip().lower()
                for h in os.getenv("ADEX_BROWSER_ALLOWED_HOSTS", ",".join(DEFAULT_HOSTS)).split(",")
            ),
        )
    )
    try:
        host = urlsplit(url).hostname or ""
        # No IP literals, single-label hosts, alternate numeric IP forms or DNS
        # suffix guessing. Every admitted DNS answer is validated below as well.
        labels = host.split(".")
        valid = (
            len(host) <= 253
            and len(labels) >= 2
            and bool(re.fullmatch(r"[a-z]{2,63}", labels[-1]))
            and all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels[:-1])
        )
        if not valid or not allowed_url(url, (host,)) or (mode == "allowlist" and host not in configured):
            raise ValueError()
    except ValueError:
        raise HTTPException(400, "BROWSER_URL_NOT_ALLOWED") from None
    return tuple(dict.fromkeys((host, *configured))) if mode == "public" else configured


def resolve_public_hosts(hosts, resolver=None):
    resolver = resolver or socket.getaddrinfo
    pinned = {}
    for host in dict.fromkeys(hosts):
        if not re.fullmatch(r"[a-z0-9.-]{1,253}", host):
            continue
        try:
            # Inspect A and AAAA: a mixed public/private answer is rejected, not
            # reduced to its public subset. Chromium receives a fixed IPv4 map.
            addresses = {row[4][0] for row in resolver(host, 443, type=socket.SOCK_STREAM)}
            if not addresses or not all(ipaddress.ip_address(ip).is_global for ip in addresses):
                continue
            ipv4 = sorted(ip for ip in addresses if ipaddress.ip_address(ip).version == 4)
            if ipv4:
                pinned[host] = ipv4[0]
        except (OSError, ValueError):
            continue
    return pinned
