"""Host-authorized document import into App-owned private LocalFileStorage."""

import asyncio
import hashlib
import mimetypes
import os
import stat
from pathlib import Path
import httpx
from fastapi import HTTPException

LIMIT = 25 * 1024 * 1024


def read_document(source):
    roots = [
        Path(p).expanduser().resolve()
        for p in os.getenv("ADEX_COMPUTER_FILE_ROOTS", "").split(os.pathsep)
        if p
    ]
    if not roots:
        raise HTTPException(403, "COMPUTER_FILE_ROOT_NOT_GRANTED")
    requested = Path(source).expanduser()
    if not requested.is_absolute():
        if requested.parts and requested.parts[0] == "Desktop":
            requested = Path.home() / requested
        else:
            requested = roots[0] / requested
    target = requested.resolve()
    root = next((r for r in roots if target.is_relative_to(r)), None)
    if root is None:
        raise HTTPException(403, "COMPUTER_FILE_OUTSIDE_GRANTED_ROOT")
    parts = target.relative_to(root).parts
    if (
        not parts
        or any(p.startswith(".") or p.lower() in {"keychains", "credentials"} for p in parts)
        or target.suffix.lower() in {".pem", ".key", ".p8", ".p12", ".mobileprovision"}
    ):
        raise HTTPException(403, "COMPUTER_FILE_NOT_ALLOWED")
    descriptors = []
    try:
        descriptors.append(os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW))
        for part in parts[:-1]:
            descriptors.append(
                os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptors[-1])
            )
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptors[-1])
        descriptors.append(fd)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise HTTPException(400, "COMPUTER_REGULAR_FILE_REQUIRED")
        if info.st_size > LIMIT:
            raise HTTPException(413, "COMPUTER_FILE_SIZE_LIMIT")
        with os.fdopen(os.dup(fd), "rb") as stream:
            data = stream.read(LIMIT + 1)
        if len(data) > LIMIT:
            raise HTTPException(413, "COMPUTER_FILE_SIZE_LIMIT")
        return target.name, data
    except PermissionError:
        raise HTTPException(403, "COMPUTER_FILE_ACCESS_DENIED") from None
    except OSError:
        raise HTTPException(404, "COMPUTER_FILE_UNAVAILABLE") from None
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


async def export_document(service, owner, body):
    service.grant(owner)
    run = await service.authorize(owner, body)
    if not run.get("computer_file_path") or run["computer_file_path"] != body["file_path"]:
        raise HTTPException(403, "COMPUTER_FILE_NOT_REQUESTED")
    name, data = await asyncio.to_thread(read_document, body["file_path"])
    await service.authorize(owner, body)
    digest = hashlib.sha256(data).hexdigest()
    async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
        result = await client.post(
            os.environ["ADEX_APP_URL"] + "/internal/files",
            headers={
                "Authorization": "Bearer " + service.core.token("app", "file:write", owner),
                "Idempotency-Key": f"computer-file:{body['run_id']}:{body['command_key']}",
            },
            files={"file": (name, data, mimetypes.guess_type(name)[0] or "application/octet-stream")},
        )
        if result.is_error:
            raise HTTPException(result.status_code, "COMPUTER_FILE_IMPORT_FAILED")
        file_id = result.json()["id"]
    saved = await service.core.call(
        "app", "file:read", "GET", f"/internal/files/{file_id}", owner=owner, resource=file_id
    )
    if (
        saved.get("status") != "READY"
        or saved.get("sha256") != digest
        or saved.get("size_bytes") != len(data)
    ):
        raise HTTPException(502, "COMPUTER_FILE_READBACK_MISMATCH")
    return {key: saved[key] for key in ("id", "name", "size_bytes", "sha256", "mime_type")}
