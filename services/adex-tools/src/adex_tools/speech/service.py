"""Bounded duplex relay. PG prevents capability replay across Tools replicas."""

import asyncio
import json
import logging
import time
import re
from uuid import UUID
from fastapi import HTTPException, WebSocketDisconnect
from adex_tools.speech.provider import Transcript, audio_event, connection, event


async def claim(core, owner, session):
    async with core.pool.connection() as conn, conn.transaction():
        # Owner lock protects the active connection limit across replicas. Never
        # hold this transaction while connecting to or waiting on the provider.
        await conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("speech:" + owner,))
        await conn.execute("DELETE FROM speech_sessions WHERE expires_at < now()")
        cur = await conn.execute(
            "SELECT 1 FROM speech_sessions WHERE owner_id=%s AND active_until>now()", (owner,)
        )
        if await cur.fetchone():
            raise ValueError("SPEECH_BUSY")
        cur = await conn.execute(
            "INSERT INTO speech_sessions VALUES (%s,%s,now()+interval '4 minutes',now()+interval '70 seconds') "
            "ON CONFLICT DO NOTHING RETURNING id",
            (session, owner),
        )
        if not await cur.fetchone():
            raise ValueError("SPEECH_SESSION_USED")


def error_code(error):
    if isinstance(error, BaseExceptionGroup):
        return error_code(error.exceptions[0])
    if isinstance(error, HTTPException):
        return error.detail
    if isinstance(error, ValueError) and str(error) in {
        "SPEECH_BUSY",
        "SPEECH_SESSION_USED",
        "SPEECH_INVALID_AUTH",
        "SPEECH_INVALID_AUDIO",
        "SPEECH_AUDIO_LIMIT",
        "SPEECH_INVALID_EVENT",
        "SPEECH_PROVIDER_REJECTED",
        "SPEECH_INCOMPLETE",
        "BLOCKED_EXTERNAL",
        "SPEECH_CONFIGURATION_ERROR",
    }:
        return str(error)
    return "SPEECH_UNAVAILABLE"


async def relay(socket, core, session):
    started = time.monotonic()
    claimed = False
    metrics = {"frames": 0, "bytes": 0, "final_chars": 0, "outcome": "disconnected"}
    try:
        async with asyncio.timeout(5):
            raw = await socket.receive_text()
            if len(raw) > 2048:
                raise ValueError("SPEECH_INVALID_AUTH")
            first = json.loads(raw)
        # Reuse service signature validation; the scoped capability is sent only
        # in the first encrypted frame, never in access logs/query parameters.
        from starlette.requests import Request

        request = Request(
            {"type": "http", "headers": [(b"authorization", ("Bearer " + first["token"]).encode())]}
        )
        claims = core.require(request, "app", "speech:stream", session)
        owner = str(UUID(claims["owner"]))
        await claim(core, owner, session)
        claimed = True
        async with asyncio.timeout(65), connection() as upstream:
            transcript = Transcript()
            finishing = asyncio.Event()

            async def send_audio():
                total = 0
                async with asyncio.timeout(45):
                    while True:
                        message = await socket.receive()
                        if message["type"] == "websocket.disconnect":
                            raise WebSocketDisconnect()
                        if message.get("bytes") is not None:
                            audio = message["bytes"]
                            total += len(audio)
                            metrics["frames"] += 1
                            metrics.setdefault("first_audio_s", round(time.monotonic() - started, 3))
                            metrics["bytes"] = total
                            if total > 1440000:
                                raise ValueError("SPEECH_AUDIO_LIMIT")
                            await upstream.send(json.dumps(audio_event(audio)))
                        elif json.loads(message.get("text", "{}")) == {"type": "finish"}:
                            metrics["finish_s"] = round(time.monotonic() - started, 3)
                            finishing.set()
                            await upstream.send(json.dumps(event("session.finish")))
                            return
                        else:
                            raise ValueError("SPEECH_INVALID_EVENT")

            async def receive_text():
                async for raw in upstream:
                    data = json.loads(raw)
                    kind = data.get("type", "")
                    if kind == "session.updated":
                        await socket.send_json({"type": "ready"})
                    elif kind == "error" or kind.endswith("transcription.failed"):
                        provider_code = str(data.get("error", {}).get("code", "unknown"))
                        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", provider_code):
                            provider_code = "unknown"
                        logging.getLogger(__name__).warning("ASR provider rejection: %s", provider_code)
                        raise ValueError("SPEECH_PROVIDER_REJECTED")
                    elif kind.endswith(("transcription.text", "transcription.completed")):
                        preview = transcript.update(data)
                        if preview:
                            metrics.setdefault("first_partial_s", round(time.monotonic() - started, 3))
                        metrics["partials"] = metrics.get("partials", 0) + 1
                        await socket.send_json({"type": "partial", "text": preview})
                    elif kind == "session.finished":
                        if not finishing.is_set():
                            raise ValueError("SPEECH_INCOMPLETE")
                        final = transcript.final()
                        metrics["final_chars"] = len(final)
                        metrics["outcome"] = "completed"
                        await socket.send_json({"type": "final", "text": final})
                        return
                raise ValueError("SPEECH_INCOMPLETE")

            # A disconnect or either pump failing cancels its peer immediately.
            async with asyncio.TaskGroup() as group:
                reader = group.create_task(receive_text())
                writer = group.create_task(send_audio())
                await writer
                async with asyncio.timeout(15):
                    await reader
    except WebSocketDisconnect:
        pass
    except (Exception, ExceptionGroup) as error:
        code = error_code(error)
        metrics["outcome"] = code
        logging.getLogger(__name__).warning(
            "ASR failure %s: code=%s category=%s claimed=%s", session, code, type(error).__name__, claimed
        )
        try:
            await socket.send_json({"type": "error", "code": code})
        except Exception:
            pass
    finally:
        if claimed:
            logging.getLogger("uvicorn.error").info("ASR stream %s: %s", session, metrics)
        try:
            if claimed:
                await core.query("UPDATE speech_sessions SET active_until=now() WHERE id=%s", (session,))
        finally:
            # Even if PG is lost during cleanup, release the socket/audio. The
            # bounded active_until lease expires without a second recovery loop.
            try:
                await socket.close()
            except Exception:
                pass
