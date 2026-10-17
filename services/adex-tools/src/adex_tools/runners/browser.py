"""Read-only Chromium runner orchestration; no service credentials in the child."""

import asyncio
import json
import os
import sys
from fastapi import HTTPException
from adex_tools.runners.browser_policy import (
    allowed_url as allowed_url,
    admitted_hosts,
)  # allowed_url remains a compatible import


_slots = asyncio.Semaphore(2)


async def read_page(url, query="", max_pages=3):
    try:
        await asyncio.wait_for(_slots.acquire(), 1)
    except TimeoutError:
        raise HTTPException(429, "BROWSER_BUSY") from None
    try:
        return await _read_page(url, query, max_pages)
    finally:
        _slots.release()


async def _read_page(url, query="", max_pages=3):
    hosts = admitted_hosts(url)
    if not 1 <= max_pages <= 3:
        raise HTTPException(400, "BROWSER_PAGE_LIMIT")
    environment = {
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
            "ADEX_BROWSER_DIRECT_FALLBACK",
            "ADEX_BROWSER_CHANNEL",
        )
    }
    child = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "adex_tools.runners.browser_runner",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env=environment,
        start_new_session=True,
    )
    try:
        output, _ = await asyncio.wait_for(
            child.communicate(
                json.dumps(
                    {"url": url, "query": query[:300], "hosts": hosts, "max_pages": max_pages}
                ).encode()
            ),
            45,
        )
        if child.returncode or len(output) > 160000:
            raise HTTPException(503, "BROWSER_UNAVAILABLE")
        result = json.loads(output)
        if result.get("error"):
            raise HTTPException(503, result["error"])
        return result
    except (TimeoutError, ValueError):
        raise HTTPException(503, "BROWSER_TIMEOUT") from None
    finally:
        if child.returncode is None:
            import signal

            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await child.wait()
