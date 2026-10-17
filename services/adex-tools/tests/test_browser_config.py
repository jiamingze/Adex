import asyncio
import pytest
from adex_tools.runners.browser_config import upstream_proxy, browser_channel
from adex_tools.runners.browser_proxy import BrowserEgress


@pytest.mark.parametrize(
    "value",
    [
        "https://127.0.0.1:7890",
        "http://user:secret@127.0.0.1:7890",
        "http://example.com:80",
        "http://127.0.0.1:7890/path",
        "http://127.0.0.1:7890?token=secret",
        "http://127.0.0.1",
        "http://127.0.0.1:99999",
    ],
)
def test_proxy_is_explicit_loopback_and_no_credentials(value):
    with pytest.raises(ValueError, match="BROWSER_UPSTREAM_PROXY_INVALID"):
        upstream_proxy(value)


def test_invalid_browser_channel_is_not_an_executable_path(monkeypatch):
    monkeypatch.setenv("ADEX_BROWSER_CHANNEL", "/tmp/unsafe-browser")
    with pytest.raises(ValueError, match="BROWSER_CHANNEL_INVALID"):
        browser_channel()


async def test_upstream_only_receives_validated_pinned_ip():
    targets = []

    async def proxy(reader, writer):
        targets.append(await reader.readuntil(b"\r\n\r\n"))
        writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        await writer.drain()
        data = await reader.read(100)
        writer.write(data)
        await writer.drain()
        writer.close()

    upstream = await asyncio.start_server(proxy, "127.0.0.1", 0)
    egress = BrowserEgress(
        {"example.com": "93.184.215.14"}, f"http://127.0.0.1:{upstream.sockets[0].getsockname()[1]}"
    )
    server = await asyncio.start_server(egress.handle, "127.0.0.1", 0, limit=8192)
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", server.sockets[0].getsockname()[1])
        writer.write(b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\n")
        await writer.drain()
        assert b"200" in await reader.readuntil(b"\r\n\r\n")
        writer.write(b"opaque TLS bytes")
        await writer.drain()
        assert await reader.read(100) == b"opaque TLS bytes"
        writer.close()
        await writer.wait_closed()
        assert targets == [b"CONNECT 93.184.215.14:443 HTTP/1.1\r\nHost: 93.184.215.14:443\r\n\r\n"]
    finally:
        server.close()
        upstream.close()
        await server.wait_closed()
        await egress.close()
        await upstream.wait_closed()


def test_source_url_keeps_product_not_credentials():
    from adex_tools.browser.policy import public_source_url

    assert (
        public_source_url("https://shop.example/item?id=123&token=secret&session=x#abc")
        == "https://shop.example/item?id=123"
    )
    assert public_source_url("https://user:secret@shop.example/item") == ""
    assert (
        public_source_url("https://shop.example/item?id=a.b.c&sku=256GB&password=x")
        == "https://shop.example/item?sku=256GB"
    )


@pytest.mark.parametrize(
    "target,allowed,expected",
    [
        ("api.shop.example.co.uk", "www.example.co.uk", True),
        ("evil-example.com", "example.com", False),
        ("b.github.io", "a.github.io", False),
        ("api.a.github.io", "a.github.io", True),
        ("127.0.0.1", "example.com", False),
    ],
)
def test_read_scope_uses_private_public_suffix(target, allowed, expected):
    from adex_tools.browser.policy import same_read_site

    assert same_read_site(target, {allowed}) is expected


def test_telemetry_is_denied_not_approved_and_navigation_is_not_dropped():
    from adex_tools.browser.policy import unsolicited_telemetry

    assert unsolicited_telemetry("https://pages.example.com/data/sem_sdk", "fetch", False)
    assert not unsolicited_telemetry("https://example.com/login", "document", True)
    assert not unsolicited_telemetry("https://example.com/collect", "document", True)


@pytest.mark.parametrize(
    "host,method,held",
    [
        ("api.example.com", "GET", False),
        ("api.example.com", "POST", True),
        ("other.example.net", "GET", True),
    ],
)
async def test_same_site_reads_never_authorize_writes_or_other_sites(host, method, held):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from adex_tools.browser.runner import Broker

    broker = Broker()
    broker.test_fixture = False
    broker.page = SimpleNamespace(url="https://www.example.com/")
    broker.read_hosts = {"www.example.com"}
    broker.gesture = "搜索商品"
    broker.admit = AsyncMock(return_value=True)
    broker.forward = AsyncMock()
    request = SimpleNamespace(
        url=f"https://{host}/search",
        resource_type="fetch",
        method=method,
        is_navigation_request=lambda: False,
        post_data_buffer=b"q=test",
        headers={},
    )
    route = SimpleNamespace(request=request, abort=AsyncMock())
    task = asyncio.create_task(broker.intercept(route))
    for _ in range(20):
        if task.done() or broker.pending:
            break
        await asyncio.sleep(0.01)
    assert bool(broker.pending) is held
    if held:
        broker.forward.assert_not_awaited()
        broker.pending["future"].set_result(False)
    await task
    assert broker.forward.await_count == (0 if held else 1)


@pytest.mark.parametrize("fallback", [False, True])
async def test_proxy_failure_fallback_is_opt_in_and_pre_tls_same_pinned_ip(monkeypatch, fallback):
    attempts, direct_bytes = [], []
    real_open = asyncio.open_connection

    async def rejected(reader, writer):
        await reader.readuntil(b"\r\n\r\n")
        writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def direct(reader, writer):
        data = await reader.read(100)
        direct_bytes.append(data)
        writer.write(data)
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    proxy = await asyncio.start_server(rejected, "127.0.0.1", 0)
    target = await asyncio.start_server(direct, "127.0.0.1", 0)
    proxy_port, target_port = proxy.sockets[0].getsockname()[1], target.sockets[0].getsockname()[1]

    async def dial(host, port):
        attempts.append((host, port))
        if (host, port) == ("127.0.0.1", proxy_port):
            return await real_open(host, port)
        assert (host, port) == ("93.184.215.14", 443)
        return await real_open("127.0.0.1", target_port)

    monkeypatch.setattr(asyncio, "open_connection", dial)
    egress = BrowserEgress(
        {"example.com": "93.184.215.14"}, f"http://127.0.0.1:{proxy_port}", direct_fallback=fallback
    )
    server = await asyncio.start_server(egress.handle, "127.0.0.1", 0)
    try:
        reader, writer = await real_open("127.0.0.1", server.sockets[0].getsockname()[1])
        writer.write(b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\n")
        await writer.drain()
        if fallback:
            assert b"200" in await reader.readuntil(b"\r\n\r\n")
            writer.write(b"opaque TLS bytes")
            await writer.drain()
            assert await reader.read(100) == b"opaque TLS bytes"
            assert attempts == [("127.0.0.1", proxy_port), ("93.184.215.14", 443)]
            assert direct_bytes == [b"opaque TLS bytes"]
        else:
            assert await reader.read() == b""
            assert attempts == [("127.0.0.1", proxy_port)]
            assert not direct_bytes
        writer.close()
        await writer.wait_closed()
    finally:
        server.close()
        proxy.close()
        target.close()
        await egress.close()
        await server.wait_closed()
        await proxy.wait_closed()
        await target.wait_closed()


@pytest.mark.parametrize(
    "location,admitted",
    [("https://passport.example.com/login", True), ("https://different.example.net/login", False)],
)
async def test_read_redirect_pins_only_same_site_and_never_follows_in_fetch(location, admitted):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from adex_tools.browser.runner import Broker

    broker = Broker()
    broker.test_fixture = False
    broker.read_hosts = {"www.example.com"}
    broker.admit = AsyncMock(return_value=True)
    response = SimpleNamespace(status=302, headers={"location": location})
    request = SimpleNamespace(
        url="https://www.example.com/search", method="GET", is_navigation_request=lambda: True
    )
    route = SimpleNamespace(request=request, fetch=AsyncMock(return_value=response), fulfill=AsyncMock())
    await broker.forward(route)
    route.fetch.assert_awaited_once_with(max_redirects=0, max_retries=0, timeout=10000)
    assert broker.admit.await_count == (1 if admitted else 0)
    assert ("passport.example.com" in broker.read_hosts) is admitted
    route.fulfill.assert_awaited_once_with(response=response)
