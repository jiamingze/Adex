import base64
import hashlib
import hmac
import json
import os
import signal
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
import httpx
import psycopg
import pytest
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[2]
BASE = os.environ["ADEX_TEST_URL"]


def sign(issuer, aud, scope, owner="*", resource="*"):
    p = (
        base64.urlsafe_b64encode(
            json.dumps(
                {
                    "iss": issuer,
                    "aud": aud,
                    "scope": scope,
                    "owner": str(owner),
                    "resource": str(resource),
                    "exp": int(time.time()) + 180,
                }
            ).encode()
        )
        .decode()
        .rstrip("=")
    )
    sig = (
        base64.urlsafe_b64encode(
            hmac.new(
                os.environ[f"ADEX_{issuer.upper()}_KEY"].encode(),
                p.encode(),
                hashlib.sha256,
            ).digest()
        )
        .decode()
        .rstrip("=")
    )
    return {"Authorization": "Bearer " + p + "." + sig}


def wait(fn, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = fn()
        if value:
            return value
        time.sleep(0.2)
    raise AssertionError("Timed out waiting for durable state")


@pytest.fixture(scope="module")
def db():
    assert os.environ["ADEX_PG_DB"].startswith("adex_test_"), (
        "Never run fault tests against user data"
    )
    with psycopg.connect(
        host=os.environ["ADEX_PG_HOST"],
        port=os.environ["ADEX_PG_PORT"],
        dbname=os.environ["ADEX_PG_DB"],
        user="adex_admin",
        password=os.environ["ADEX_ADMIN_PASSWORD"],
        autocommit=True,
        row_factory=dict_row,
    ) as conn:
        yield conn


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=BASE, timeout=20, trust_env=False) as c:
        r = c.post(
            "/api/v1/auth/login",
            json={
                "username": os.environ["ADEX_OWNER_USERNAME"],
                "password": os.environ["ADEX_OWNER_PASSWORD"],
            },
        )
        r.raise_for_status()
        c.headers.update({"Authorization": "Bearer " + r.json()["token"]})
        yield c


def occurrence(client, db):
    conv = client.post("/api/v1/conversations", json={"title": "fault fixture"}).json()[
        "id"
    ]
    body = {
        "title": "fixture schedule",
        "instruction": "只回复：持久任务验收通过",
        "kind": "ONCE",
        "timezone": "Asia/Shanghai",
        "origin_conversation_id": conv,
        "first_fire_at": (
            datetime.now(timezone.utc) + timedelta(seconds=2)
        ).isoformat(),
    }
    key = str(uuid4())
    with ThreadPoolExecutor(max_workers=5) as pool:
        responses = list(
            pool.map(
                lambda _: client.post(
                    "/api/v1/automations", json=body, headers={"Idempotency-Key": key}
                ),
                range(5),
            )
        )
    assert all(r.status_code == 200 for r in responses), [
        (r.status_code, r.text) for r in responses
    ]
    assert len({r.json()["id"] for r in responses}) == 1
    sid = responses[0].json()["id"]
    assert (
        client.post(
            "/api/v1/automations",
            json=body | {"title": "changed"},
            headers={"Idempotency-Key": key},
        ).status_code
        == 409
    )
    row = wait(
        lambda: db.execute(
            "SELECT * FROM automation.occurrences WHERE schedule_id=%s", (sid,)
        ).fetchone()
    )
    assert (
        db.execute(
            "SELECT count(*) AS n FROM automation.occurrences WHERE schedule_id=%s",
            (sid,),
        ).fetchone()["n"]
        == 1
    )
    return conv, db.execute(
        "SELECT * FROM automation.runs WHERE id=%s", (row["run_id"],)
    ).fetchone()


def claim():
    with httpx.Client(timeout=15, trust_env=False) as c:
        r = c.post(
            os.environ["ADEX_AUTOMATION_URL"] + "/internal/runs/claim",
            headers=sign("agent", "automation", "run:claim"),
            json={"worker_id": "fault-fixture-" + str(uuid4())},
        )
        r.raise_for_status()
        return r.json()["run"]


def write(run, action, extra=None):
    return httpx.post(
        os.environ["ADEX_AUTOMATION_URL"] + f"/internal/runs/{run['id']}/{action}",
        headers=sign("agent", "automation", "run:write", run["owner_id"], run["id"]),
        json={"attempt_id": run["attempt_id"], "epoch": run["epoch"]} | (extra or {}),
        trust_env=False,
        timeout=15,
    )


def worker_env():
    e = dict(os.environ)
    e["ADEX_SERVICE"] = "agent"
    e["ADEX_DB_URL"] = (
        f"postgresql://adex_agent:{e['ADEX_AGENT_DB_PASSWORD']}@{e['ADEX_PG_HOST']}:{e['ADEX_PG_PORT']}/{e['ADEX_PG_DB']}"
    )
    return e


def test_three_schedulers_sigkill_fencing_resume_and_outbox(client, db):
    conv, queued = occurrence(client, db)
    with ThreadPoolExecutor(max_workers=8) as pool:
        claims = list(pool.map(lambda _: claim(), range(8)))
    nonempty = [c for c in claims if c]
    assert len(nonempty) == 1
    run = nonempty[0]
    assert run["id"] == str(queued["id"])
    gate = ROOT / ".local-data" / ("checkpoint-gate-" + uuid4().hex)
    e = worker_env()
    e["ADEX_TEST_CHECKPOINT_GATE"] = str(gate)
    log = (ROOT / ".local-data/recovery-worker.log").open("w")
    worker = subprocess.Popen(
        [
            "uv",
            "run",
            "--project",
            "services/adex-agent",
            "python",
            "scripts/execute_run.py",
            json.dumps(run),
        ],
        cwd=ROOT,
        env=e,
        stdout=log,
        stderr=log,
        start_new_session=True,
    )
    try:
        wait(lambda: gate.exists())
        before = db.execute(
            "SELECT checkpoint_ref FROM automation.runs WHERE id=%s", (run["id"],)
        ).fetchone()["checkpoint_ref"]
        assert before
        os.killpg(worker.pid, signal.SIGKILL)
        worker.wait(timeout=5)
    finally:
        if worker.poll() is None:
            os.killpg(worker.pid, signal.SIGKILL)
            worker.wait()
        log.close()
        gate.unlink(missing_ok=True)
    db.execute(
        "UPDATE automation.runs SET lease_until=clock_timestamp()-interval '1 second' WHERE id=%s",
        (run["id"],),
    )
    recovered = claim()
    assert recovered["epoch"] == run["epoch"] + 1
    assert recovered["attempt_id"] != run["attempt_id"]
    assert write(run, "heartbeat").status_code == 409
    assert write(run, "complete", {"checkpoint_ref": str(before)}).status_code == 409
    e.pop("ADEX_TEST_CHECKPOINT_GATE", None)
    subprocess.run(
        [
            "uv",
            "run",
            "--project",
            "services/adex-agent",
            "python",
            "scripts/execute_run.py",
            json.dumps(recovered),
        ],
        cwd=ROOT,
        env=e,
        check=True,
        capture_output=True,
        timeout=30,
    )
    state = db.execute(
        "SELECT status FROM automation.runs WHERE id=%s", (run["id"],)
    ).fetchone()["status"]
    assert state == "COMPLETED"
    assert (
        db.execute(
            "SELECT count(*) AS n FROM agent.invocations WHERE invocation_key LIKE %s",
            ("run:" + run["id"] + "%",),
        ).fetchone()["n"]
        == 1
    )
    wait(
        lambda: db.execute(
            "SELECT 1 FROM app.messages WHERE dedupe_key=%s", ("run:" + run["id"],)
        ).fetchone()
    )
    # Force transport replay after consumer commit: one message and notification remain.
    db.execute(
        "UPDATE automation.outbox SET delivered_at=NULL,next_attempt_at=now(),lease_until=NULL WHERE run_id=%s",
        (run["id"],),
    )
    wait(
        lambda: db.execute(
            "SELECT delivered_at FROM automation.outbox WHERE run_id=%s AND delivered_at IS NOT NULL",
            (run["id"],),
        ).fetchone()
    )
    assert (
        db.execute(
            "SELECT count(*) AS n FROM app.messages WHERE dedupe_key=%s",
            ("run:" + run["id"],),
        ).fetchone()["n"]
        == 1
    )
    assert (
        db.execute(
            "SELECT count(*) AS n FROM app.notifications WHERE conversation_id=%s",
            (conv,),
        ).fetchone()["n"]
        == 1
    )
    statuses = db.execute(
        "SELECT status FROM automation.attempts WHERE run_id=%s ORDER BY epoch",
        (run["id"],),
    ).fetchall()
    assert [r["status"] for r in statuses] == ["LOST", "COMPLETED"]
    with pytest.raises(psycopg.Error):
        db.execute(
            "UPDATE agent.checkpoints SET sha256='tampered' WHERE id=%s", (before,)
        )


def test_tenant_isolation_and_schema_roles(client, db):
    uid = str(uuid4())
    cid = str(uuid4())
    db.execute(
        "INSERT INTO app.users(id,username,password_hash) VALUES(%s,%s,'unusable')",
        (uid, "fixture-" + uid),
    )
    db.execute(
        "INSERT INTO app.conversations(id,owner_id,title) VALUES(%s,%s,'other-user')",
        (cid, uid),
    )
    assert client.get(f"/api/v1/conversations/{cid}/messages").status_code == 404
    assert (
        client.post(
            f"/api/v1/conversations/{cid}/messages",
            json={"client_message_id": str(uuid4()), "content": "unauthorized"},
        ).status_code
        == 404
    )
    with psycopg.connect(
        host=os.environ["ADEX_PG_HOST"],
        port=os.environ["ADEX_PG_PORT"],
        dbname=os.environ["ADEX_PG_DB"],
        user="adex_agent",
        password=os.environ["ADEX_AGENT_DB_PASSWORD"],
        autocommit=True,
    ) as agent:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            agent.execute("SELECT * FROM app.messages")
    bad = sign("tools", "automation", "run:claim")
    assert (
        httpx.post(
            os.environ["ADEX_AUTOMATION_URL"] + "/internal/runs/claim",
            headers=bad,
            json={"worker_id": "fake"},
            trust_env=False,
        ).status_code
        == 403
    )


def test_memory_deletion_invalidates_context_and_inflight_results(client, db):
    conv = client.post(
        "/api/v1/conversations", json={"title": "forgetting fixture"}
    ).json()["id"]
    owner = client.get("/api/v1/me").json()["id"]
    fact = "test secret preference " + str(uuid4())
    r = client.post(
        f"/api/v1/conversations/{conv}/messages",
        json={"client_message_id": str(uuid4()), "content": "记住：" + fact},
    )
    r.raise_for_status()
    wait(
        lambda: any(
            m["content"] == fact for m in client.get("/api/v1/memories").json()["items"]
        )
    )
    m = next(
        m
        for m in client.get("/api/v1/memories").json()["items"]
        if m["content"] == fact
    )
    old = client.get("/api/v1/me").json()["memory_revision"]
    client.delete("/api/v1/memories/" + m["id"]).raise_for_status()
    ctx = httpx.get(
        BASE + "/internal/context/" + conv,
        headers=sign("agent", "app", "context:read", owner, conv),
        trust_env=False,
    ).json()
    assert fact not in json.dumps(ctx)
    assert ctx["memory_revision"] > old
    payload = {
        "event_id": str(uuid4()),
        "run_id": str(uuid4()),
        "owner_id": owner,
        "origin_conversation_id": conv,
        "content": fact,
        "memory_revision": old,
    }
    response = httpx.post(
        BASE + "/internal/results/attach",
        headers=sign("automation", "app", "result:attach", owner, conv),
        json=payload,
        trust_env=False,
    )
    assert response.json()["discarded"] == "MEMORY_REVISION_CHANGED"
    assert (
        db.execute(
            "SELECT count(*) AS n FROM app.messages WHERE dedupe_key=%s",
            ("run:" + payload["run_id"],),
        ).fetchone()["n"]
        == 0
    )
    assert client.post("/api/v1/memories", json={"content": fact}).status_code == 409


def test_snapshot_and_sse_replay(client):
    conv = client.post(
        "/api/v1/conversations", json={"title": "SSE replay fixture"}
    ).json()["id"]
    client.post(
        f"/api/v1/conversations/{conv}/messages",
        json={"client_message_id": str(uuid4()), "content": "stream fixture"},
    ).raise_for_status()
    snapshot = wait(
        lambda: (
            lambda s: s if any(m["role"] == "assistant" for m in s["items"]) else None
        )(client.get(f"/api/v1/conversations/{conv}/messages").json())
    )
    with client.stream(
        "GET", f"/api/v1/conversations/{conv}/events?after_seq=0"
    ) as response:
        assert response.status_code == 200
        seen = []
        for line in response.iter_lines():
            if line.startswith("id:"):
                seen.append(int(line[3:]))
            if seen and seen[-1] >= snapshot["event_seq"]:
                break
    assert seen == list(range(1, snapshot["event_seq"] + 1))


def test_unknown_provider_call_never_resubmits(client, db):
    owner = client.get("/api/v1/me").json()["id"]
    e = worker_env()
    e["ADEX_UNKNOWN_FIXTURE_OWNER"] = owner
    result = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            "services/adex-agent",
            "python",
            "scripts/test_unknown.py",
        ],
        cwd=ROOT,
        env=e,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert "UNKNOWN no resubmit PASS" in result.stdout


def test_redis_and_es_outage_degrade_without_losing_messages(client, db):
    assert os.environ["ADEX_REDIS_URL"].endswith(":56380/0")
    os.kill(int(os.environ["ADEX_TEST_REDIS_PID"]), signal.SIGTERM)
    state = wait(
        lambda: (lambda r: r if r.get("redis") == "DEGRADED" else None)(
            httpx.get(
                os.environ["ADEX_AGENT_URL"] + "/health/ready", trust_env=False
            ).json()
        )
    )
    assert state["status"] == "UP"
    conv = client.post(
        "/api/v1/conversations", json={"title": "cache outage fixture"}
    ).json()["id"]
    client.post(
        f"/api/v1/conversations/{conv}/messages",
        json={"client_message_id": str(uuid4()), "content": "Redis outage fixture"},
    ).raise_for_status()
    wait(
        lambda: any(
            m["role"] == "assistant"
            for m in client.get(f"/api/v1/conversations/{conv}/messages").json()[
                "items"
            ]
        )
    )
    assert (
        db.execute(
            "SELECT count(*) AS n FROM app.outbox WHERE kind LIKE 'memory.index:%' AND delivered_at IS NULL"
        ).fetchone()["n"]
        > 0
    )


def test_deleted_conversation_invalidates_sources_and_consumes_results(client, db):
    owner = client.get("/api/v1/me").json()["id"]
    conv = client.post("/api/v1/conversations", json={"title": "delete source fixture"}).json()["id"]
    fact = "deleted-source-" + uuid4().hex
    client.post(f"/api/v1/conversations/{conv}/messages", json={"content": "记住：" + fact, "client_message_id": str(uuid4())}).raise_for_status()
    wait(lambda: any(m["content"] == fact for m in client.get("/api/v1/memories").json()["items"]))
    message = db.execute("SELECT id FROM app.messages WHERE conversation_id=%s AND role='user' LIMIT 1", (conv,)).fetchone()["id"]
    client.delete(f"/api/v1/conversations/{conv}").raise_for_status()
    assert not any(m["content"] == fact for m in client.get("/api/v1/memories").json()["items"])
    db.execute("INSERT INTO app.outbox(id,kind,resource_id) VALUES(%s,'memory.extract',%s) ON CONFLICT(kind,resource_id) DO UPDATE SET delivered_at=NULL,next_attempt_at=now()", (uuid4(), message))
    wait(lambda: db.execute("SELECT count(*) AS n FROM app.outbox WHERE resource_id=%s AND kind='memory.extract' AND delivered_at IS NULL", (message,)).fetchone()["n"] == 0)
    assert client.post("/api/v1/memories", json={"content": fact}).status_code == 409
    for endpoint, scope in [("results", "result:attach"), ("monitors", "monitor:attach")]:
        payload = {"event_id": str(uuid4()), "run_id": str(uuid4()), "owner_id": owner, "origin_conversation_id": conv, "content": fact, "memory_revision": client.get("/api/v1/me").json()["memory_revision"]}
        response = httpx.post(BASE + f"/internal/{endpoint}/attach", headers=sign("automation", "app", scope, owner, conv), json=payload, trust_env=False)
        assert response.status_code == 200, response.text
        assert response.json()["discarded"] == "CONVERSATION_DELETED"
        assert db.execute("SELECT count(*) AS n FROM app.notifications WHERE event_id=%s", (payload["event_id"],)).fetchone()["n"] == 0


def test_z_postgres_unavailable_rejects_authoritative_writes(client):
    from psycopg import sql

    name = os.environ["ADEX_PG_DB"]
    assert name.startswith("adex_test_")
    with psycopg.connect(
        host=os.environ["ADEX_PG_HOST"],
        port=os.environ["ADEX_PG_PORT"],
        dbname="postgres",
        user="adex_admin",
        password=os.environ["ADEX_ADMIN_PASSWORD"],
        autocommit=True,
    ) as admin:
        try:
            admin.execute(
                sql.SQL("ALTER DATABASE {} ALLOW_CONNECTIONS false").format(
                    sql.Identifier(name)
                )
            )
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s",
                (name,),
            )
            response = client.post(
                "/api/v1/conversations", json={"title": "must not persist"}
            )
            assert response.status_code == 503
            assert response.json()["code"] == "DATABASE_UNAVAILABLE"
            assert httpx.get(BASE + "/health/ready", trust_env=False).status_code == 503
        finally:
            admin.execute(
                sql.SQL("ALTER DATABASE {} ALLOW_CONNECTIONS true").format(
                    sql.Identifier(name)
                )
            )
        wait(
            lambda: httpx.get(BASE + "/health/ready", trust_env=False).status_code
            == 200,
            timeout=30,
        )
