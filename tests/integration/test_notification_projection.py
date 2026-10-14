"""Notification results must not bring back deleted conversation content."""

from uuid import uuid4
from test_reliability import client, db


def test_result_notification_hidden_after_conversation_deletion(client, db):
    owner = client.get("/api/v1/me").json()["id"]
    conv = client.post(
        "/api/v1/conversations", json={"title": "result visibility fixture"}
    ).json()["id"]
    identifier = uuid4()
    db.execute(
        "INSERT INTO app.notifications(id,event_id,owner_id,conversation_id,title,body) VALUES(%s,%s,%s,%s,'任务已完成','TEST_FIXTURE private result')",
        (identifier, uuid4(), owner, conv),
    )
    assert str(identifier) in [
        row["id"] for row in client.get("/api/v1/notifications").json()["items"]
    ]
    client.delete(f"/api/v1/conversations/{conv}").raise_for_status()
    assert str(identifier) not in [
        row["id"] for row in client.get("/api/v1/notifications").json()["items"]
    ]
    assert db.execute(
        "SELECT id FROM app.notifications WHERE id=%s", (identifier,)
    ).fetchone()
