"""Verify the locally installed app-server without credentials or model calls."""

import argparse
import asyncio
import json
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]


async def smoke(binary):
    with tempfile.TemporaryDirectory(prefix="adex-codex-smoke-") as directory:
        env = {"PATH": os.defpath, "HOME": directory, "CODEX_HOME": directory}
        process = await asyncio.create_subprocess_exec(
            str(binary),
            "--listen",
            "stdio://",
            cwd=directory,
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            request = {
                "id": 1,
                "method": "initialize",
                "params": {
                    "clientInfo": {
                        "name": "adex-runtime-smoke",
                        "title": "Adex",
                        "version": "0.1.0",
                    }
                },
            }
            process.stdin.write((json.dumps(request) + "\n").encode())
            await process.stdin.drain()
            async with asyncio.timeout(30):
                while True:
                    line = await process.stdout.readline()
                    if not line:
                        raise RuntimeError(
                            "app-server exited before initialize response"
                        )
                    response = json.loads(line)
                    if response.get("id") != 1:
                        continue
                    if "error" in response or not isinstance(
                        response.get("result"), dict
                    ):
                        raise RuntimeError("app-server rejected initialize")
                    break
            process.stdin.write(b'{"method":"initialized"}\n')
            await process.stdin.drain()
            print(
                "PASS: app-server initialize/initialized over stdio (isolated, no model call)"
            )
        finally:
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), 5)
                except TimeoutError:
                    process.kill()
                    await process.wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--binary", type=Path, default=ROOT / ".local-data/codex/bin/codex-app-server"
    )
    args = parser.parse_args()
    asyncio.run(smoke(args.binary.resolve()))
