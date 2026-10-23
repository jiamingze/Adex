"""Alibaba ASR protocol; credentials and provider messages never reach clients."""

import base64
import json
import os
from uuid import uuid4
from contextlib import asynccontextmanager
from websockets.asyncio.client import connect


class Transcript:
    def __init__(self):
        self.items = {}
        self.completed = set()

    def update(self, event):
        kind = event.get("type", "")
        if kind.endswith("input_audio_transcription.text"):
            key = event["item_id"]
            if key not in self.completed:
                self.items[key] = event.get("text", "") + event.get("stash", "")
        elif kind.endswith("input_audio_transcription.completed"):
            key = event["item_id"]
            self.items[key] = event.get("transcript", "")
            self.completed.add(key)
        return "".join(self.items.values())

    def final(self):
        if self.items.keys() - self.completed:
            raise ValueError("SPEECH_INCOMPLETE")
        return "".join(self.items.values())


def event(kind, **fields):
    return {"event_id": uuid4().hex, "type": kind, **fields}


def audio_event(audio):
    if not audio or len(audio) > 32768 or len(audio) % 2:
        raise ValueError("SPEECH_INVALID_AUDIO")
    return event("input_audio_buffer.append", audio=base64.b64encode(audio).decode())


@asynccontextmanager
async def connection():
    key = os.getenv("DASHSCOPE_API_KEY", "")
    if not key:
        raise ValueError("BLOCKED_EXTERNAL")
    url = os.getenv("ADEX_ASR_WS_URL", "wss://dashscope.aliyuncs.com/api-ws/v1/realtime")
    model = os.getenv("ADEX_ASR_MODEL", "qwen3-asr-flash-realtime")
    if not url.startswith("wss://") or "?" in url:
        raise ValueError("SPEECH_CONFIGURATION_ERROR")
    async with connect(
        url + "?model=" + model,
        additional_headers={"Authorization": "Bearer " + key},
        open_timeout=8,
        close_timeout=2,
        max_size=262144,
        max_queue=8,
    ) as upstream:
        await upstream.send(
            json.dumps(
                event(
                    "session.update",
                    session={
                        "input_audio_format": "pcm",
                        "sample_rate": 16000,
                        "input_audio_transcription": {"language": "zh"},
                        "turn_detection": {
                            "type": "server_vad",
                            "threshold": 0.0,
                            "silence_duration_ms": 400,
                        },
                    },
                )
            )
        )
        yield upstream
