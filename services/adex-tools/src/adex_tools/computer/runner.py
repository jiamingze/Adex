"""Restricted native process boundary. Child receives no service/model credentials."""

import asyncio
import json
import os
import sys
from pathlib import Path
from fastapi import HTTPException


class MacRunner:
    async def call(self, body):
        if os.getenv("ADEX_COMPUTER_TEST_FIXTURE") == "true" and "adex_test_" in os.getenv("ADEX_DB_URL", ""):
            from .fixture import execute

            return execute(body)
        if sys.platform != "darwin":
            raise HTTPException(503, "COMPUTER_BLOCKED_EXTERNAL_MAC_REQUIRED")
        binary = Path(os.getenv("ADEX_COMPUTER_RUNNER", ""))
        if not binary.is_absolute() or not binary.is_file():
            raise HTTPException(503, "COMPUTER_BLOCKED_EXTERNAL_RUNNER_REQUIRED")
        process = await asyncio.create_subprocess_exec(
            str(binary),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env={k: v for k, v in os.environ.items() if k in {"PATH", "HOME", "TMPDIR", "LANG"}},
            start_new_session=True,
        )
        try:
            output, _ = await asyncio.wait_for(process.communicate(json.dumps(body).encode()), 20)
            if process.returncode or len(output) > 250000:
                raise HTTPException(503, "COMPUTER_RUNNER_UNAVAILABLE")
            data = json.loads(output)
            if data.get("error"):
                raise HTTPException(409, data["error"])
            return data
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
