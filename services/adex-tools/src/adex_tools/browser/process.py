"""Bounded local broker lifecycle. No durable scheduling or recovery ownership."""

import asyncio
import json
import os
import signal
import sys
import time
from fastapi import HTTPException


class BrowserProcess:
    def __init__(self, child):
        self.child = child
        self.lock = asyncio.Lock()
        self.last_used = time.monotonic()
        self.preview = {}
        self.close_lock = asyncio.Lock()

    @classmethod
    async def start(cls):
        env = {
            k: v
            for k, v in os.environ.items()
            if k
            in (
                "PATH",
                "HOME",
                "TMPDIR",
                "LANG",
                "PLAYWRIGHT_BROWSERS_PATH",
                "ADEX_BROWSER_UPSTREAM_PROXY",
                "ADEX_BROWSER_CHANNEL",
                "ADEX_BROWSER_MODE",
                "ADEX_BROWSER_ALLOWED_HOSTS",
            )
        }
        child = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "adex_tools.browser.runner",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=env,
            start_new_session=True,
            limit=4 * 1024 * 1024,
        )
        return cls(child)

    async def call(self, body):
        async with self.lock:
            self.last_used = time.monotonic()
            try:
                self.child.stdin.write(json.dumps(body).encode() + b"\n")
                await self.child.stdin.drain()
                raw = await asyncio.wait_for(
                    self.child.stdout.readline(), 25 if "url" in body and "action" not in body else 18
                )
                value = json.loads(raw)
                if value.get("screenshot"):
                    self.preview = {"screenshot": value["screenshot"]}
                if value.get("error"):
                    raise HTTPException(409, value["error"])
                return value
            except (TimeoutError, ValueError, OSError):
                await self.close()
                raise HTTPException(409, "BROWSER_SESSION_LOST") from None

    async def close(self):
        async with self.close_lock:
            if self.child.returncode is None:
                # Let Chromium/Playwright close their pipes before terminating the process.
                # Abrupt SIGTERM alone leaves asyncio transports alive at loop teardown.
                try:
                    self.child.stdin.write(b'{"action":"close"}\n')
                    await self.child.stdin.drain()
                    await asyncio.wait_for(self.child.wait(), 3)
                except (TimeoutError, OSError, ConnectionError):
                    try:
                        os.killpg(self.child.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                    try:
                        await asyncio.wait_for(self.child.wait(), 3)
                    except TimeoutError:
                        try:
                            os.killpg(self.child.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        await self.child.wait()
            self.child.stdin.close()
            try:
                await self.child.stdin.wait_closed()
            except (OSError, ConnectionError):
                pass
            self.preview = {}


class BrowserPool:
    def __init__(self):
        self.items = {}
        self.lock = asyncio.Lock()

    async def get(self, session, init):
        async with self.lock:
            for key, item in list(self.items.items()):
                if time.monotonic() - item.last_used > 1200 or item.child.returncode is not None:
                    await item.close()
                    self.items.pop(key, None)
            if session not in self.items:
                if len(self.items) >= 4:
                    raise HTTPException(429, "BROWSER_BUSY")
                actor = await BrowserProcess.start()
                try:
                    await actor.call(init)
                except BaseException:
                    await actor.close()
                    raise
                self.items[session] = actor
            return self.items[session]

    async def close(self, session=None):
        for key in list(self.items) if session is None else [session]:
            item = self.items.pop(key, None)
            if item:
                await item.close()
