# ruff: noqa: F401, F811 -- imported pytest fixtures
"""Isolated PG + four services; model/search/APNs fixtures are not real providers."""

import time
from uuid import uuid4
from test_reliability import client, db
from test_connectors import execute


def wait_for(callback, seconds=25):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = callback()
        if value:
            return value
        time.sleep(0.25)
    raise AssertionError("Timed out waiting for durable chat action")


def chat(client, text):
    conv = client.post(
        "/api/v1/conversations", json={"title": "TEST_FIXTURE productivity"}
    ).json()["id"]
    body = {"client_message_id": str(uuid4()), "content": text}
    path = f"/api/v1/conversations/{conv}/messages"
    response = client.post(path, json=body)
    response.raise_for_status()
    answer = wait_for(
        lambda: next(
            (m for m in client.get(path).json()["items"] if m["role"] == "assistant"),
            None,
        )
    )
    return conv, path, body, answer


def test_todo_chat_creates_owned_item_once(client, db):
    conv, path, body, answer = chat(client, "把准备项目周报加入我的待办")
    assert "已添加到你的待办" in answer["content"]
    tasks = [
        t
        for t in client.get("/api/v1/matrix").json()["items"]
        if t["conversation_id"] == conv
    ]
    assert len(tasks) == 1 and tasks[0]["important"] and not tasks[0]["urgent"]
    assert tasks[0]["status"] == "TODO"
    row = db.execute(
        "SELECT m.due_at,t.created_at FROM app.matrix_tasks m JOIN app.turns t ON t.id=m.source_turn_id WHERE m.id=%s",
        (tasks[0]["id"],),
    ).fetchone()
    assert (row["due_at"] - row["created_at"]).total_seconds() == 86400
    for label in (
        "**任务**",
        "**详情**",
        "**截止时间**",
        "**重要程度**：重要",
        "**紧急程度**：不紧急",
    ):
        assert label in answer["content"]
    assert tasks[0]["description"] in answer["content"]
    client.post(path, json=body).raise_for_status()
    assert (
        db.execute(
            "SELECT count(*) AS n FROM app.matrix_tasks WHERE conversation_id=%s",
            (conv,),
        ).fetchone()["n"]
        == 1
    )


def test_explicit_priority_overrides_default(client):
    conv, _, _, answer = chat(client, "把准备项目周报加入待办，不重要但紧急")
    task = next(
        t
        for t in client.get("/api/v1/matrix").json()["items"]
        if t["conversation_id"] == conv
    )
    assert task["important"] is False and task["urgent"] is True
    assert "**重要程度**：不重要" in answer["content"]
    update = dict(task, title="修改标题")
    update.pop("description")
    response = client.patch("/api/v1/matrix/" + task["id"], json=update)
    response.raise_for_status()
    assert response.json()["description"] == task["description"]


def test_one_minute_chat_executes_and_backfills(client, db):
    conv, path, body, answer = chat(client, "1分钟后给整理一条最新的新闻")
    assert "已设置" in answer["content"]
    schedule = next(
        s
        for s in client.get("/api/v1/automations").json()["items"]
        if s["origin_conversation_id"] == conv
    )
    assert schedule["kind"] == "ONCE"
    assert answer["cards"][0]["data"]["kind"] == "ONCE"
    client.post(path, json=body).raise_for_status()
    occurrence = wait_for(
        lambda: db.execute(
            "SELECT * FROM automation.occurrences WHERE schedule_id=%s",
            (schedule["id"],),
        ).fetchone(),
        80,
    )
    pending = db.execute(
        "SELECT * FROM automation.runs WHERE id=%s", (occurrence["run_id"],)
    ).fetchone()
    execute(client, db, dict(pending, id=str(pending["id"])))
    run = wait_for(
        lambda: db.execute(
            "SELECT * FROM automation.runs WHERE id=%s AND status='COMPLETED'",
            (occurrence["run_id"],),
        ).fetchone(),
        45,
    )
    assert str(run["origin_conversation_id"]) == conv
    notifications = wait_for(
        lambda: [
            n
            for n in client.get("/api/v1/notifications").json()["items"]
            if n["run_id"] == str(run["id"])
        ]
    )
    assert len(notifications) == 1
    messages = client.get(path).json()["items"]
    assert len([m for m in messages if m["role"] == "assistant"]) >= 2
    assert (
        db.execute(
            "SELECT count(*) AS n FROM automation.occurrences WHERE schedule_id=%s",
            (schedule["id"],),
        ).fetchone()["n"]
        == 1
    )
