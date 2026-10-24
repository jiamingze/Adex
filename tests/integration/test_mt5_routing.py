"""Isolated chat stack; real model/terminal reads are separately opt-in, never orders."""

from uuid import uuid4
import os
import pytest
from test_reliability import client, db, wait


@pytest.mark.parametrize("query", ["帮我下单xauusd", "用mt5下单安", "帮我下一单黄金的交易", "帮我做多黄金"], ids=["xauusd", "mt5_correction", "gold_trade", "gold_long"])
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
               ("网页助手 https://www.futunn.com/ 需要你登录后确认并继续。此前回复：本轮尚未取得任务操作的执行回执，请明确需要操作的事项及时间。", conv))
    body = {
        "client_message_id": str(uuid4()), "content": query,
    }
    real_language = os.getenv("ADEX_TEST_REAL_TRADING_LANGUAGE") == "1" and "黄金" in query
    if real_language:
        # Only text generation is enabled by this flag; terminal reads require
        # the independent ADEX_TEST_REAL_MT5_READ opt-in. There is no order sender.
        body["model"] = "qwen3.8-flash"
    sent = client.post(f"/api/v1/conversations/{conv}/messages", json=body)
    sent.raise_for_status()
    turn = sent.json()["message_id"]
    wait(lambda: db.execute("SELECT status FROM app.turns WHERE id=%s", (turn,)).fetchone()["status"]
         in ("COMPLETED", "FAILED"), timeout=90 if real_language else 20)
    assert db.execute("SELECT status FROM app.turns WHERE id=%s", (turn,)).fetchone()["status"] == "COMPLETED"
    assert not db.execute("SELECT id FROM automation.runs WHERE origin_conversation_id=%s", (conv,)).fetchone()
    frozen = db.execute("SELECT messages FROM agent.interactive_plans WHERE invocation_key=%s",
                        ("chat:" + turn,)).fetchone()["messages"]
    system = frozen[0]["content"]
    assert "trading.mt5-research@1.1.1" in system
    assert "不打开其他网站代替MT5下单" in system
    assert "本轮网页任务状态" not in system
    if os.getenv("ADEX_TEST_REAL_MT5_READ") == "1":
        assert "TERMINAL_READ_ONLY" in system
        import json
        import re
        analyses = db.execute("SELECT state,result FROM agent.invocations WHERE invocation_key LIKE %s",
                              ("chat:" + turn + ":mt5-advice:%",)).fetchall()
        structured = []
        for row in analyses:
            if row["state"] == "COMPLETED":
                try:
                    structured.append(json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", row["result"]["content"].strip())))
                except (ValueError, KeyError):
                    pass
        assert any(a.get("decision") in ("SETUP", "NO_SETUP", "INSUFFICIENT_DATA") for a in structured)
    reply = db.execute("SELECT content FROM app.messages WHERE conversation_id=%s AND role='assistant' ORDER BY seq DESC LIMIT 1", (conv,)).fetchone()["content"]
    assert "事项及时间" not in reply
    assert not any(text in reply for text in ("请补充", "做多还是做空", "需要明确以下关键参数"))
    if real_language:
        assert "MT5" in reply or "XAUUSD" in reply.upper()
        assert "本轮尚未取得可核验的执行回执" not in reply
        assert "BLOCKED_EXTERNAL" not in reply
        print("REAL_LANGUAGE_READ_ONLY", query, reply[:1200])


def test_continuous_trade_delegation_never_creates_gui_approval(client, db):
    conv = client.post("/api/v1/conversations", json={"title": "TEST_FIXTURE trade continuation"}).json()["id"]
    queries = ["帮我下一个黄金交易", "有没有挂单建议",
               "你跳ChatGPT的客户端把截图信息给他让他给你建议", "浏览器都行你决定"]
    for query in queries:
        body = {"client_message_id": str(uuid4()), "content": query}
        if os.getenv("ADEX_TEST_REAL_TRADING_LANGUAGE") == "1":
            body["model"] = "qwen3.8-flash"
        sent = client.post(f"/api/v1/conversations/{conv}/messages", json=body)
        sent.raise_for_status()
        turn = sent.json()["message_id"]
        wait(lambda: db.execute("SELECT status FROM app.turns WHERE id=%s", (turn,)).fetchone()["status"]
             in ("COMPLETED", "FAILED"), timeout=90)
        assert db.execute("SELECT status FROM app.turns WHERE id=%s", (turn,)).fetchone()["status"] == "COMPLETED"
        frozen = db.execute("SELECT messages FROM agent.interactive_plans WHERE invocation_key=%s",
                            ("chat:" + turn,)).fetchone()["messages"]
        assert "trading.mt5-research@1.1.1" in frozen[0]["content"]
        reply = db.execute("SELECT content FROM app.messages WHERE conversation_id=%s AND role='assistant' ORDER BY seq DESC LIMIT 1", (conv,)).fetchone()["content"]
        assert not any(text in reply for text in ("请确认", "请补充", "请选择", "请提供", "需要你确认"))
        assert not db.execute("SELECT id FROM automation.runs WHERE origin_conversation_id=%s", (conv,)).fetchone()
        assert not db.execute("SELECT id FROM tools.approvals WHERE request->>'origin_conversation_id'=%s", (conv,)).fetchone()
        if os.getenv("ADEX_TEST_REAL_MT5_READ") == "1":
            assert db.execute("SELECT invocation_key FROM agent.invocations WHERE invocation_key LIKE %s AND state='COMPLETED'",
                              ("chat:" + turn + ":mt5-advice:%",)).fetchone()
        print("CONTINUATION_RESEARCH_ONLY", query, reply[:500])
