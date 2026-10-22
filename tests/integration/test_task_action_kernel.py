"""Isolated real PG task commands with explicit deterministic model fixtures."""

from uuid import uuid4
from test_reliability import client, db, wait


def send(client, conv, content):
    path = f"/api/v1/conversations/{conv}/messages"
    before = {m["id"] for m in client.get(path).json()["items"]}
    body = {"client_message_id": str(uuid4()), "content": content}
    response = client.post(path, json=body)
    response.raise_for_status()
    answer = wait(
        lambda: next(
            (
                m
                for m in client.get(path).json()["items"]
                if m["role"] == "assistant" and m["id"] not in before
            ),
            None,
        ),
        timeout=35,
    )
    return answer, body


def test_typed_chat_create_update_and_replay(client, db):
    conv = client.post(
        "/api/v1/conversations", json={"title": "kernel fixture"}
    ).json()["id"]
    answer, body = send(client, conv, "TASK_KERNEL_CREATE_FIXTURE")
    assert "已设置" in answer["content"], answer
    rows = db.execute(
        "SELECT * FROM automation.schedules WHERE origin_conversation_id=%s", (conv,)
    ).fetchall()
    assert len(rows) == 1
    schedule = rows[0]
    client.post(f"/api/v1/conversations/{conv}/messages", json=body).raise_for_status()
    assert (
        db.execute(
            "SELECT count(*) n FROM automation.schedules WHERE origin_conversation_id=%s",
            (conv,),
        ).fetchone()["n"]
        == 1
    )
    answer, _ = send(client, conv, "TASK_KERNEL_UPDATE_FIXTURE")
    assert "已更新自动安排" in answer["content"], answer
    saved = db.execute(
        "SELECT * FROM automation.schedules WHERE id=%s", (schedule["id"],)
    ).fetchone()
    assert (
        saved["title"] == "TEST_FIXTURE updated"
        and saved["revision"] == schedule["revision"] + 1
    )
    assert saved["kind"] == "DAILY" and saved["local_time"].hour == 19
    replay = db.execute(
        "SELECT * FROM automation.schedule_mutations WHERE schedule_id=%s",
        (schedule["id"],),
    ).fetchone()
    assert replay and str(replay["response"]["id"]) == str(schedule["id"])
    assert (
        db.execute(
            "SELECT count(*) n FROM app.chat_task_actions WHERE state='SUCCEEDED' AND turn_id IN (SELECT id FROM app.turns WHERE conversation_id=%s)",
            (conv,),
        ).fetchone()["n"]
        == 2
    )
    client.delete(
        "/api/v1/automations/" + str(schedule["id"]),
        params={"revision": saved["revision"]},
    ).raise_for_status()


def test_schedule_command_replays_after_commit_instead_of_stale_revision(client, db):
    from test_reliability import sign
    import os, httpx

    conv = client.post(
        "/api/v1/conversations", json={"title": "command fixture"}
    ).json()["id"]
    _, _ = send(client, conv, "TASK_KERNEL_CREATE_FIXTURE")
    s = db.execute(
        "SELECT * FROM automation.schedules WHERE origin_conversation_id=%s", (conv,)
    ).fetchone()
    patch = {
        "revision": s["revision"],
        "title": "replayed",
        "command_key": str(uuid4()),
    }
    url = os.environ["ADEX_AUTOMATION_URL"] + "/internal/automations/" + str(s["id"])
    headers = sign("app", "automation", "schedule:write", s["owner_id"], s["id"])
    with httpx.Client(trust_env=False) as c:
        first = c.patch(url, json=patch, headers=headers)
        first.raise_for_status()
        replay = c.patch(url, json=patch, headers=headers)
        assert replay.status_code == 200 and replay.json() == first.json()
        assert (
            c.patch(
                url, json={**patch, "title": "different"}, headers=headers
            ).status_code
            == 409
        )
    client.delete(
        "/api/v1/automations/" + str(s["id"]),
        params={"revision": first.json()["revision"]},
    ).raise_for_status()


def test_todo_semantic_proposal_commits_real_record_and_update(client, db):
    conv = client.post(
        "/api/v1/conversations", json={"title": "todo kernel fixture"}
    ).json()["id"]
    answer, _ = send(client, conv, "TASK_KERNEL_TODO_FIXTURE")
    assert "已添加到你的待办" in answer["content"], answer
    old = db.execute(
        "SELECT * FROM app.matrix_tasks WHERE conversation_id=%s", (conv,)
    ).fetchone()
    assert old and old["important"] and not old["urgent"]
    answer, _ = send(client, conv, "TASK_KERNEL_TODO_UPDATE_FIXTURE")
    assert "已更新你的待办" in answer["content"], answer
    saved = db.execute(
        "SELECT * FROM app.matrix_tasks WHERE id=%s", (old["id"],)
    ).fetchone()
    assert saved["urgent"] and saved["revision"] == old["revision"] + 1


def test_complex_research_reuses_run_checkpoint_and_origin_result(client, db):
    from test_connectors import execute

    conv = client.post(
        "/api/v1/conversations", json={"title": "workflow fixture"}
    ).json()["id"]
    answer, _ = send(client, conv, "TASK_KERNEL_WORKFLOW_FIXTURE")
    assert "已开始分步研究" in answer["content"], answer
    assert answer["cards"][0]["data"]["kind"] == "RESEARCH"
    run = db.execute(
        "SELECT * FROM automation.runs WHERE origin_conversation_id=%s", (conv,)
    ).fetchone()
    assert run["request"]["params"]["agent_loop"] is True
    assert (
        run["request"]["params"]["original_request"] == "TASK_KERNEL_WORKFLOW_FIXTURE"
    )
    execute(client, db, {"id": str(run["id"])})
    checkpoints = db.execute(
        "SELECT state FROM agent.checkpoints WHERE run_id=%s", (run["id"],)
    ).fetchall()
    assert any(
        c["state"].get("phase") == "agent_loop" and c["state"].get("pending")
        for c in checkpoints
    )
    assert any(c["state"].get("phase") == "result" for c in checkpoints)
    wait(
        lambda: any(
            "分步研究结果" in m["content"]
            for m in client.get(f"/api/v1/conversations/{conv}/messages").json()[
                "items"
            ]
        )
    )
