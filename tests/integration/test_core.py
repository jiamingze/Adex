"""Real PostgreSQL concurrent and crash-window tests, never a mock DB."""

import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import httpx
import pytest

BASE = os.getenv("ADEX_TEST_URL", "http://127.0.0.1:8080")


@pytest.fixture(scope="module")
def client():
    c = httpx.Client(base_url=BASE, timeout=30, trust_env=False)
    r = c.post(
        "/api/v1/auth/login",
        json={
            "username": os.environ["ADEX_OWNER_USERNAME"],
            "password": os.environ["ADEX_OWNER_PASSWORD"],
        },
    )
    r.raise_for_status()
    c.headers["Authorization"] = "Bearer " + r.json()["token"]
    yield c
    c.close()


def test_message_idempotency(client):
    conv = client.post(
        "/api/v1/conversations", json={"title": "idempotency test"}
    ).json()["id"]
    body = {"client_message_id": str(uuid4()), "content": "hello test"}
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(
                lambda _: client.post(
                    f"/api/v1/conversations/{conv}/messages", json=body
                ),
                range(12),
            )
        )
    assert all(r.status_code == 200 for r in results)
    assert len({r.json()["message_id"] for r in results}) == 1
    conflict = client.post(
        f"/api/v1/conversations/{conv}/messages", json=body | {"content": "different"}
    )
    assert conflict.status_code == 409


def test_auth_and_ownership(client):
    assert httpx.get(BASE + "/api/v1/memories", trust_env=False).status_code == 401
    assert client.get(f"/api/v1/conversations/{uuid4()}/messages").status_code == 404


def test_memory_tombstone(client):
    fact = "fixture preference " + str(uuid4())
    r = client.post("/api/v1/memories", json={"content": fact})
    r.raise_for_status()
    mid = r.json()["id"]
    assert client.delete("/api/v1/memories/" + mid).status_code == 200
    assert client.post("/api/v1/memories", json={"content": fact}).status_code == 409
    assert all(m["id"] != mid for m in client.get("/api/v1/memories").json()["items"])


def test_travel_chat_answers_without_creating_a_background_task(client):
    import time
    from uuid import uuid4
    conv = client.post("/api/v1/conversations", json={"title": "interactive travel fixture"}).json()["id"]
    before = {r["id"] for r in client.get("/api/v1/tasks").json()["items"]}
    response = client.post(f"/api/v1/conversations/{conv}/messages", json={"client_message_id": str(uuid4()), "content": "帮我安排一个上海出发到普吉岛的四天三晚行程"})
    response.raise_for_status()
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        data = client.get(f"/api/v1/conversations/{conv}/messages").json()
        answers = [m for m in data["items"] if m["role"] == "assistant"]
        if answers:
            assert "已创建后台任务" not in answers[-1]["content"]
            assert not any(c["type"] == "task_status" for c in answers[-1].get("cards", []))
            assert {r["id"] for r in client.get("/api/v1/tasks").json()["items"]} == before
            return
        time.sleep(.2)
    raise AssertionError("Interactive travel reply did not finish")


def test_daily_schedule_from_chat_persists_once(client):
    import time
    conv=client.post('/api/v1/conversations',json={'title':'daily schedule chat'}).json()['id']
    body={'client_message_id':str(uuid4()),'content':'每天八点帮我整理网上最新关于spacx的信息'}
    assert client.post(f'/api/v1/conversations/{conv}/messages',json=body).status_code==200
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        data=client.get(f'/api/v1/conversations/{conv}/messages').json()
        answers=[m for m in data['items'] if m['role']=='assistant']
        if answers:break
        time.sleep(.2)
    assert answers and '已设置每天 08:00' in answers[0]['content']
    assert answers[0]['cards'][0]['type']=='automation_status'
    assert client.post(f'/api/v1/conversations/{conv}/messages',json=body).status_code==200
    schedules=client.get('/api/v1/automations').json()['items']
    owned=[s for s in schedules if s['origin_conversation_id']==conv]
    assert len(owned)==1 and owned[0]['kind']=='DAILY'
    assert owned[0]['timezone']=='Asia/Shanghai' and str(owned[0]['local_time']).startswith('08:00')
    assert 'SpaceX' in owned[0]['instruction']
