"""Synthetic semantic proposal through real App/Agent/Automation, no external publish."""

from uuid import uuid4
from test_reliability import client, db, wait


def test_prefixless_chat_creates_browser_run_with_draft_context(client, db):
    conv = client.post(
        "/api/v1/conversations", json={"title": "TEST_FIXTURE browser follow-up"}
    ).json()["id"]
    client.post(
        f"/api/v1/conversations/{conv}/messages",
        json={
            "content": "TEST_FIXTURE 待审核文章正文",
            "client_message_id": str(uuid4()),
        },
    ).raise_for_status()
    wait(
        lambda: bool(
            db.execute(
                "SELECT id FROM app.messages WHERE conversation_id=%s AND role='assistant'",
                (conv,),
            ).fetchone()
        )
    )
    client.post(
        f"/api/v1/conversations/{conv}/messages",
        json={
            "content": "到小红书上发表",
            "client_message_id": str(uuid4()),
        },
    ).raise_for_status()

    def run():
        return db.execute(
            "SELECT kind,instruction FROM automation.runs WHERE origin_conversation_id=%s",
            (conv,),
        ).fetchone()

    wait(lambda: bool(run()))
    result = run()
    assert result["kind"] == "BROWSER"
    assert "TEST_FIXTURE 待审核文章正文" in result["instruction"]
    assert "不构成审批" in result["instruction"]
