"""Read-only Chromium runner orchestration; no service credentials in the child."""

import asyncio
import json
import os
import sys
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
        return (
            value.scheme == "https"
            and value.hostname in hosts
            and value.port in (None, 443)
            and not value.username
            and not value.password
            and not value.fragment
        )
    except ValueError:
        return False


_slots = asyncio.Semaphore(2)


async def read_page(url, query=""):
    async with _slots:
        return await _read_page(url, query)


async def _read_page(url, query=""):
    hosts = tuple(os.getenv("ADEX_BROWSER_ALLOWED_HOSTS", ",".join(DEFAULT_HOSTS)).split(","))
    if not allowed_url(url, hosts):
        raise HTTPException(400, "BROWSER_URL_NOT_ALLOWED")
    environment = {
        k: v
        for k, v in os.environ.items()
        if k in ("PATH", "HOME", "TMPDIR", "LANG", "PLAYWRIGHT_BROWSERS_PATH")
    }
    child = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "adex_tools.browser_runner",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env=environment,
        start_new_session=True,
    )
    try:
        output, _ = await asyncio.wait_for(
            child.communicate(json.dumps({"url": url, "query": query[:300], "hosts": hosts}).encode()), 45
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
