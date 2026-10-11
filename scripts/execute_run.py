"""Run one already-claimed background attempt; intended for worker recovery diagnostics/tests."""

import asyncio
import json
import sys
from adex_kernel.core import Core
from adex_agent.runtime import Runtime


async def main():
    core = Core("agent")
    await core.start()
    runtime = Runtime(core)
    try:
        await runtime.background_run(json.loads(sys.argv[1]))
    finally:
        await runtime.redis.aclose()
        await core.pool.close()


asyncio.run(main())
