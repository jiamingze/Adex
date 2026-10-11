"""Provider-agnostic contract; deterministic fixtures are explicitly mock only."""

import asyncio
import io
import math
import struct
import tempfile
import wave
import zlib
from pathlib import Path
from typing import Protocol

KINDS = ("IMAGE", "AUDIO", "VIDEO")


class MediaSubmissionProvider(Protocol):
    """Execution port shared by providers; optional catalog/cancel capabilities are separate."""

    async def submit(
        self, *, kind: str, prompt: str, input_refs: list[str], params: dict, request_key: str
    ) -> dict: ...

    async def get_result(self, *, provider_job_id: str) -> tuple[bytes, str, str]: ...

    async def reconcile(self, *, request_key: str, provider_job_id: str | None) -> dict: ...


class MediaGenerationProvider(MediaSubmissionProvider, Protocol):
    """Full capability port; submission-only adapters need not claim unsupported cancellation."""

    async def capabilities(self) -> dict: ...

    async def get_status(self, *, provider_job_id: str) -> dict: ...

    async def cancel(self, *, provider_job_id: str) -> dict: ...


def image_fixture() -> bytes:
    def chunk(kind, value):
        return struct.pack(">I", len(value)) + kind + value + struct.pack(">I", zlib.crc32(kind + value))

    rows = b"".join(b"\0" + bytes((60, 130 + y // 4, 115)) * 256 for y in range(256))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 256, 256, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def audio_fixture() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as out:
        out.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        out.writeframes(
            b"".join(
                struct.pack("<h", int(3000 * math.sin(2 * math.pi * (440 if i < 16000 else 554) * i / 16000)))
                for i in range(48000)
            )
        )
    return output.getvalue()


async def video_fixture() -> bytes:
    with tempfile.TemporaryDirectory(prefix="adex-fixture-") as directory:
        path = Path(directory) / "fixture.mp4"
        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=0x398673:s=320x240:d=2",
            "-an",
            "-c:v",
            "libx264",
            "-threads",
            "1",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            await asyncio.wait_for(process.wait(), 10)
        except BaseException:
            process.kill()
            await process.wait()
            raise
        if process.returncode:
            raise RuntimeError("MOCK_VIDEO_RENDER_FAILED")
        return path.read_bytes()


async def fixture(kind):
    if kind == "IMAGE":
        return image_fixture(), "fixture.png", "image/png"
    if kind == "AUDIO":
        return audio_fixture(), "fixture.wav", "audio/wav"
    if kind == "VIDEO":
        return await video_fixture(), "fixture.mp4", "video/mp4"
    raise ValueError("UNSUPPORTED_CAPABILITY")


class MockMediaGenerationProvider:
    async def capabilities(self):
        return {
            "provider": "mock",
            "model_id": "mock-fixture-v1",
            "kinds": list(KINDS),
            "operations": [
                "image_text_to_image",
                "image_edit",
                "image_variation",
                "original_audio_generate",
                "text_to_video",
                "image_to_video",
            ],
            "fixture_parameters_applied": False,
            "mock": True,
            "real_generation": "BLOCKED_EXTERNAL",
            "max_input_bytes": 25 * 1024 * 1024,
            "native_async": False,
            "cancellable": True,
            "queryable": True,
            "idempotent": True,
            "charging_unit": "none",
        }

    async def submit(self, *, kind, prompt, input_refs, params, request_key):
        if kind not in KINDS:
            raise ValueError("UNSUPPORTED_CAPABILITY")
        return {
            "provider_job_id": "mock:" + kind + ":" + request_key,
            "status": "SUCCEEDED",
            "model_id": "mock-fixture-v1",
        }

    async def get_status(self, *, provider_job_id):
        return {"status": "SUCCEEDED", "provider_job_id": provider_job_id}

    async def get_result(self, *, provider_job_id):
        _, kind, _ = provider_job_id.split(":", 2)
        return await fixture(kind)

    async def cancel(self, *, provider_job_id):
        return {"status": "CANCELED", "provider_job_id": provider_job_id, "charged": False}

    async def reconcile(self, *, request_key, provider_job_id=None):
        return (
            await self.get_status(provider_job_id=provider_job_id)
            if provider_job_id
            else {"status": "NOT_SUBMITTED"}
        )


async def video_poster(data):
    with tempfile.TemporaryDirectory(prefix="adex-poster-") as directory:
        source = Path(directory) / "input.mp4"
        target = Path(directory) / "poster.png"
        source.write_bytes(data)
        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(source),
            "-frames:v",
            "1",
            "-vf",
            "scale=320:-1",
            "-threads",
            "1",
            str(target),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            await asyncio.wait_for(process.wait(), 8)
        except BaseException:
            if process.returncode is None:
                process.kill()
                await process.wait()
            raise
        if process.returncode or not target.exists() or target.stat().st_size > 1_000_000:
            raise RuntimeError("VIDEO_POSTER_FAILED")
        return target.read_bytes()
