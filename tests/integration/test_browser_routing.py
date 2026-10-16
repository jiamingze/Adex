"""Synthetic semantic proposal through real App/Agent/Automation, no external publish."""

import pytest
from uuid import uuid4
from test_reliability import client, db, wait


@pytest.mark.parametrize(
    "query,mode",
    [("到小红书上发表", "operate"), ("去京东看看这款手机多少钱", "lookup")],
)
def test_prefixless_chat_creates_browser_run_with_draft_context(
    client, db, query, mode
):
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
            "content": query,
            "client_message_id": str(uuid4()),
        },
    ).raise_for_status()

    def run():
        return db.execute(
            "SELECT id,kind,instruction,request FROM automation.runs WHERE origin_conversation_id=%s",
            (conv,),
        ).fetchone()

    wait(lambda: bool(run()))
    result = run()
    assert result["kind"] == "BROWSER"
    assert "TEST_FIXTURE 待审核文章正文" in result["instruction"]
    assert "不构成审批" in result["instruction"]
    assert result["request"]["params"]["browser_mode"] == mode
    if mode == "lookup":
        from test_browser_operator import execute, state
        from test_reliability import claim

        claimed = claim()
        assert str(claimed["id"]) == str(result["id"])
        execute(claimed)
        completed = state(db, result["id"])
        assert completed["status"] == "COMPLETED", completed
        checkpoint = db.execute(
            "SELECT state FROM agent.checkpoints WHERE id=%s",
            (completed["checkpoint_ref"],),
        ).fetchone()["state"]
        assert checkpoint["artifact"]["lookup_evidence"]["observed_at"]
        assert checkpoint["artifact"]["receipts"] == []
        assert "未创建订单" in completed["result"]
    else:
        client.post(f"/api/v1/tasks/{result['id']}/cancel", json={}).raise_for_status()


def test_multiple_browser_effect_approvals_share_run_but_connector_unique_remains(db):
    """Real PostgreSQL regression for the second-approval crash seen on Taobao."""
    import psycopg

    browser_run, connector_run, owner = uuid4(), uuid4(), uuid4()
    insert = "INSERT INTO tools.approvals(id,owner_id,request,request_hash,kind,run_id,state) VALUES(%s,%s,'{}',%s,%s,%s,'UNKNOWN')"
    with db.transaction():
        for index in range(2):
            db.execute(
                insert, (uuid4(), owner, str(index), "browser.request", browser_run)
            )
        assert (
            db.execute(
                "SELECT count(*) AS n FROM tools.approvals WHERE run_id=%s",
                (browser_run,),
            ).fetchone()["n"]
            == 2
        )
        db.execute(insert, (uuid4(), owner, "one", "calendar.create", connector_run))
        with pytest.raises(psycopg.errors.UniqueViolation):
            with db.transaction():
                db.execute(
                    insert, (uuid4(), owner, "two", "calendar.create", connector_run)
                )


def test_guest_chat_browser_access_keeps_owner_isolation_and_no_account_profiles(db):
    import httpx
    import os

    with (
        httpx.Client(base_url=os.environ["ADEX_TEST_URL"], trust_env=False) as guest,
        httpx.Client(base_url=os.environ["ADEX_TEST_URL"], trust_env=False) as other,
    ):
        guest.post("/api/v1/auth/guest").raise_for_status()
        other.post("/api/v1/auth/guest").raise_for_status()
        conv = guest.post(
            "/api/v1/conversations", json={"title": "TEST_FIXTURE guest lookup"}
        ).json()["id"]
        sent = guest.post(
            f"/api/v1/conversations/{conv}/messages",
            json={
                "content": "淘宝 iphone17 pro max 多少钱",
                "client_message_id": str(uuid4()),
            },
        )
        sent.raise_for_status()

        def current():
            return db.execute(
                "SELECT id FROM automation.runs WHERE origin_conversation_id=%s",
                (conv,),
            ).fetchone()

        wait(lambda: bool(current()))
        run = current()["id"]
        view = guest.get(f"/api/v1/browser/runs/{run}")
        view.raise_for_status()
        assert view.json()["is_guest"] is True
        assert other.get(f"/api/v1/browser/runs/{run}").status_code in (403, 404)
        assert guest.get("/api/v1/browser/accounts").status_code == 403
        assert guest.post("/api/v1/actions", json={}).status_code == 403
        assert (
            guest.post(
                f"/api/v1/browser/sessions/{uuid4()}/control",
                json={"action": "remember"},
            ).status_code
            == 403
        )
        db.execute("UPDATE automation.runs SET status='CANCELLED' WHERE id=%s", (run,))
