"""Permanent schedule deletion in isolated PG; no real external effects."""

import os
import httpx
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from test_reliability import client, db, sign


def test_delete_physically_removes_schedule_fences_runs_and_does_not_resurrect(
    client, db
):
    owner = client.get("/api/v1/me").json()["id"]
    conv = client.post(
        "/api/v1/conversations", json={"title": "delete schedule fixture"}
    ).json()["id"]
    key = str(uuid4())
    body = {
        "origin_conversation_id": conv,
        "title": "DELETE_TEST_FIXTURE",
        "instruction": "fixture read",
        "kind": "ONCE",
        "timezone": "Asia/Shanghai",
        "first_fire_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
    }
    created = client.post(
        "/api/v1/automations", json=body, headers={"Idempotency-Key": key}
    )
    created.raise_for_status()
    schedule = created.json()
    sid = schedule["id"]
    waiting, completed = str(uuid4()), str(uuid4())
    for rid, status in [(waiting, "WAITING_INPUT"), (completed, "COMPLETED")]:
        db.execute(
            "INSERT INTO automation.runs(id,schedule_id,owner_id,origin_conversation_id,instruction,status,epoch) VALUES(%s,%s,%s,%s,'fixture',%s,3)",
            (rid, sid, owner, conv, status),
        )
    db.execute(
        "INSERT INTO automation.occurrences(schedule_id,scheduled_at,run_id,status) VALUES(%s,now(),%s,'CREATED')",
        (sid, waiting),
    )
    assert client.delete(f"/api/v1/automations/{sid}?revision=9999").status_code == 409
    assert client.delete(f"/api/v1/automations/{sid}?revision=1").status_code == 200
    assert (
        db.execute(
            "SELECT count(*) AS n FROM automation.schedules WHERE id=%s", (sid,)
        ).fetchone()["n"]
        == 0
    )
    assert (
        db.execute(
            "SELECT count(*) AS n FROM automation.occurrences WHERE schedule_id=%s",
            (sid,),
        ).fetchone()["n"]
        == 0
    )
    rows = db.execute(
        "SELECT id,status,epoch,schedule_id FROM automation.runs WHERE id IN (%s,%s)",
        (waiting, completed),
    ).fetchall()
    assert len(rows) == 2 and all(r["schedule_id"] is None for r in rows)
    assert next(r for r in rows if str(r["id"]) == waiting)["status"] == "CANCELLED"
    assert next(r for r in rows if str(r["id"]) == waiting)["epoch"] == 4
    assert next(r for r in rows if str(r["id"]) == completed)["status"] == "COMPLETED"
    assert not any(
        s["id"] == sid for s in client.get("/api/v1/automations").json()["items"]
    )
    assert client.delete(f"/api/v1/automations/{sid}?revision=1").status_code == 200
    assert (
        client.post(
            "/api/v1/automations", json=body, headers={"Idempotency-Key": key}
        ).status_code
        == 410
    )
    assert client.delete(f"/api/v1/automations/{uuid4()}?revision=1").status_code == 404
    cancelled = client.post(
        "/api/v1/automations", json=body, headers={"Idempotency-Key": str(uuid4())}
    ).json()
    update = client.patch(
        f"/api/v1/automations/{cancelled['id']}",
        json={"status": "CANCELLED", "revision": cancelled["revision"]},
    )
    update.raise_for_status()
    assert (
        client.delete(
            f"/api/v1/automations/{cancelled['id']}?revision={update.json()['revision']}"
        ).status_code
        == 200
    )
    wrong = sign("app", "automation", "schedule:write", uuid4(), sid)
    auto = os.environ["ADEX_AUTOMATION_URL"]
    assert (
        httpx.delete(
            f"{auto}/internal/automations/{sid}?revision=1",
            headers=wrong,
            trust_env=False,
        ).status_code
        == 404
    )
