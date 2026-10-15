"""Per-run CONNECT-only egress: redirects cannot bypass pinned public DNS.

No TLS interception, credentials, arbitrary ports or general HTTP proxying. The
listener exists only for the lifetime of the credential-free browser child.
"""

import asyncio


class BrowserEgress:
    def __init__(self, pinned):
        self.pinned = pinned
        self.active = 0

    async def handle(self, reader, writer):
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
            if admitted:
                self.active -= 1
