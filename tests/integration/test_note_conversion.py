"""Real App/Agent/PG composition chain; model is explicitly TEST_FIXTURE only."""

from uuid import uuid4
from test_reliability import client, db, wait


def test_explicit_reply_to_note_idempotency_ownership_and_deletion(client, db):
    conv = client.post(
        "/api/v1/conversations", json={"title": "note conversion fixture"}
    ).json()["id"]
    client.post(
        f"/api/v1/conversations/{conv}/messages",
        json={
            "content": "Explain fixture API design",
            "client_message_id": str(uuid4()),
        },
    ).raise_for_status()

    def replies():
        return [
            m
            for m in client.get(f"/api/v1/conversations/{conv}/messages").json()[
                "items"
            ]
            if m["role"] == "assistant"
        ]

    wait(lambda: bool(replies()))
    message = replies()[-1]
    body = {"conversation_id": conv, "message_id": message["id"]}
    result = client.post("/api/v1/notes/from-message", json=body)
    result.raise_for_status()
    note = result.json()
    assert note["title"].startswith("TEST_FIXTURE")
    assert message["content"] in note["content"]
    assert (
        client.post("/api/v1/notes/from-message", json=body).json()["id"] == note["id"]
    )
    user_message = next(
        m
        for m in client.get(f"/api/v1/conversations/{conv}/messages").json()["items"]
        if m["role"] == "user"
    )
    assert (
        client.post(
            "/api/v1/notes/from-message",
            json={**body, "message_id": user_message["id"]},
        ).status_code
        == 404
    )
    foreign = client.post(
        "/api/v1/notes/from-message", json={**body, "conversation_id": str(uuid4())}
    )
    assert foreign.status_code == 404
    client.delete(f"/api/v1/conversations/{conv}").raise_for_status()
    assert (
        client.get(f"/api/v1/notes/{note['id']}").json()["content"] == note["content"]
    )
    assert client.post("/api/v1/notes/from-message", json=body).status_code == 404
    client.delete(
        f"/api/v1/notes/{note['id']}", params={"revision": note["revision"]}
    ).raise_for_status()
    assert client.get(f"/api/v1/notes/{note['id']}").status_code == 404


def test_failed_note_composition_does_not_create_a_note(client, db):
    conv = client.post(
        "/api/v1/conversations", json={"title": "invalid note fixture"}
    ).json()["id"]
    message = uuid4()
    db.execute(
        "INSERT INTO app.messages(id,conversation_id,seq,role,content) VALUES(%s,%s,1,'assistant','fixture:note-invalid')",
        (message, conv),
    )
    result = client.post(
        "/api/v1/notes/from-message",
        json={"conversation_id": conv, "message_id": str(message)},
    )
    assert result.status_code >= 500
    assert (
        db.execute(
            "SELECT count(*) AS n FROM app.notes WHERE source_message_id=%s", (message,)
        ).fetchone()["n"]
        == 0
    )
