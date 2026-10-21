"""Real isolated PG/API schedule edits, not external execution."""

from datetime import datetime, timezone, timedelta
from uuid import uuid4
from test_reliability import client, db, sign, wait


def test_schedule_edit_changes_future_work_but_preserves_runs(client, db):
    conv = client.post("/api/v1/conversations", json={"title": "edit fixture"}).json()[
        "id"
    ]
    first = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    r = client.post(
        "/api/v1/automations",
        json={
            "origin_conversation_id": conv,
            "title": "before",
            "instruction": "TEST_FIXTURE old",
            "kind": "INTERVAL",
            "interval_seconds": 600,
            "timezone": "Asia/Shanghai",
            "first_fire_at": first,
        },
        headers={"Idempotency-Key": str(uuid4())},
    )
    r.raise_for_status()
    saved = r.json()
    path = "/api/v1/automations/" + saved["id"]
    owner = client.get("/api/v1/me").json()["id"]
    rid = str(uuid4())
    db.execute(
        "INSERT INTO automation.runs(id,schedule_id,owner_id,origin_conversation_id,instruction,status,request) VALUES(%s,%s,%s,%s,'TEST_FIXTURE old','COMPLETED','{}')",
        (rid, saved["id"], owner, conv),
    )
    r = client.patch(
        path,
        json={
            "revision": saved["revision"],
            "title": "after",
            "instruction": "TEST_FIXTURE new",
        },
    )
    r.raise_for_status()
    current = r.json()
    assert current["next_fire_at"] == saved["next_fire_at"]
    assert current["title"] == "after" and current["instruction"] == "TEST_FIXTURE new"
    assert (
        db.execute(
            "SELECT instruction FROM automation.runs WHERE id=%s", (rid,)
        ).fetchone()["instruction"]
        == "TEST_FIXTURE old"
    )
    assert (
        client.patch(
            path, json={"revision": saved["revision"], "title": "stale"}
        ).status_code
        == 409
    )
    r = client.patch(
        path,
        json={
            "revision": current["revision"],
            "kind": "DAILY",
            "local_time": "19:00",
            "timezone": "Asia/Tokyo",
        },
    )
    r.raise_for_status()
    current = r.json()
    assert current["interval_seconds"] is None and current["local_time"].startswith(
        "19:00"
    )
    assert (
        datetime.fromisoformat(current["next_fire_at"].replace("Z", "+00:00"))
        .astimezone(timezone(timedelta(hours=9)))
        .hour
        == 19
    )
    assert (
        client.patch(
            path,
            json={
                "revision": current["revision"],
                "kind": "INTERVAL",
                "interval_seconds": 1,
            },
        ).status_code
        == 400
    )
    assert (
        client.patch(
            path, json={"revision": current["revision"], "timezone": "bad/zone"}
        ).status_code
        == 400
    )
    assert (
        client.patch(
            path, json={"revision": current["revision"], "owner_id": str(uuid4())}
        ).status_code
        == 400
    )
    r = client.patch(
        path,
        json={
            "revision": current["revision"],
            "kind": "INTERVAL",
            "interval_seconds": 1200,
            "status": "PAUSED",
        },
    )
    r.raise_for_status()
    current = r.json()
    assert current["status"] == "PAUSED" and current["local_time"] is None
    assert datetime.fromisoformat(
        current["next_fire_at"].replace("Z", "+00:00")
    ) > datetime.now(timezone.utc) + timedelta(minutes=19)
    assert (
        client.patch(
            path,
            json={
                "revision": current["revision"],
                "kind": "ONCE",
                "first_fire_at": (
                    datetime.now(timezone.utc) - timedelta(days=1)
                ).isoformat(),
            },
        ).status_code
        == 400
    )
    r = client.patch(
        path,
        json={
            "revision": current["revision"],
            "kind": "ONCE",
            "status": "ACTIVE",
            "first_fire_at": (
                datetime.now(timezone.utc) + timedelta(seconds=5)
            ).isoformat(),
        },
    )
    r.raise_for_status()
    current = r.json()
    assert current["interval_seconds"] is None and current["local_time"] is None
    # User scope remains resolved by the public gateway; a forged internal owner cannot edit.
    import httpx, os

    denied = httpx.patch(
        os.environ["ADEX_AUTOMATION_URL"] + "/internal/automations/" + saved["id"],
        json={"revision": current["revision"], "title": "foreign"},
        headers=sign("app", "automation", "schedule:write", str(uuid4()), saved["id"]),
        trust_env=False,
    )
    assert denied.status_code == 404

    claimed = wait(
        lambda: db.execute(
            "SELECT id,instruction FROM automation.runs WHERE schedule_id=%s AND id<>%s",
            (saved["id"], rid),
        ).fetchone()
    )
    assert claimed["instruction"] == "TEST_FIXTURE new"
    assert (
        db.execute(
            "SELECT count(*) AS n FROM automation.occurrences WHERE schedule_id=%s",
            (saved["id"],),
        ).fetchone()["n"]
        == 1
    )
    assert (
        client.patch(
            path, json={"revision": current["revision"] + 1, "title": "revive"}
        ).status_code
        == 409
    )

    # Consume our generated work so subsequent suites do not claim this fixture Run.
    client.post(
        "/api/v1/tasks/" + str(claimed["id"]) + "/cancel", json={}
    ).raise_for_status()
