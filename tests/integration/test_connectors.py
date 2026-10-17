"""Real Adex HTTP/PG/Run/outbox chain with explicit TEST_FIXTURE external providers."""

import json
import os
import subprocess
from urllib.parse import urlparse, parse_qs
from uuid import uuid4
import httpx
from test_reliability import client, db, claim, sign, wait, worker_env, ROOT

FIXTURE = "http://127.0.0.1:18109"


def seed(**data):
    r = httpx.post(FIXTURE + "/fixture/seed", json=data, trust_env=False)
    r.raise_for_status()


def connect(client, service, access):
    r = client.post(
        "/api/v1/connectors/google/authorize",
        json={"service": service, "access": access},
    )
    r.raise_for_status()
    url = r.json()["authorization_url"]
    consent = httpx.get(url, trust_env=False).json()
    callback = client.get(
        "/api/v1/connectors/google/callback",
        params={"state": consent["state"], "code": consent["code"]},
    )
    callback.raise_for_status()
    assert callback.json()["provider"] == "TEST_FIXTURE"
    # State cannot be replayed, even in the initiating authenticated session.
    replay = client.get(
        "/api/v1/connectors/google/callback",
        params={"state": consent["state"], "code": consent["code"]},
    )
    assert replay.status_code == 403
    return callback.json()["id"]


def execute(client, db, run):
    claimed = claim()
    assert claimed and claimed["id"] == run["id"]
    done = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            "services/adex-agent",
            "python",
            "scripts/execute_run.py",
            json.dumps(claimed),
        ],
        cwd=ROOT,
        env=worker_env(),
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert done.returncode == 0, done.stderr[-1000:]
    row = db.execute(
        "SELECT * FROM automation.runs WHERE id=%s", (run["id"],)
    ).fetchone()
    assert row["status"] == "COMPLETED", row["error_code"]
    wait(
        lambda: db.execute(
            "SELECT delivered_at FROM automation.outbox WHERE run_id=%s", (run["id"],)
        ).fetchone()["delivered_at"]
    )
    return claimed


def conversation(client):
    return client.post(
        "/api/v1/conversations", json={"title": "connector TEST_FIXTURE"}
    ).json()["id"]


def calendar_events():
    return [
        {
            "id": "first",
            "etag": "version-one",
            "summary": "fixture meeting A",
            "start": {"dateTime": "2026-10-13T10:00:00+08:00"},
            "end": {"dateTime": "2026-10-13T11:00:00+08:00"},
        },
        {
            "id": "second",
            "etag": "version-two",
            "summary": "fixture meeting B",
            "start": {"dateTime": "2026-10-13T10:30:00+08:00"},
            "end": {"dateTime": "2026-10-13T11:30:00+08:00"},
        },
    ]


def test_calendar_conflict_approve_modify_verify(client, db):
    seed(events=calendar_events(), fault="", writes=0)
    conn = connect(client, "calendar", "write")
    conv = conversation(client)
    result = client.post(
        f"/api/v1/connectors/{conn}/query",
        json={"start": "2026-10-13T00:00:00Z", "end": "2026-10-14T00:00:00Z"},
    ).json()
    assert result["provider"] == "TEST_FIXTURE" and len(result["conflicts"]) == 1
    draft = client.post(
        "/api/v1/actions",
        json={
            "connection_id": conn,
            "origin_conversation_id": conv,
            "kind": "calendar.update",
            "payload": {
                "event_id": "second",
                "start": "2026-10-13T12:00:00+08:00",
                "end": "2026-10-13T13:00:00+08:00",
            },
        },
    )
    draft.raise_for_status()
    action = draft.json()
    bad = client.post(
        f"/api/v1/actions/{action['id']}/approve", json={"request_hash": "wrong"}
    )
    assert bad.status_code == 409
    run = client.post(
        f"/api/v1/actions/{action['id']}/approve",
        json={"request_hash": action["request_hash"]},
    )
    run.raise_for_status()
    run = run.json()
    execute(client, db, run)
    receipt = db.execute(
        "SELECT state,result FROM tools.approvals WHERE id=%s", (action["id"],)
    ).fetchone()
    assert (
        receipt["state"] == "SUCCEEDED"
        and receipt["result"]["verified"]
        and receipt["result"]["provider"] == "TEST_FIXTURE"
    )
    assert (
        client.post(
            f"/api/v1/connectors/{conn}/query",
            json={"start": "2026-10-13T00:00:00Z", "end": "2026-10-14T00:00:00Z"},
        ).json()["conflicts"]
        == []
    )
    # Lease fencing and receipt dedupe protect against duplicate dispatch.
    assert (
        db.execute(
            "SELECT count(*) AS n FROM tools.effects WHERE effect_key=%s",
            ("action:" + action["id"],),
        ).fetchone()["n"]
        == 1
    )
    listed = client.get("/api/v1/connectors").json()
    assert "credentials" not in json.dumps(listed)
    cipher = db.execute(
        "SELECT credentials FROM tools.connector_connections WHERE id=%s", (conn,)
    ).fetchone()["credentials"]
    assert "test-access" not in cipher and "test-refresh" not in cipher


def test_important_mail_change_proactive_dedupe_preferences(client, db):
    seed(
        messages=[
            {
                "id": "important-one",
                "historyId": "v1",
                "threadId": "thread-one",
                "labelIds": ["INBOX", "IMPORTANT"],
                "payload": {
                    "headers": [{"name": "Subject", "value": "fixture important mail"}]
                },
            }
        ],
        fault="",
    )
    conn = connect(client, "gmail", "read")
    conv = conversation(client)
    run = client.post(
        f"/api/v1/connectors/{conn}/sync",
        json={
            "origin_conversation_id": conv,
            "idempotency_key": str(uuid4()),
            "query": {"query": "in:inbox"},
        },
    )
    run.raise_for_status()
    execute(client, db, run.json())
    signal = next(
        s
        for s in client.get("/api/v1/signals").json()["items"]
        if s["connection_id"] == conn
    )
    assert (
        signal["kind"] == "IMPORTANT_EMAIL"
        and signal["importance"] == 80
        and signal["correlation_key"] == "gmail:thread-one"
    )
    assert "确认" in signal["suggestion"]
    second = client.post(
        f"/api/v1/connectors/{conn}/sync",
        json={
            "origin_conversation_id": conv,
            "idempotency_key": str(uuid4()),
            "query": {},
        },
    ).json()
    execute(client, db, second)
    assert (
        db.execute(
            "SELECT count(*) AS n FROM app.proactive_signals WHERE connection_id=%s",
            (conn,),
        ).fetchone()["n"]
        == 1
    )
    assert (
        db.execute(
            "SELECT count(*) AS n FROM tools.effects WHERE tool_id=%s", ("gmail.send",)
        ).fetchone()["n"]
        == 0
    )
    assert (
        client.post(f"/api/v1/connectors/{conn}/revoke", json={}).json()["status"]
        == "REVOKED"
    )
    assert client.post(f"/api/v1/connectors/{conn}/query", json={}).status_code == 403
    assert (
        db.execute(
            "SELECT credentials FROM tools.connector_connections WHERE id=%s", (conn,)
        ).fetchone()["credentials"]
        is None
    )


def test_offline_push_and_resume_original_run(client, db):
    seed(events=calendar_events(), pushes=[], fault="")
    conn = connect(client, "calendar", "write")
    conv = conversation(client)
    prefs = {
        "enabled": True,
        "push_enabled": True,
        "min_importance": 70,
        "quiet_start": None,
        "quiet_end": None,
        "timezone": "Asia/Shanghai",
    }
    client.put("/api/v1/notification-preferences", json=prefs).raise_for_status()
    device = client.post(
        "/api/v1/push/devices", json={"token": "ab" * 32, "environment": "sandbox"}
    )
    device.raise_for_status()
    action = client.post(
        "/api/v1/actions",
        json={
            "connection_id": conn,
            "origin_conversation_id": conv,
            "kind": "calendar.update",
            "payload": {
                "event_id": "second",
                "start": "2026-10-13T12:00:00+08:00",
                "end": "2026-10-13T13:00:00+08:00",
            },
        },
    ).json()
    run = client.post(
        f"/api/v1/actions/{action['id']}/approve",
        json={"request_hash": action["request_hash"]},
    ).json()
    execute(client, db, run)
    # No client polling/SSE is required for server-side notification dispatch.
    notification = wait(
        lambda: db.execute(
            "SELECT * FROM app.notifications WHERE run_id=%s", (run["id"],)
        ).fetchone()
    )
    delivered = wait(
        lambda: db.execute(
            "SELECT * FROM app.push_deliveries WHERE notification_id=%s AND status='ACCEPTED'",
            (notification["id"],),
        ).fetchone()
    )
    pushes = httpx.get(FIXTURE + "/fixture/state", trust_env=False).json()["pushes"]
    payload = next(
        p["payload"]
        for p in pushes
        if p["payload"]["notification_id"] == str(notification["id"])
    )
    assert (
        payload["conversation_id"] == conv
        and payload["run_id"] == run["id"]
        and payload["action_id"] == action["id"]
    )
    resumed = client.get(f"/api/v1/notifications/{notification['id']}/resume")
    resumed.raise_for_status()
    assert (
        resumed.json()["conversation_id"] == conv
        and resumed.json()["run"]["id"] == run["id"]
        and resumed.json()["run"]["status"] == "COMPLETED"
    )
    assert "test-access" not in json.dumps(
        payload
    ) and "fixture meeting" not in json.dumps(payload)
    assert (
        db.execute(
            "SELECT token_cipher FROM app.push_devices WHERE id=%s",
            (device.json()["id"],),
        ).fetchone()["token_cipher"]
        != "ab" * 32
    )
    client.delete("/api/v1/push/devices/" + device.json()["id"]).raise_for_status()
    client.put(
        "/api/v1/notification-preferences", json={**prefs, "push_enabled": False}
    ).raise_for_status()


def test_matrix_revision_and_cross_user_ownership(client, db):
    task = client.post(
        "/api/v1/matrix",
        json={
            "title": "fixture focus task",
            "important": True,
            "urgent": False,
            "status": "TODO",
        },
    )
    task.raise_for_status()
    task = task.json()
    assert (
        next(
            t
            for t in client.get("/api/v1/matrix").json()["items"]
            if t["id"] == task["id"]
        )["quadrant"]
        == "PLAN"
    )
    body = {**task, "urgent": True}
    assert client.patch("/api/v1/matrix/" + task["id"], json=body).status_code == 200
    assert client.patch("/api/v1/matrix/" + task["id"], json=body).status_code == 409
    guest = httpx.Client(base_url=os.environ["ADEX_TEST_URL"], trust_env=False)
    guest.post("/api/v1/auth/guest", json={}).raise_for_status()
    assert guest.get("/api/v1/connectors").status_code == 403
    guest.close()
    client.delete("/api/v1/matrix/" + task["id"]).raise_for_status()


def test_connector_watch_reuses_occurrence_run_checkpoint_system(client, db):
    seed(messages=[], fault="")
    conn = connect(client, "gmail", "read")
    conv = conversation(client)
    schedule = client.post(
        f"/api/v1/connectors/{conn}/watch",
        json={"origin_conversation_id": conv, "idempotency_key": str(uuid4())},
    )
    schedule.raise_for_status()
    schedule = schedule.json()
    assert schedule["task_kind"] == "CONNECTOR_SYNC"
    db.execute(
        "UPDATE automation.schedules SET next_fire_at=now()-interval '1 second' WHERE id=%s",
        (schedule["id"],),
    )
    run = wait(
        lambda: db.execute(
            "SELECT * FROM automation.runs WHERE schedule_id=%s", (schedule["id"],)
        ).fetchone()
    )
    assert (
        run["kind"] == "CONNECTOR_SYNC" and str(run["request"]["connection_id"]) == conn
    )
    execute(client, db, {"id": str(run["id"])})
    assert (
        db.execute(
            "SELECT count(*) AS n FROM automation.occurrences WHERE schedule_id=%s",
            (schedule["id"],),
        ).fetchone()["n"]
        == 1
    )
    client.patch(
        "/api/v1/automations/" + schedule["id"],
        json={
            "status": "CANCELLED",
            "revision": db.execute(
                "SELECT revision FROM automation.schedules WHERE id=%s",
                (schedule["id"],),
            ).fetchone()["revision"],
        },
    ).raise_for_status()


def test_gmail_uncertain_send_reconciles_without_resubmission(client, db):
    seed(messages=[], fault="gmail_unknown", writes=0)
    conn = connect(client, "gmail", "send")
    conv = conversation(client)
    # The fixture emulates incremental consent; add read scope only for explicit
    # reconciliation, never grant gmail.modify or mailbox deletion.
    db.execute(
        "UPDATE tools.connector_connections SET scopes=scopes || '[\"https://www.googleapis.com/auth/gmail.readonly\"]'::jsonb WHERE id=%s",
        (conn,),
    )
    action = client.post(
        "/api/v1/actions",
        json={
            "connection_id": conn,
            "origin_conversation_id": conv,
            "kind": "gmail.send",
            "payload": {
                "to": "fixture@example.com",
                "subject": "fixture",
                "text": "TEST_FIXTURE only",
            },
        },
    ).json()
    run = client.post(
        f"/api/v1/actions/{action['id']}/approve",
        json={"request_hash": action["request_hash"]},
    ).json()
    claimed = claim()
    assert claimed["id"] == run["id"]
    done = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            "services/adex-agent",
            "python",
            "scripts/execute_run.py",
            json.dumps(claimed),
        ],
        cwd=ROOT,
        env=worker_env(),
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert done.returncode == 0
    assert (
        db.execute(
            "SELECT state FROM tools.approvals WHERE id=%s", (action["id"],)
        ).fetchone()["state"]
        == "UNKNOWN"
    )
    reconciled = client.post(f"/api/v1/actions/{action['id']}/reconcile", json={})
    reconciled.raise_for_status()
    assert reconciled.json()["verified"] and reconciled.json()["reconciled"]
    assert httpx.get(FIXTURE + "/fixture/state", trust_env=False).json()["writes"] == 1
    seed(fault="")


def test_oauth_wrong_session_and_resource_owner_cannot_access(client, db):
    start = client.post(
        "/api/v1/connectors/google/authorize",
        json={"service": "gmail", "access": "read"},
    ).json()
    consent = httpx.get(start["authorization_url"], trust_env=False).json()
    with httpx.Client(base_url=os.environ["ADEX_TEST_URL"], trust_env=False) as other:
        other.post(
            "/api/v1/auth/register",
            json={"username": "fixture_" + uuid4().hex[:10], "password": "fixture"},
        ).raise_for_status()
        bad = other.get(
            "/api/v1/connectors/google/callback",
            params={"state": consent["state"], "code": consent["code"]},
        )
        assert bad.status_code == 403
        valid = client.get(
            "/api/v1/connectors/google/callback",
            params={"state": consent["state"], "code": consent["code"]},
        )
        valid.raise_for_status()
        assert (
            other.post(
                "/api/v1/connectors/" + valid.json()["id"] + "/query", json={}
            ).status_code
            == 404
        )
        conn = valid.json()["id"]
        conv = conversation(client)
        assert (
            other.post(
                "/api/v1/connectors/" + conn + "/sync",
                json={
                    "origin_conversation_id": conv,
                    "query": {},
                    "idempotency_key": str(uuid4()),
                },
            ).status_code
            == 404
        )


def test_scopes_and_legacy_route_cannot_bypass_action_approval(client, db):
    seed(events=calendar_events(), fault="")
    read_conn = connect(client, "calendar", "read")
    conv = conversation(client)
    body = {
        "connection_id": read_conn,
        "origin_conversation_id": conv,
        "kind": "calendar.update",
        "payload": {
            "event_id": "second",
            "start": "2026-10-13T12:00:00Z",
            "end": "2026-10-13T13:00:00Z",
        },
    }
    assert client.post("/api/v1/actions", json=body).status_code == 403
    write_conn = connect(client, "calendar", "write")
    action = client.post(
        "/api/v1/actions", json={**body, "connection_id": write_conn}
    ).json()
    assert (
        client.post(f"/api/v1/approvals/{action['id']}/approve", json={}).status_code
        == 404
    )
    assert (
        db.execute(
            "SELECT state FROM tools.approvals WHERE id=%s", (action["id"],)
        ).fetchone()["state"]
        == "PENDING"
    )


def test_push_setup_status_and_idempotent_test_notification(client, db):
    status = client.get("/api/v1/push/status")
    status.raise_for_status()
    assert status.json()["availability"] == "CONFIGURED_UNVERIFIED"
    assert "token_cipher" not in status.text and "token_hash" not in status.text
    event = str(uuid4())
    conv = client.post(
        "/api/v1/conversations", json={"title": "TEST_FIXTURE push test"}
    ).json()["id"]
    first = client.post(
        "/api/v1/push/test", json={"event_id": event, "conversation_id": conv}
    )
    first.raise_for_status()
    second = client.post(
        "/api/v1/push/test", json={"event_id": event, "conversation_id": conv}
    )
    second.raise_for_status()
    assert first.json()["notification_id"] == second.json()["notification_id"]
    limited = client.post(
        "/api/v1/push/test", json={"event_id": str(uuid4()), "conversation_id": conv}
    )
    assert limited.status_code == 429
