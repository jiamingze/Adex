import pytest
from adex_tools.speech.provider import Transcript, audio_event


def test_partial_revisions_and_final_segments_do_not_duplicate():
    state = Transcript()
    prefix = "conversation.item.input_audio_transcription."
    assert state.update({"type": prefix + "text", "item_id": "a", "text": "今天", "stash": "天"}) == "今天天"
    assert (
        state.update({"type": prefix + "text", "item_id": "a", "text": "今天", "stash": "天气"}) == "今天天气"
    )
    state.update({"type": prefix + "completed", "item_id": "a", "transcript": "今天天气。"})
    assert (
        state.update({"type": prefix + "text", "item_id": "b", "text": "很好", "stash": ""})
        == "今天天气。很好"
    )
    state.update({"type": prefix + "completed", "item_id": "b", "transcript": "很好。"})
    assert state.final() == "今天天气。很好。"


def test_unfinalized_transcript_cannot_be_reported_as_success():
    state = Transcript()
    state.update({"type": "conversation.item.input_audio_transcription.text", "item_id": "a", "text": "草稿"})
    with pytest.raises(ValueError):
        state.final()


def test_audio_validation_is_bounded_even_length_pcm():
    assert audio_event(b"\0\0")["audio"] == "AAA="
    for audio in (b"", b"\0", b"\0" * 32770):
        with pytest.raises(ValueError):
            audio_event(audio)


async def test_relay_waits_for_provider_final_and_closes(monkeypatch):
    import asyncio
    import json
    from contextlib import asynccontextmanager
    from uuid import uuid4
    from adex_tools.speech import service

    class Core:
        def require(self, *args):
            return {"owner": str(uuid4())}

        async def query(self, *args):
            pass

    async def claim(*args):
        pass

    monkeypatch.setattr(service, "claim", claim)

    class Socket:
        sent = []
        closed = False

        async def receive_text(self):
            return '{"token":"fixture"}'

        async def receive(self):
            return {"type": "websocket.receive", "text": '{"type":"finish"}'}

        async def send_json(self, data):
            self.sent.append(data)

        async def close(self):
            self.closed = True

    class Upstream:
        def __init__(self):
            self.queue = asyncio.Queue()

        async def send(self, raw):
            assert json.loads(raw)["type"] == "session.finish"
            for data in [
                {
                    "type": "conversation.item.input_audio_transcription.completed",
                    "item_id": "1",
                    "transcript": "真实协议测试",
                },
                {"type": "session.finished"},
            ]:
                await self.queue.put(json.dumps(data))

        def __aiter__(self):
            return self

        async def __anext__(self):
            return await self.queue.get()

    @asynccontextmanager
    async def connection():
        yield Upstream()

    monkeypatch.setattr(service, "connection", connection)
    socket = Socket()
    await service.relay(socket, Core(), uuid4())
    assert socket.closed
    assert socket.sent[-1] == {"type": "final", "text": "真实协议测试"}


async def test_unauthenticated_never_connects_provider(monkeypatch):
    from fastapi import HTTPException
    from adex_tools.speech.service import relay
    from uuid import uuid4

    class Core:
        def require(self, *args):
            raise HTTPException(401, "UNAUTHENTICATED")

    class Socket:
        result = None

        async def receive_text(self):
            return '{"token":"invalid"}'

        async def send_json(self, data):
            self.result = data

        async def close(self):
            pass

    socket = Socket()
    await relay(socket, Core(), uuid4())
    assert socket.result == {"type": "error", "code": "UNAUTHENTICATED"}
