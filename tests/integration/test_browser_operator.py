"""Real Chromium + isolated PG/HTTP; synthetic publisher, NOT real account execution."""

import json
import os
import subprocess
from uuid import uuid4
import httpx
from test_reliability import client, db, claim, worker_env, wait, sign


def execute(run):
    script = """import asyncio,json,sys
from adex_kernel.core import Core
from adex_agent.execution.runtime import Runtime
async def main():
 core=Core('agent');await core.start();runtime=Runtime(core)
 try: await runtime.background_run(json.loads(sys.argv[1]))
 finally: await runtime.redis.aclose();await core.pool.close()
asyncio.run(main())"""
    response = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            "services/adex-agent",
            "python",
            "-c",
            script,
            json.dumps(run),
        ],
        env=worker_env(),
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert response.returncode == 0, response.stderr


def create(client, goal="TEST_FIXTURE 发布演练"):
    conv = client.post(
        "/api/v1/conversations", json={"title": "TEST_FIXTURE Browser"}
    ).json()["id"]
    response = client.post(
        "/api/v1/tasks",
        headers={"Idempotency-Key": str(uuid4())},
        json={
            "kind": "BROWSER",
            "instruction": goal,
            "origin_conversation_id": conv,
            "browser_url": "https://example.com/fixture",
        },
    )
    response.raise_for_status()
    return conv, response.json()["id"]


def session(client, run):
    return next(
        row
        for row in client.get("/api/v1/browser/sessions").json()["items"]
        if str(row["run_id"]) == str(run)
    )


def state(db, run):
    return db.execute("SELECT * FROM automation.runs WHERE id=%s", (run,)).fetchone()


def cleanup_notifications(db, run):
    wait(
        lambda: db.execute(
            "SELECT count(*) AS n FROM automation.outbox WHERE run_id=%s AND delivered_at IS NULL",
            (run,),
        ).fetchone()["n"]
        == 0
    )
    db.execute("UPDATE app.notifications SET read=true WHERE run_id=%s", (run,))


def test_generic_browser_prepare_approve_dispatch_receipt_same_run(client, db):
    conv, run = create(client)
    first = claim()
    assert first["id"] == run
    execute(first)
    assert state(db, run)["status"] == "WAITING_INPUT", state(db, run)
    item = session(client, run)
    action = next(
        a
        for a in client.get("/api/v1/actions").json()["items"]
        if a["id"] == item["action_id"]
    )
    assert action["kind"] == "browser.request" and action["state"] == "PENDING"
    assert action["request"]["payload"]["fields"]["title"] == "TEST_FIXTURE 标题"
    assert (
        db.execute(
            "SELECT count(*) AS n FROM tools.effects WHERE tool_id='browser.request'"
        ).fetchone()["n"]
        == 0
    )
    confirmed = client.post(
        f"/api/v1/actions/{action['id']}/approve",
        json={"request_hash": action["request_hash"]},
    )
    confirmed.raise_for_status()
    assert confirmed.json()["id"] == run
    second = claim()
    assert second["id"] == run and second["epoch"] > first["epoch"]
    execute(second)
    assert state(db, run)["status"] == "COMPLETED", state(db, run)
    receipt = db.execute(
        "SELECT result FROM tools.approvals WHERE id=%s", (action["id"],)
    ).fetchone()["result"]
    assert (
        receipt["verified"]
        and receipt["test_fixture"]
        and receipt["provider_receipt"] == "TEST_FIXTURE_NOTE_001"
    )
    wait(
        lambda: db.execute(
            "SELECT count(*) AS n FROM app.messages WHERE conversation_id=%s AND role='assistant'",
            (conv,),
        ).fetchone()["n"]
        >= 2
    )
    assert (
        db.execute(
            "SELECT count(*) AS n FROM automation.outbox WHERE run_id=%s", (run,)
        ).fetchone()["n"]
        == 2
    )
    with httpx.Client(base_url=str(client.base_url), trust_env=False) as other:
        login = other.post(
            "/api/v1/auth/register",
            json={"username": "browser-" + str(uuid4())[:8], "password": "fixture"},
        ).json()
        other.headers.update({"Authorization": "Bearer " + login["token"]})
        assert other.get(f"/api/v1/browser/sessions/{item['id']}").status_code == 404
    client.post(
        f"/api/v1/browser/sessions/{item['id']}/close", json={}
    ).raise_for_status()

    cleanup_notifications(db, run)


def test_browser_login_takeover_resumes_same_run_without_password_in_checkpoint(
    client, db
):
    conv, run = create(client)
    claimed = claim()
    assert claimed["id"] == run
    owner = claimed["owner_id"]
    headers = sign("agent", "tools", "browser:operate", owner, run)
    execution = {
        "run_id": run,
        "epoch": claimed["epoch"],
        "attempt_id": claimed["attempt_id"],
    }
    ensured = httpx.post(
        os.environ["ADEX_TOOLS_URL"] + "/internal/browser/operator/ensure",
        headers=headers,
        json={
            **execution,
            "conversation_id": conv,
            "url": "https://example.com/fixture",
        },
        trust_env=False,
    )
    ensured.raise_for_status()
    sid = ensured.json()["id"]
    # First observation initializes the process; then user can safely take control.
    httpx.post(
        os.environ["ADEX_TOOLS_URL"] + f"/internal/browser/operator/{sid}/observe",
        headers=headers,
        json=execution,
        trust_env=False,
    ).raise_for_status()
    takeover = client.post(
        f"/api/v1/browser/sessions/{sid}/control", json={"action": "takeover"}
    )
    takeover.raise_for_status()
    assert takeover.json()["status"] == "HUMAN"
    execute(claimed)
    assert state(db, run)["status"] == "WAITING_INPUT"
    view = client.get(f"/api/v1/browser/sessions/{sid}").json()
    node = next(n for n in view["nodes"] if n.get("name") == "密码" and n.get("id"))
    password = "PRIVATE_TEST_FIXTURE_PASSWORD"
    typed = client.post(
        f"/api/v1/browser/sessions/{sid}/control",
        json={"action": "type", "element_id": node["id"], "text": password},
    )
    typed.raise_for_status()
    assert password not in typed.text
    assert (
        db.execute(
            "SELECT count(*) AS n FROM agent.checkpoints WHERE state::text LIKE %s",
            ("%" + password + "%",),
        ).fetchone()["n"]
        == 0
    )
    view = client.get(f"/api/v1/browser/sessions/{sid}").json()
    saved = client.post(
        f"/api/v1/browser/sessions/{sid}/control",
        json={
            "action": "remember",
            "profile_revision": view.get("profile_revision", 0),
        },
    )
    saved.raise_for_status()
    stale = client.post(
        f"/api/v1/browser/sessions/{sid}/control",
        json={"action": "remember", "profile_revision": 0},
    )
    assert stale.status_code == 409
    profile = client.get("/api/v1/browser/accounts").json()["items"][0]
    cipher = db.execute(
        "SELECT cipher FROM tools.browser_profiles WHERE id=%s", (profile["id"],)
    ).fetchone()["cipher"]
    assert cipher.startswith("v1.") and password not in cipher
    db.execute(
        "UPDATE tools.browser_sessions SET runtime_id=%s WHERE id=%s",
        ("TEST_FIXTURE_LOST_INSTANCE", sid),
    )
    recovered = client.post(
        f"/api/v1/browser/sessions/{sid}/control", json={"action": "recover"}
    )
    recovered.raise_for_status()
    assert recovered.json()["status"] == "HUMAN"
    client.post(f"/api/v1/browser/sessions/{sid}/resume", json={}).raise_for_status()
    resumed = claim()
    assert resumed["id"] == run
    execute(resumed)
    assert state(db, run)["status"] == "WAITING_INPUT"
    item = session(client, run)
    action = next(
        a
        for a in client.get("/api/v1/actions").json()["items"]
        if a["id"] == item["action_id"]
    )
    client.post(
        f"/api/v1/actions/{action['id']}/revoke",
        json={"request_hash": action["request_hash"]},
    ).raise_for_status()
    assert session(client, run)["status"] == "HUMAN"
    client.post(f"/api/v1/browser/sessions/{sid}/close", json={}).raise_for_status()
    assert state(db, run)["status"] == "CANCELLED"
    client.post(
        f"/api/v1/browser/accounts/{profile['id']}/revoke", json={}
    ).raise_for_status()
    assert (
        db.execute(
            "SELECT cipher FROM tools.browser_profiles WHERE id=%s", (profile["id"],)
        ).fetchone()["cipher"]
        is None
    )

    cleanup_notifications(db, run)


def test_browser_uncertain_submission_does_not_resubmit(client, db):
    conv, run = create(client, "fixture:browser-unknown 发布演练")
    claimed = claim()
    assert claimed["id"] == run
    execute(claimed)
    item = session(client, run)
    action = next(
        a
        for a in client.get("/api/v1/actions").json()["items"]
        if a["id"] == item["action_id"]
    )
    client.post(
        f"/api/v1/actions/{action['id']}/approve",
        json={"request_hash": action["request_hash"]},
    ).raise_for_status()
    resumed = claim()
    assert resumed["id"] == run
    execute(resumed)
    assert state(db, run)["status"] == "WAITING_INPUT"
    assert session(client, run)["status"] == "UNKNOWN"
    outcome = client.post(f"/api/v1/actions/{action['id']}/reconcile", json={})
    outcome.raise_for_status()
    assert outcome.json()["state"] == "UNKNOWN" and not outcome.json()["resubmitted"]
    assert (
        db.execute(
            "SELECT count(*) AS n FROM tools.effects WHERE effect_key=%s",
            ("action:" + action["id"],),
        ).fetchone()["n"]
        == 1
    )
    client.post(
        f"/api/v1/browser/sessions/{item['id']}/close", json={}
    ).raise_for_status()

    cleanup_notifications(db, run)
