"""Synchronous original music adapter. No retry or invented remote reconciliation."""

import os
import httpx
from fastapi import HTTPException


class MiniMaxMusicProvider:
    def __init__(self):
        self.key = os.getenv("ADEX_MUSIC_API_KEY", "")
        self.base = os.getenv("ADEX_MUSIC_BASE_URL", "https://api.minimaxi.com/v1").rstrip("/")
        self.model = os.getenv("ADEX_MUSIC_MODEL", "music-3.0")
        self.audio = None
        self.metadata = {}
        if not self.key or not self.base.startswith("https://"):
            raise HTTPException(503, "MUSIC_NOT_CONFIGURED")

    async def submit(self, *, kind, prompt, input_refs, params, request_key):
        if kind != "AUDIO" or input_refs:
            raise HTTPException(400, "UNSUPPORTED_CAPABILITY")
        duration = params.get("duration_seconds", 180)
        payload = {
            "model": self.model,
            "prompt": (prompt + f"。目标时长约 {duration} 秒。")[:2000],
            "is_instrumental": params.get("mode", "instrumental") != "vocals",
            "lyrics_optimizer": params.get("mode") == "vocals",
            "stream": False,
            "output_format": "hex",
            "audio_setting": {"sample_rate": 44100, "bitrate": 256000, "format": "mp3"},
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=10), trust_env=False) as client:
            async with client.stream(
                "POST",
                self.base + "/music_generation",
                json=payload,
                headers={"Authorization": "Bearer " + self.key},
            ) as response:
                if response.status_code in (401, 403):
                    raise HTTPException(503, "MUSIC_PROVIDER_DENIED")
                if response.status_code >= 400:
                    raise HTTPException(503, "MUSIC_PROVIDER_HTTP_" + str(response.status_code))
                raw = bytearray()
                async for part in response.aiter_bytes():
                    raw.extend(part)
                    if len(raw) > 52 * 1024 * 1024:
                        raise HTTPException(502, "MUSIC_OUTPUT_TOO_LARGE")
        import json

        value = json.loads(raw)
        if value.get("base_resp", {}).get("status_code", 0) != 0:
            # Never expose vendor messages: they may include request/account details.
            raise HTTPException(503, "MUSIC_PROVIDER_DENIED")
        encoded = value.get("data", {}).get("audio", "")
        if not isinstance(encoded, str) or not encoded:
            raise HTTPException(502, "MUSIC_RESULT_MISSING")
        try:
            self.audio = bytes.fromhex(encoded)
        except ValueError:
            raise HTTPException(502, "MUSIC_RESULT_INVALID") from None
        if not (
            self.audio.startswith(b"ID3")
            or (len(self.audio) > 2 and self.audio[0] == 255 and self.audio[1] & 224 == 224)
        ):
            raise HTTPException(502, "MUSIC_RESULT_INVALID")
        self.metadata = value.get("extra_info", {})
        return {"provider_job_id": str(value.get("trace_id") or request_key), "status": "SUCCEEDED"}

    async def get_result(self, *, provider_job_id):
        if self.audio is None:
            raise HTTPException(409, "PROVIDER_UNKNOWN")
        return self.audio, "original-music.mp3", "audio/mpeg"

    async def reconcile(self, *, request_key, provider_job_id):
        # This synchronous API documents no retrieval by request_key/trace_id.
        return {"status": "UNKNOWN", "provider_job_id": provider_job_id}
