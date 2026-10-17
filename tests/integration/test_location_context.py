# ruff: noqa: F401, F811 -- imported isolated-stack fixtures
"""Synthetic location only; no device permission or physical fix is claimed."""

from datetime import datetime, timezone
from uuid import uuid4
import os
import httpx
from test_reliability import client, db, wait


def test_location_is_turn_scoped_cleared_and_bound_to_retries(client, db):
    conv = client.post(
        "/api/v1/conversations", json={"title": "TEST_FIXTURE location"}
    ).json()["id"]
    path = f"/api/v1/conversations/{conv}/messages"
    position = {
        "source": "device",
        "label": "TEST_FIXTURE 上海市徐汇区",
        "latitude": 31.23456,
        "longitude": 121.47891,
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    body = {
        "client_message_id": str(uuid4()),
        "content": "附近有什么五星级酒店",
        "client_location": position,
    }
    response = client.post(path, json=body)
    response.raise_for_status()
    turn = response.json()["message_id"]
    wait(
        lambda: db.execute(
            "SELECT * FROM app.turns WHERE id=%s AND status='COMPLETED'", (turn,)
        ).fetchone(),
        40,
    )
    row = db.execute(
        "SELECT client_location,location_hash FROM app.turns WHERE id=%s", (turn,)
    ).fetchone()
    assert row["client_location"] is None and row["location_hash"]
    plan = db.execute(
        "SELECT messages FROM agent.interactive_plans WHERE invocation_key=%s",
        ("chat:" + turn,),
    ).fetchone()
    assert "徐汇区" in str(plan["messages"])
    assert "31.23" not in str(plan["messages"]) and "121.48" not in str(
        plan["messages"]
    )
    assert client.post(path, json=body).json()["message_id"] == turn
    changed = {
        **body,
        "client_location": {**position, "label": "TEST_FIXTURE other city"},
    }
    assert client.post(path, json=changed).status_code == 409
    assert "client_location" not in str(client.get(path).json())
    with httpx.Client(
        base_url=os.environ["ADEX_TEST_URL"], trust_env=False
    ) as outsider:
        auth = outsider.post(
            "/api/v1/auth/register",
            json={"username": "location-" + str(uuid4())[:8], "password": "fixture"},
        )
        auth.raise_for_status()
        outsider.headers["Authorization"] = "Bearer " + auth.json()["token"]
        assert outsider.get(path).status_code in (403, 404)


def test_invalid_location_cannot_create_a_turn(client, db):
    conv = client.post(
        "/api/v1/conversations", json={"title": "TEST_FIXTURE invalid location"}
    ).json()["id"]
    response = client.post(
        f"/api/v1/conversations/{conv}/messages",
        json={
            "client_message_id": str(uuid4()),
            "content": "明天天气",
            "client_location": {
                "source": "device",
                "label": "",
                "latitude": 999,
                "longitude": 1,
                "observed_at": datetime.now(timezone.utc).isoformat(),
            },
        },
    )
    assert response.status_code == 400
    assert (
        db.execute(
            "SELECT count(*) AS n FROM app.turns WHERE conversation_id=%s", (conv,)
        ).fetchone()["n"]
        == 0
    )
