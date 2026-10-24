"""Real isolated chat stack, synthetic model; never touches an MT5 account."""

from uuid import uuid4
import pytest
from test_reliability import client, db, wait


@pytest.mark.parametrize("query", ["帮我下单xauusd", "用mt5下单安"])
def test_mt5_correction_freezes_native_skill_without_creating_browser_run(client, db, query):
    conv = client.post("/api/v1/conversations", json={"title": "TEST_FIXTURE MT5 route"}).json()["id"]
    first = client.post(f"/api/v1/conversations/{conv}/messages", json={
        "client_message_id": str(uuid4()), "content": "TEST_FIXTURE 对话背景",
    })
    first.raise_for_status()
    wait(lambda: db.execute(
        "SELECT status FROM app.turns WHERE id=%s", (first.json()["message_id"],)
    ).fetchone()["status"] == "COMPLETED")
    # Synthetic stale website history reproduces the user's correction; no user DB changes.
    db.execute("UPDATE app.messages SET content=%s WHERE conversation_id=%s AND role='assistant'",
               ("网页助手 https://www.futunn.com/ 需要你登录后确认并继续", conv))
    sent = client.post(f"/api/v1/conversations/{conv}/messages", json={
        "client_message_id": str(uuid4()), "content": query,
    })
    sent.raise_for_status()
    turn = sent.json()["message_id"]
    wait(lambda: db.execute("SELECT status FROM app.turns WHERE id=%s", (turn,)).fetchone()["status"]
         in ("COMPLETED", "FAILED"))
    assert db.execute("SELECT status FROM app.turns WHERE id=%s", (turn,)).fetchone()["status"] == "COMPLETED"
    assert not db.execute("SELECT id FROM automation.runs WHERE origin_conversation_id=%s", (conv,)).fetchone()
    frozen = db.execute("SELECT messages FROM agent.interactive_plans WHERE invocation_key=%s",
                        ("chat:" + turn,)).fetchone()["messages"]
    system = frozen[0]["content"]
    assert "trading.mt5-research@1.0.0" in system
    assert "不打开其他网站代替MT5下单" in system
    assert "本轮网页任务状态" not in system
