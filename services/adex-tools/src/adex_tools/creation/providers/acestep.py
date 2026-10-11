"""Local ACE-Step runner; recorded job IDs can be queried without resubmission."""

import asyncio
import json
import os
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException


class AceStepMusicProvider:
    def __init__(self):
        self.base = os.getenv("ADEX_ACESTEP_URL", "http://127.0.0.1:8001").rstrip("/")
        url = urlsplit(self.base)
        if (
            url.scheme != "http"
            or url.hostname not in ("127.0.0.1", "localhost")
            or url.username
            or url.password
            or url.path
        ):
            raise HTTPException(503, "MUSIC_RUNNER_CONFIGURATION_INVALID")
        self.model = "acestep-v15-turbo"
        self.metadata = {}
        self.result = None

    async def request(self, path, payload):
        async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
            response = await client.post(self.base + path, json=payload)
            if response.is_error:
                raise HTTPException(503, "MUSIC_RUNNER_UNAVAILABLE")
            value = response.json()
            if value.get("code") != 200:
                raise HTTPException(502, "MUSIC_RUNNER_REJECTED")
            return value["data"]

    async def submit(self, *, kind, prompt, input_refs, params, request_key):
        if kind != "AUDIO" or input_refs or params.get("mode", "instrumental") != "instrumental":
            raise HTTPException(400, "UNSUPPORTED_CAPABILITY")
        value = await self.request(
            "/release_task",
            {
                "model": self.model,
                "prompt": prompt,
                "lyrics": "[Instrumental]",
                "audio_duration": params.get("duration_seconds", 180),
                "audio_format": "mp3",
                "batch_size": 1,
                "thinking": False,
                "use_cot_caption": False,
                "use_cot_language": False,
                "inference_steps": 8,
            },
        )
        return {"provider_job_id": value["task_id"], "status": "QUEUED"}

    async def reconcile(self, *, request_key, provider_job_id):
        values = await self.request("/query_result", {"task_id_list": [provider_job_id]})
        value = next((row for row in values if row["task_id"] == provider_job_id), None)
        if value and value["status"] == 1:
            results = json.loads(value["result"]) if isinstance(value["result"], str) else value["result"]
            self.result = results[0]
            self.metadata["music_duration"] = round(self.result.get("metas", {}).get("duration", 0) * 1000)
            return {"status": "SUCCEEDED", "provider_job_id": provider_job_id}
        if value and value["status"] == 2:
            raise HTTPException(502, "MUSIC_GENERATION_FAILED")
        return {"status": "UNKNOWN", "provider_job_id": provider_job_id}

    async def get_result(self, *, provider_job_id):
        deadline = asyncio.get_running_loop().time() + 900
        while self.result is None:
            await self.reconcile(request_key="", provider_job_id=provider_job_id)
            if self.result is not None:
                break
            if asyncio.get_running_loop().time() >= deadline:
                raise HTTPException(409, "PROVIDER_UNKNOWN")
            await asyncio.sleep(3)
        path = self.result["file"]
        parsed = urlsplit(path)
        if parsed.scheme or parsed.netloc or parsed.path != "/v1/audio":
            raise HTTPException(502, "MUSIC_RESULT_INVALID")
        async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
            async with client.stream("GET", self.base + path) as response:
                response.raise_for_status()
                audio = bytearray()
                async for chunk in response.aiter_bytes():
                    audio.extend(chunk)
                    if len(audio) > 26 * 1024 * 1024:
                        raise HTTPException(502, "MUSIC_OUTPUT_TOO_LARGE")
        if not (audio.startswith(b"ID3") or (len(audio) > 2 and audio[0] == 255 and audio[1] & 224 == 224)):
            raise HTTPException(502, "MUSIC_RESULT_INVALID")
        return bytes(audio), "original-music.mp3", "audio/mpeg"
