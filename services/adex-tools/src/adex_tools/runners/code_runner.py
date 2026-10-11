import asyncio
import os
import tempfile
from pathlib import Path
import json
from uuid import uuid4


async def check_game(source):
    if os.getenv("ADEX_CODE_RUNNER_MODE") == "gateway":
        import hashlib
        import hmac
        import time
        import httpx
        from urllib.parse import urlparse

        endpoint = os.environ["ADEX_CODE_RUNNER_URL"]
        if urlparse(endpoint).scheme not in ("http", "https") or urlparse(endpoint).username:
            raise RuntimeError("INVALID_RUNNER_ENDPOINT")
        raw = json.dumps({"source": source}).encode()
        stamp = str(int(time.time()))
        signature = hmac.new(
            os.environ["ADEX_RUNNER_KEY"].encode(), stamp.encode() + b"." + raw, hashlib.sha256
        ).hexdigest()
        async with httpx.AsyncClient(timeout=25, trust_env=False, follow_redirects=False) as client:
            response = await client.post(
                endpoint.rstrip("/") + "/internal/check",
                content=raw,
                headers={"X-Timestamp": stamp, "X-Signature": signature},
            )
            response.raise_for_status()
            if len(response.content) > 12000:
                raise RuntimeError("RUNNER_RESPONSE_TOO_LARGE")
            return response.json()
    if os.getenv("ADEX_CODE_RUNNER_MODE") != "docker":
        return {"status": "BLOCKED_ENVIRONMENT", "reason": "Docker sandbox runner is not configured"}
    if len(source) > 128000:
        raise ValueError("GAME_SOURCE_TOO_LARGE")
    temp_root = Path(os.getenv("ADEX_CODE_RUNNER_TEMP_ROOT", ".local-data/runner-tmp")).resolve()
    temp_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix="adex-game-", dir=temp_root) as folder:
        path = Path(folder) / "game.html"
        path.write_text(source)
        path.chmod(0o444)
        name = "adex-game-" + uuid4().hex
        process = await asyncio.create_subprocess_exec(
            "docker",
            "run",
            "--rm",
            "--name",
            name,
            "--stop-timeout=1",
            "--network=none",
            "--cpus=0.5",
            "--memory=512m",
            "--pids-limit=64",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--tmpfs=/tmp:rw,size=128m",
            "--mount",
            f"type=bind,source={path},target=/input/game.html,readonly",
            os.getenv("ADEX_CODE_RUNNER_IMAGE", "adex-code-runner:local"),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            output, _ = await asyncio.wait_for(process.communicate(), 16)
        except BaseException:
            if process.returncode is None:
                process.kill()
                await process.wait()
            raise RuntimeError("CODE_RUNNER_TIMEOUT") from None
        finally:
            cleanup = await asyncio.create_subprocess_exec(
                "docker",
                "rm",
                "-f",
                name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            try:
                await asyncio.wait_for(cleanup.wait(), 4)
            except asyncio.TimeoutError:
                cleanup.kill()
                await cleanup.wait()
        if process.returncode or len(output) > 10000:
            raise RuntimeError("CODE_RUNNER_FAILED")
        return json.loads(output)
