# ruff: noqa: F401, F811 -- imported pytest fixtures
"""Real isolated scheduling/outbox; APNs remains an explicitly labelled fixture."""

from datetime import datetime, timedelta, timezone
from test_reliability import client, db, wait
from test_connectors import execute, seed


def create(client, important=True, lead=604):
    due = datetime.now(timezone.utc) + timedelta(seconds=lead)
    body = {
        "title": "TEST_FIXTURE 提交项目材料",
        "description": "检查附件后提交",
        "important": important,
        "urgent": False,
        "due_at": due.isoformat(),
    }
    response = client.post("/api/v1/matrix", json=body)
    response.raise_for_status()
    return response.json()


def run_for(db, task):
    reminder = wait(
        lambda: db.execute(
            "SELECT * FROM app.matrix_reminders WHERE task_id=%s", (task["id"],)
        ).fetchone()
    )
    schedule = wait(
        lambda: db.execute(
            "SELECT * FROM automation.schedules WHERE idempotency_key=%s",
            ("matrix-reminder:" + str(reminder["id"]),),
        ).fetchone()
    )
    assert schedule["task_kind"] == "MATRIX_REMINDER"
    occurrence = wait(
        lambda: db.execute(
            "SELECT * FROM automation.occurrences WHERE schedule_id=%s",
            (schedule["id"],),
        ).fetchone()
    )
    expected = max(
        reminder["created_at"],
        datetime.fromisoformat(task["due_at"]) - timedelta(minutes=10),
    )
    assert abs((occurrence["scheduled_at"] - expected).total_seconds()) < 0.01
    run = db.execute(
        "SELECT * FROM automation.runs WHERE id=%s", (occurrence["run_id"],)
    ).fetchone()
    return reminder, dict(run, id=str(run["id"]))


def test_deadline_notification_and_idempotent_delivery(client, db):
    seed(pushes=[], fault="")
    client.put(
        "/api/v1/notification-preferences",
        json={
            "enabled": True,
            "push_enabled": True,
            "min_importance": 70,
            "quiet_start": None,
            "quiet_end": None,
            "timezone": "Asia/Shanghai",
        },
    ).raise_for_status()
    client.post(
        "/api/v1/push/devices", json={"token": "ab" * 32, "environment": "sandbox"}
    ).raise_for_status()
    task = create(client)
    reminder, run = run_for(db, task)
    execute(client, db, run)
    notification = wait(
        lambda: db.execute(
            "SELECT * FROM app.notifications WHERE matrix_reminder_id=%s",
            (reminder["id"],),
        ).fetchone()
    )
    assert task["title"] in notification["body"] and "截止时间" in notification["body"]
    assert notification["importance"] == 100
    wait(
        lambda: db.execute(
            "SELECT notification_id FROM app.push_deliveries WHERE notification_id=%s AND status='ACCEPTED'",
            (notification["id"],),
        ).fetchone()
    )
    assert str(notification["conversation_id"]) == str(run["origin_conversation_id"])
    assert str(notification["run_id"]) == run["id"]

    # Other integration modules legitimately leave model calls in this shared test DB.
    # The invariant is no LLM call for THIS deterministic reminder Run.
    def invocation_count():
        return db.execute(
            "SELECT count(*) AS n FROM agent.invocations WHERE invocation_key LIKE %s",
            ("run:" + run["id"] + ":%",),
        ).fetchone()["n"]

    assert invocation_count() == 0
    db.execute(
        "UPDATE automation.outbox SET delivered_at=NULL,next_attempt_at=now() WHERE run_id=%s",
        (run["id"],),
    )
    wait(
        lambda: db.execute(
            "SELECT delivered_at FROM automation.outbox WHERE run_id=%s", (run["id"],)
        ).fetchone()["delivered_at"]
    )
    assert (
        db.execute(
            "SELECT count(*) AS n FROM app.notifications WHERE matrix_reminder_id=%s",
            (reminder["id"],),
        ).fetchone()["n"]
        == 1
    )
    assert invocation_count() == 0


def test_completed_task_suppresses_already_scheduled_reminder(client, db):
    task = create(client)
    reminder, run = run_for(db, task)
    response = client.patch(
        "/api/v1/matrix/" + task["id"], json=dict(task, status="DONE")
    )
    response.raise_for_status()
    execute(client, db, run)
    assert not db.execute(
        "SELECT id FROM app.notifications WHERE matrix_reminder_id=%s",
        (reminder["id"],),
    ).fetchone()


def test_changed_deadline_and_deleted_item_suppress_old_reminders(client, db):
    task = create(client)
    reminder, run = run_for(db, task)
    new_due = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    response = client.patch(
        "/api/v1/matrix/" + task["id"], json=dict(task, due_at=new_due)
    )
    response.raise_for_status()
    assert (
        db.execute(
            "SELECT count(*) AS n FROM app.matrix_reminders WHERE task_id=%s",
            (task["id"],),
        ).fetchone()["n"]
        == 2
    )
    execute(client, db, run)
    assert not db.execute(
        "SELECT id FROM app.notifications WHERE matrix_reminder_id=%s",
        (reminder["id"],),
    ).fetchone()
    client.delete("/api/v1/matrix/" + task["id"]).raise_for_status()
    assert not db.execute(
        "SELECT id FROM app.matrix_reminders WHERE task_id=%s", (task["id"],)
    ).fetchone()
    ordinary = create(client, important=False)
    assert not db.execute(
        "SELECT id FROM app.matrix_reminders WHERE task_id=%s", (ordinary["id"],)
    ).fetchone()


def test_inside_ten_minutes_catches_up_without_model(client, db):
    task = create(client, lead=300)
    reminder, run = run_for(db, task)
    execute(client, db, run)
    assert db.execute(
        "SELECT id FROM app.notifications WHERE matrix_reminder_id=%s",
        (reminder["id"],),
    ).fetchone()
