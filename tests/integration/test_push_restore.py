# ruff: noqa: F401, F811 -- imported pytest fixtures
"""Real isolated PG/API delivery; APNs is an explicit external fixture."""

from uuid import uuid4
from test_reliability import client, db, wait


def test_fresh_native_registration_restores_revoked_device_without_old_backlog(
    client, db
):
    owner = client.get("/api/v1/me").json()["id"]
    conv = client.post(
        "/api/v1/conversations", json={"title": "TEST_FIXTURE push restore"}
    ).json()["id"]
    preferences = client.get("/api/v1/notification-preferences").json()
    client.put(
        "/api/v1/notification-preferences",
        json={
            **preferences,
            "enabled": True,
            "push_enabled": True,
            "quiet_start": None,
            "quiet_end": None,
        },
    ).raise_for_status()
    token = uuid4().hex * 2

    def register():
        return client.post(
            "/api/v1/push/devices", json={"token": token, "environment": "sandbox"}
        )

    first = register()
    first.raise_for_status()
    did = first.json()["id"]
    try:
        client.delete("/api/v1/push/devices/" + did).raise_for_status()
        assert not db.execute(
            "SELECT active FROM app.push_devices WHERE id=%s", (did,)
        ).fetchone()["active"]
        old_id = str(uuid4())
        db.execute(
            "INSERT INTO app.notifications(id,event_id,owner_id,conversation_id,title,body) VALUES(%s,%s,%s,%s,'TEST_FIXTURE missed','fixture')",
            (old_id, str(uuid4()), owner, conv),
        )
        restored = register()
        restored.raise_for_status()
        assert restored.json()["id"] == did
        assert db.execute(
            "SELECT active FROM app.push_devices WHERE id=%s", (did,)
        ).fetchone()["active"]
        sent = client.post(
            "/api/v1/push/test",
            json={"event_id": str(uuid4()), "conversation_id": conv},
        )
        sent.raise_for_status()
        nid = sent.json()["notification_id"]
        result = wait(
            lambda: db.execute(
                "SELECT status FROM app.push_deliveries WHERE notification_id=%s AND device_id=%s AND status='ACCEPTED'",
                (nid, did),
            ).fetchone()
        )
        assert result["status"] == "ACCEPTED"
        assert not db.execute(
            "SELECT 1 FROM app.push_deliveries WHERE notification_id=%s AND device_id=%s",
            (old_id, did),
        ).fetchone()
    finally:
        client.delete("/api/v1/push/devices/" + did).raise_for_status()
        client.put(
            "/api/v1/notification-preferences", json=preferences
        ).raise_for_status()
