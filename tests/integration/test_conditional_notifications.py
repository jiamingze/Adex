"""Real schedule/checkpoint/outbox/notification gates; quotes are explicitly synthetic."""

import hashlib
import json
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from psycopg.types.json import Jsonb
from test_reliability import client, db, write, wait

RULE = {
    "description": "TEST_FIXTURE 现货黄金低于800元/克",
    "operator": "lt",
    "threshold": "800",
    "unit": "CNY/g",
}


def test_conditional_results_backfill_chat_but_only_met_creates_notification(
    client, db
):
    owner = client.get("/api/v1/me").json()["id"]
    conv = client.post(
        "/api/v1/conversations", json={"title": "conditional fixture"}
    ).json()["id"]
    body = {
        "origin_conversation_id": conv,
        "title": "conditional fixture",
        "instruction": "TEST_FIXTURE 价格检查",
        "kind": "DAILY",
        "local_time": "08:00",
        "timezone": "Asia/Shanghai",
        "first_fire_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "notification_policy": "CONDITION_MET",
        "notification_condition": RULE,
    }
    created = client.post(
        "/api/v1/automations", json=body, headers={"Idempotency-Key": str(uuid4())}
    )
    created.raise_for_status()
    sid = created.json()["id"]
    assert created.json()["task_request"]["notification_condition"] == RULE
    revision = db.execute(
        "SELECT memory_revision FROM app.users WHERE id=%s", (owner,)
    ).fetchone()["memory_revision"]
    for status, value, should_notify in [
        ("NOT_MET", "810", False),
        ("UNKNOWN", "790", False),
        ("MET", "810", False),
        ("MET", "790", True),
        ("MISSING", "790", False),
        ("LEGACY", "790", False),
        ("LEGACY_FAIL", "", False),
        ("FAIL", "", False),
    ]:
        rid, attempt, ref = str(uuid4()), str(uuid4()), str(uuid4())
        request = {
            "notification_policy": "CONDITION_MET",
            "notification_condition": RULE,
        }
        if status.startswith("LEGACY"):
            request = {"notification_policy": "EVERY_RUN"}
        db.execute(
            "INSERT INTO automation.runs(id,schedule_id,owner_id,origin_conversation_id,instruction,status,epoch,attempt_id,worker_id,lease_until,request) VALUES(%s,%s,%s,%s,'fixture','RUNNING',1,%s,'fixture',now()+interval '60 seconds',%s)",
            (rid, sid, owner, conv, attempt, Jsonb(request)),
        )
        run = {"id": rid, "owner_id": owner, "epoch": 1, "attempt_id": attempt}
        if status in {"FAIL", "LEGACY_FAIL"}:
            write(
                run, "fail", {"code": "SEARCH_UNAVAILABLE", "memory_revision": revision}
            ).raise_for_status()
        else:
            state = {
                "phase": "result",
                "schema_version": 1,
                "content": f"TEST_FIXTURE {rid}",
                "artifact": {},
            }
            if status not in {"MISSING", "LEGACY"}:
                state["notification_assessment"] = {
                    "condition": RULE,
                    "status": status,
                    "value": value,
                    "unit": "CNY/g",
                    "evidence": [
                        {
                            "url": "https://example.test/price",
                            "quote": f"TEST_FIXTURE {value} 元/克",
                            "source_kind": "BROWSER_RENDERED_PAGE",
                            "fetched_at": datetime.now(timezone.utc).isoformat(),
                        }
                    ],
                }
            sha = hashlib.sha256(
                json.dumps(
                    state, sort_keys=True, ensure_ascii=False, default=str
                ).encode()
            ).hexdigest()
            db.execute(
                "INSERT INTO agent.checkpoints(id,run_id,owner_id,epoch,attempt_id,logical_key,memory_revision,schema_version,state,sha256) VALUES(%s,%s,%s,1,%s,'result',%s,1,%s,%s)",
                (ref, rid, owner, attempt, revision, Jsonb(state), sha),
            )
            write(run, "checkpoint", {"checkpoint_ref": ref}).raise_for_status()
            write(run, "complete", {"checkpoint_ref": ref}).raise_for_status()
        event = wait(
            lambda: db.execute(
                "SELECT * FROM automation.outbox WHERE run_id=%s", (rid,)
            ).fetchone()
        )
        assert event["payload"]["notify"] is should_notify
        wait(
            lambda: db.execute(
                "SELECT delivered_at FROM automation.outbox WHERE run_id=%s", (rid,)
            ).fetchone()["delivered_at"]
        )
        assert (
            db.execute(
                "SELECT count(*) AS n FROM app.messages WHERE conversation_id=%s AND role='assistant' AND dedupe_key=%s",
                (conv, "run:" + rid),
            ).fetchone()["n"]
            == 1
        )
        assert db.execute(
            "SELECT count(*) AS n FROM app.notifications WHERE run_id=%s", (rid,)
        ).fetchone()["n"] == int(should_notify)
        # Duplicate delivery cannot create another conversation message or notification.
        import httpx, os
        from test_reliability import sign

        replay = httpx.post(
            os.environ["ADEX_APP_URL"] + "/internal/results/attach",
            json=event["payload"],
            headers=sign("automation", "app", "result:attach", owner, conv),
            trust_env=False,
        )
        replay.raise_for_status()
        assert db.execute(
            "SELECT count(*) AS n FROM app.notifications WHERE run_id=%s", (rid,)
        ).fetchone()["n"] == int(should_notify)


def test_chat_keeps_numeric_notification_rule_with_schedule(client):
    from test_chat_productivity import chat

    conv, path, body, answer = chat(
        client, "每10分钟检查现货黄金价格，低于800元/克才通知我，否则只记录到会话"
    )
    assert "不发通知" in answer["content"]
    schedules = client.get("/api/v1/automations").json()["items"]
    saved = next(s for s in schedules if s["origin_conversation_id"] == conv)
    assert saved["task_request"]["notification_policy"] == "CONDITION_MET"
    assert saved["task_request"]["notification_condition"]["threshold"] == "800"


def test_worker_records_unknown_condition_silently_when_search_is_unavailable(
    client, db
):
    # This stack deliberately has no Tavily key: missing evidence must not become MET.
    from test_connectors import execute

    owner = client.get("/api/v1/me").json()["id"]
    conv = client.post(
        "/api/v1/conversations", json={"title": "conditional unavailable fixture"}
    ).json()["id"]
    created = client.post(
        "/api/v1/automations",
        json={
            "origin_conversation_id": conv,
            "title": "fixture",
            "instruction": "TEST_FIXTURE 查询现货黄金价格",
            "kind": "INTERVAL",
            "interval_seconds": 600,
            "timezone": "Asia/Shanghai",
            "first_fire_at": (
                datetime.now(timezone.utc) + timedelta(days=1)
            ).isoformat(),
            "notification_policy": "CONDITION_MET",
            "notification_condition": RULE,
        },
        headers={"Idempotency-Key": str(uuid4())},
    )
    created.raise_for_status()
    sid = created.json()["id"]
    db.execute(
        "UPDATE automation.schedules SET next_fire_at=clock_timestamp() WHERE id=%s",
        (sid,),
    )
    run = wait(
        lambda: db.execute(
            "SELECT * FROM automation.runs WHERE schedule_id=%s AND status='QUEUED'",
            (sid,),
        ).fetchone()
    )
    execute(client, db, dict(run, id=str(run["id"])))
    saved = db.execute(
        "SELECT checkpoint_ref FROM automation.runs WHERE id=%s", (run["id"],)
    ).fetchone()
    state = db.execute(
        "SELECT state FROM agent.checkpoints WHERE id=%s", (saved["checkpoint_ref"],)
    ).fetchone()["state"]
    assert state["notification_assessment"]["status"] == "UNKNOWN"
    assert "不发通知" in state["content"]
    assert not db.execute(
        "SELECT id FROM app.notifications WHERE run_id=%s", (run["id"],)
    ).fetchone()
    assert (
        db.execute(
            "SELECT count(*) AS n FROM app.messages WHERE conversation_id=%s AND dedupe_key=%s",
            (conv, "run:" + str(run["id"])),
        ).fetchone()["n"]
        == 1
    )


def test_existing_schedule_rule_update_is_revision_checked(client, db):
    conv = client.post('/api/v1/conversations', json={'title': 'rule repair fixture'}).json()['id']
    created = client.post('/api/v1/automations', json={
        'origin_conversation_id': conv, 'title': 'fixture', 'instruction': 'TEST_FIXTURE',
        'kind': 'INTERVAL', 'interval_seconds': 600, 'timezone': 'Asia/Shanghai',
        'first_fire_at': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
    }, headers={'Idempotency-Key': str(uuid4())})
    created.raise_for_status()
    saved = created.json()
    path = '/api/v1/automations/' + saved['id']
    patch = {'revision': saved['revision'], 'notification_policy': 'CONDITION_MET', 'notification_condition': RULE}
    import httpx
    assert httpx.patch(str(client.base_url).rstrip('/') + path, json=patch, trust_env=False).status_code == 401
    assert client.patch(path, json={'revision': saved['revision']}).status_code == 400
    updated = client.patch(path, json=patch)
    updated.raise_for_status()
    assert updated.json()['task_request']['notification_condition'] == RULE
    assert updated.json()['status'] == 'ACTIVE'
    assert client.patch(path, json=patch).status_code == 409
    assert client.patch(path, json={'revision': updated.json()['revision'], 'notification_policy': 'CONDITION_MET'}).status_code == 400
    assert client.patch(path, json={'revision': updated.json()['revision'], 'notification_policy': 'EVERY_RUN'}).status_code == 200
