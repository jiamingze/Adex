"""File/artifact processing independent of HTTP; scopes are verified before invocation."""

from fastapi import HTTPException
import asyncio
import json
import os


async def file_extract(core, claims, body):
    import sys
    import os
    import tempfile
    from pathlib import Path
    import httpx

    with tempfile.TemporaryDirectory(prefix="adex-extract-") as directory:
        path = Path(directory) / "input"
        async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
            async with client.stream(
                "GET",
                os.environ["ADEX_APP_URL"] + f"/internal/files/{body.file_id}/content",
                headers={
                    "Authorization": "Bearer " + core.token("app", "file:read", claims["owner"], body.file_id)
                },
            ) as response:
                if response.is_error:
                    raise HTTPException(404, "FILE_NOT_AVAILABLE")
                size = 0
                with path.open("wb") as output:
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > 25 * 1024 * 1024:
                            raise HTTPException(413, "FILE_SIZE_LIMIT")
                        output.write(chunk)
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "adex_tools.runners.extract_runner",
            str(path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env={"PATH": os.environ.get("PATH", ""), "LANG": "en_US.UTF-8"},
        )
        try:
            output, _ = await asyncio.wait_for(process.communicate(), 7)
        except BaseException:
            process.kill()
            await process.wait()
            raise HTTPException(422, "FILE_PROCESSING_LIMIT") from None
        if process.returncode or len(output) > 200000:
            raise HTTPException(422, "UNSUPPORTED_OR_INVALID_FILE")
        return json.loads(output)


async def check_game(core, claims, body):
    from adex_tools.runners.code_runner import check_game

    return await check_game(body.source)


async def import_artifact(core, claims, body):
    import httpx

    suffix = {"RESEARCH": "md", "TRAVEL": "md", "GAME": "html", "DIAGRAM": "mmd"}.get(body.kind)
    if not suffix:
        raise HTTPException(400, "INVALID_ARTIFACT_KIND")
    if body.kind == "DIAGRAM":
        from adex_tools.creation.diagram import validate_diagram

        validate_diagram(body.source)
    async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
        response = await client.post(
            os.environ["ADEX_APP_URL"] + "/internal/files",
            headers={
                "Authorization": "Bearer " + core.token("app", "file:write", claims["owner"]),
                "Idempotency-Key": "artifact:" + body.request_key,
            },
            files={"file": ("artifact." + suffix, body.source.encode(), "text/plain")},
        )
        if response.is_error:
            raise HTTPException(response.status_code, "ARTIFACT_FILE_IMPORT_FAILED")
        return {
            "file_id": response.json()["id"],
            "source_format": suffix,
            "renderer_version": "mermaid-12.1.0-strict-v1" if suffix == "mmd" else None,
        }
