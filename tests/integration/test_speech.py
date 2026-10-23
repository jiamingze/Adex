# ruff: noqa: F401, F811
"""Real isolated PG/auth/WS. Missing provider is not a successful ASR test."""

import asyncio
import json
import os
from uuid import uuid4
import pytest
import httpx
from websockets.asyncio.client import connect
from test_reliability import client, db, sign


def exchange(session, token):
    async def run():
        async with connect(
            "ws://127.0.0.1:18107/speech-ws/" + session, proxy=None
        ) as ws:
            await ws.send(json.dumps({"token": token}))
            return json.loads(await asyncio.wait_for(ws.recv(), 10))

    return asyncio.run(run())


@pytest.mark.skipif(
    os.getenv("ADEX_TEST_REAL_ASR") == "1", reason="No-key fault test, not live ASR"
)
def test_asr_capability_auth_resource_and_replay(client, db):
    with httpx.Client(base_url="http://127.0.0.1:18080") as anonymous:
        assert anonymous.post("/api/v1/speech/session").status_code == 401
    response = client.post("/api/v1/speech/session")
    assert response.status_code == 200
    session = response.json()
    assert set(session) == {"session_id", "token"}
    # A ticket cannot be moved to another session path, nor can an invalid token
    # claim a row. No provider connection happens before these checks.
    assert exchange(str(uuid4()), session["token"])["code"] == "SCOPE_DENIED"
    assert exchange(session["session_id"], "invalid")["code"] == "UNAUTHENTICATED"
    result = exchange(session["session_id"], session["token"])
    assert result["type"] == "error"  # isolated stack has no Alibaba key
    assert exchange(session["session_id"], session["token"])["type"] == "error"
    with db.cursor() as cur:
        cur.execute(
            "SELECT count(*),bool_and(active_until<=now()) FROM tools.speech_sessions WHERE id=%s",
            (session["session_id"],),
        )
        row = cur.fetchone()
        assert row["count"] == 1 and row["bool_and"] is True


def test_asr_owner_connection_limit_is_authoritative(client, db):
    session = client.post("/api/v1/speech/session").json()
    import base64

    claims = json.loads(
        base64.urlsafe_b64decode(session["token"].split(".")[0] + "===")
    )
    fixture_id = str(uuid4())
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO tools.speech_sessions VALUES (%s,%s,now()+interval '4 minutes',now()+interval '70 seconds')",
            (fixture_id, claims["owner"]),
        )
    assert exchange(session["session_id"], session["token"])["type"] == "error"
    with db.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM tools.speech_sessions WHERE id=%s",
            (session["session_id"],),
        )
        assert cur.fetchone()["count"] == 0
        cur.execute("DELETE FROM tools.speech_sessions WHERE id=%s", (fixture_id,))


@pytest.mark.skipif(
    os.getenv("ADEX_TEST_REAL_ASR") != "1", reason="Explicit real Alibaba ASR opt-in"
)
def test_real_alibaba_speech_through_authenticated_app_and_tools(client):
    import subprocess, tempfile, wave

    session = client.post("/api/v1/speech/session").json()
    with tempfile.TemporaryDirectory() as folder:
        path = folder + "/speech.wav"
        subprocess.run(
            [
                "say",
                "-v",
                "Tingting",
                "-o",
                path,
                "--file-format=WAVE",
                "--data-format=LEI16@16000",
                "请帮我创建一个待办事项，明天下午三点开会。",
            ],
            check=True,
        )

        async def run():
            async with connect(
                "ws://127.0.0.1:18107/speech-ws/" + session["session_id"], proxy=None
            ) as ws:
                await ws.send(json.dumps({"token": session["token"]}))
                assert (
                    json.loads(await asyncio.wait_for(ws.recv(), 12))["type"] == "ready"
                )

                async def send():
                    with wave.open(path, "rb") as wav:
                        while audio := wav.readframes(1600):
                            await ws.send(audio)
                            await asyncio.sleep(0.1)
                    await ws.send('{"type":"finish"}')

                sender = asyncio.create_task(send())
                partials = []
                while True:
                    data = json.loads(await asyncio.wait_for(ws.recv(), 15))
                    assert data["type"] != "error", data
                    if data["type"] == "partial":
                        partials.append(data["text"])
                    if data["type"] == "final":
                        await sender
                        assert (
                            "明天" in data["text"]
                            and "三点" in data["text"]
                            and "开会" in data["text"]
                        )
                        assert partials
                        return

        asyncio.run(run())
