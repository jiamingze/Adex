"""Long original music from independently durable generated sections, never loops audio."""

import asyncio
import math
import tempfile
from pathlib import Path

import httpx
from fastapi import HTTPException
from adex_kernel.core import digest, required


def section_durations(duration):
    count = math.ceil((duration - 2) / 118)
    return [(duration + 2 * (count - 1)) / count] * count


async def join_sections(sections):
    with tempfile.TemporaryDirectory(prefix="adex-music-") as directory:
        args = ["ffmpeg", "-nostdin", "-v", "error"]
        for index, data in enumerate(sections):
            path = Path(directory) / f"{index}.mp3"
            path.write_bytes(data)
            args.extend(["-i", str(path)])
        filters = []
        last = "0:a"
        for index in range(1, len(sections)):
            target = f"joined{index}"
            filters.append(f"[{last}][{index}:a]acrossfade=d=2:c1=tri:c2=tri[{target}]")
            last = target
        output = Path(directory) / "composition.mp3"
        args.extend(
            [
                "-filter_complex",
                ";".join(filters),
                "-map",
                f"[{last}]",
                "-c:a",
                "libmp3lame",
                "-b:a",
                "192k",
                "-threads",
                "1",
                str(output),
            ]
        )
        process = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
        )
        try:
            await asyncio.wait_for(process.wait(), 60)
        except BaseException:
            if process.returncode is None:
                process.kill()
                await process.wait()
            raise
        if process.returncode or not output.exists():
            raise HTTPException(502, "MUSIC_COMPOSITION_FAILED")
        data = output.read_bytes()
        if len(data) > 26 * 1024 * 1024:
            raise HTTPException(502, "MEDIA_OUTPUT_TOO_LARGE")
        probe = await asyncio.create_subprocess_exec(
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(output),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        duration, _ = await asyncio.wait_for(probe.communicate(), 10)
        if probe.returncode:
            raise HTTPException(502, "MEDIA_RESULT_INVALID")
        return data, float(duration) * 1000


class MusicCompositionProvider:
    model = "qwen-audio-3.1-tts-next"

    def __init__(self, core, owner, body):
        self.core, self.owner, self.body = core, owner, body
        self.metadata = {}
        self.job_id = "composition:" + digest({"owner": str(owner), "key": body["request_key"]})

    async def submit(self, **kwargs):
        # Persist this deterministic coordinator ID before any child submission.
        return {"provider_job_id": self.job_id, "status": "PENDING"}

    async def reconcile(self, *, request_key, provider_job_id):
        if provider_job_id != self.job_id:
            raise HTTPException(409, "PROVIDER_UNKNOWN")
        # Child ledgers are checked in get_result; UNKNOWN child submissions are never repeated.
        return {"provider_job_id": self.job_id, "status": "PENDING"}

    async def get_result(self, *, provider_job_id):
        from adex_tools.creation.service import generate

        sections = []
        durations = section_durations(self.body["params"]["duration_seconds"])
        ids = []
        for index, duration in enumerate(durations):
            child = {
                **self.body,
                "request_key": self.body["request_key"] + f":section:{index}",
                "composition_parent": self.body["request_key"],
                "params": {**self.body["params"], "duration_seconds": duration},
                "prompt": self.body["prompt"]
                + f"。这是统一风格作品的第{index + 1}/{len(durations)}段，保持相同调性、速度和乐器；"
                + ("温柔铺陈。" if index == 0 else "延续旋律，最后自然结束。"),
            }
            result = await generate(self.core, self.owner, child, composition_part=True)
            file_id = result["artifact"]["file_id"]
            async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
                response = await client.get(
                    required("ADEX_APP_URL") + f"/internal/files/{file_id}/content",
                    headers={
                        "Authorization": "Bearer " + self.core.token("app", "file:read", self.owner, file_id)
                    },
                )
                response.raise_for_status()
                sections.append(response.content)
            ids.append(file_id)
        data, duration = await join_sections(sections)
        self.metadata = {
            "music_duration": duration,
            "section_file_ids": ids,
            "composition": "original sections with 2-second crossfades",
        }
        return data, "original-music.mp3", "audio/mpeg"
