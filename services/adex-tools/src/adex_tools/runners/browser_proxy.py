"""Per-run CONNECT-only egress: redirects cannot bypass pinned public DNS.

No TLS interception, credentials, arbitrary ports or general HTTP proxying. The
listener exists only for the lifetime of the credential-free browser child.
"""

import asyncio
import os
from adex_tools.runners.browser_config import upstream_proxy


class BrowserEgress:
    def __init__(self, pinned, proxy=None, direct_fallback=None):
        self.upstream_proxy = upstream_proxy(proxy)
        self.direct_fallback = (
            (os.getenv("ADEX_BROWSER_DIRECT_FALLBACK", "0") == "1")
            if direct_fallback is None
            else direct_fallback
        )
        self.pinned = pinned
        self.active = 0
        self.connections = set()

    async def close(self):
        tasks = list(self.connections)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def handle(self, reader, writer):
        connection = asyncio.current_task()
        self.connections.add(connection)
        upstream = None
        tasks = []
        admitted = False
        try:
            if self.active >= 32:
                return
            self.active += 1
            admitted = True
            header = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 4)
            method, authority, version = header.split(b"\r\n", 1)[0].decode("ascii").split(" ")
            host, port = authority.rsplit(":", 1)
            if method != "CONNECT" or version != "HTTP/1.1" or port != "443" or host not in self.pinned:
                writer.write(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n")
                await writer.drain()
                return
            # The trusted local proxy receives a pinned IP, never target DNS or cookies.
            # TLS stays end-to-end in Chromium with the original hostname/certificate.
            try:
                if self.upstream_proxy:
                    remote, upstream = await asyncio.wait_for(
                        asyncio.open_connection(*self.upstream_proxy), 6
                    )
                    target = self.pinned[host] + ":443"
                    upstream.write(f"CONNECT {target} HTTP/1.1\r\nHost: {target}\r\n\r\n".encode("ascii"))
                    await upstream.drain()
                    response = await asyncio.wait_for(remote.readuntil(b"\r\n\r\n"), 6)
                    status = response.split(b"\r\n", 1)[0].split()
                    if len(status) < 2 or status[1] != b"200":
                        raise OSError("BROWSER_PROXY_CONNECT_REJECTED")
                else:
                    remote, upstream = await asyncio.wait_for(
                        asyncio.open_connection(self.pinned[host], 443), 6
                    )
            except (OSError, TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
                if not self.upstream_proxy or not self.direct_fallback:
                    raise
                if upstream:
                    upstream.close()
                    try:
                        await asyncio.wait_for(upstream.wait_closed(), 1)
                    except (OSError, TimeoutError):
                        pass
                # Only connection establishment may fall back, before TLS or any HTTP
                # request bytes are sent. Never retry a dispatched POST or change DNS.
                remote, upstream = await asyncio.wait_for(asyncio.open_connection(self.pinned[host], 443), 6)
            writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await writer.drain()

            async def relay(source, destination):
                total = 0
                while chunk := await source.read(65536):
                    total += len(chunk)
                    if total > 8 * 1024 * 1024:
                        return
                    destination.write(chunk)
                    await destination.drain()

            tasks = [asyncio.create_task(relay(reader, upstream)), asyncio.create_task(relay(remote, writer))]
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        except (
            OSError,
            ValueError,
            UnicodeError,
            TimeoutError,
            asyncio.IncompleteReadError,
            asyncio.LimitOverrunError,
        ):
            pass
        finally:
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            if upstream:
                upstream.close()
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), 1)
                if upstream:
                    await asyncio.wait_for(upstream.wait_closed(), 1)
            except (OSError, TimeoutError):
                pass
            if admitted:
                self.active -= 1
            self.connections.discard(connection)
