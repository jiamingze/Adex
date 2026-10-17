"""Browser policy tests are local fixtures, never evidence of external reads."""

import socket
from fastapi import HTTPException
import pytest
from adex_tools.runners.browser_policy import admitted_hosts, resolve_public_hosts


def dns(*addresses):
    return lambda *args, **kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443)) for ip in addresses
    ]


def test_public_destination_and_explicit_allowlist(monkeypatch):
    monkeypatch.delenv("ADEX_BROWSER_ALLOWED_HOSTS", raising=False)
    monkeypatch.delenv("ADEX_BROWSER_MODE", raising=False)
    assert "docs.python.org" in admitted_hosts("https://docs.python.org/3/")
    monkeypatch.setenv("ADEX_BROWSER_MODE", "allowlist")
    with pytest.raises(HTTPException):
        admitted_hosts("https://docs.python.org/3/")
    monkeypatch.setenv("ADEX_BROWSER_ALLOWED_HOSTS", "docs.python.org")
    assert admitted_hosts("https://docs.python.org/3/") == ("docs.python.org",)
    with pytest.raises(HTTPException):
        admitted_hosts("https://docs.python.org.evil.test/")


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "file:///etc/passwd",
        "https://localhost",
        "https://127.0.0.1",
        "https://[::1]",
        "https://2130706433",
        "https://example.com:8443",
        "https://user:secret@example.com",
        "https://example.com\\@127.0.0.1",
        "https://example.com/\nheader",
    ],
)
def test_invalid_and_nonpublic_literal_urls(url):
    with pytest.raises(HTTPException):
        admitted_hosts(url)


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "192.168.1.1", "::1"])
def test_private_or_mixed_dns_fails_closed(ip):
    assert resolve_public_hosts(["example.com"], dns("93.184.215.14", ip)) == {}


def test_dns_is_resolved_once_and_pinned():
    calls = []

    def resolver(*args, **kwargs):
        calls.append(args[0])
        return dns("93.184.215.14")()

    assert resolve_public_hosts(["example.com", "example.com"], resolver) == {"example.com": "93.184.215.14"}
    assert calls == ["example.com"]


def test_invalid_mode_fails_closed(monkeypatch):
    monkeypatch.setenv("ADEX_BROWSER_MODE", "typo")
    with pytest.raises(HTTPException):
        admitted_hosts("https://example.com/")


@pytest.mark.parametrize(
    "authority", ["127.0.0.1:443", "169.254.169.254:443", "example.com:80", "evil.test:443"]
)
async def test_proxy_denies_redirect_destinations_without_dialing(monkeypatch, authority):
    import asyncio
    from adex_tools.runners.browser_proxy import BrowserEgress

    egress = BrowserEgress({"example.com": "93.184.215.14"})
    server = await asyncio.start_server(egress.handle, "127.0.0.1", 0, limit=8192)
    connect = asyncio.open_connection
    calls = []

    async def guarded(host, port, *args, **kwargs):
        calls.append((host, port))
        raise AssertionError("Blocked CONNECT must never dial")

    try:
        reader, writer = await connect("127.0.0.1", server.sockets[0].getsockname()[1])
        monkeypatch.setattr(asyncio, "open_connection", guarded)
        writer.write(f"CONNECT {authority} HTTP/1.1\r\nHost: {authority}\r\n\r\n".encode())
        await writer.drain()
        assert b"403" in await asyncio.wait_for(reader.read(), 2)
        assert calls == []
        writer.close()
        await writer.wait_closed()
    finally:
        server.close()
        await server.wait_closed()
        await egress.close()


def test_related_links_are_bounded_same_host_and_not_action_urls():
    from adex_tools.runners.browser_runner import related_links

    result = related_links(
        [
            {"href": "/docs", "text": "Documentation"},
            {"href": "/logout", "text": "Log out"},
            {"href": "/delete?id=1", "text": "Delete"},
            {"href": "https://evil.test/docs", "text": "Documentation"},
            {"href": "http://127.0.0.1/", "text": "Docs"},
        ],
        "https://example.com/",
        {"example.com": "93.184.215.14"},
        "documentation",
    )
    assert [row["url"] for row in result] == ["https://example.com/docs"]
