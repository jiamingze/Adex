# ruff: noqa: F401, F811 -- imported pytest fixtures
"""Real isolated PG/API; fixture UI is never evidence of macOS execution."""

import json
import os
import subprocess
from uuid import uuid4
import httpx
import pytest
from test_reliability import client, db, sign, wait, claim, worker_env, ROOT


def execute_claimed(run, timeout=60):
    done = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            "services/adex-agent",
            "python",
            "scripts/execute_run.py",
            json.dumps(run),
        ],
        cwd=ROOT,
        env=worker_env(),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    assert done.returncode == 0, done.stderr[-1000:]


def test_computer_wait_approve_resume_and_effect_receipt(client, db):
    conv = client.post(
        "/api/v1/conversations", json={"title": "TEST_FIXTURE computer"}
    ).json()["id"]
    sent = client.post(
        f"/api/v1/conversations/{conv}/messages",
        json={"client_message_id": str(uuid4()), "content": "COMPUTER_START_FIXTURE"},
    )
    sent.raise_for_status()
    run = wait(
        lambda: db.execute(
            "SELECT * FROM automation.runs WHERE origin_conversation_id=%s AND kind='COMPUTER'",
            (conv,),
        ).fetchone()
    )
    first = claim()
    assert first["id"] == str(run["id"])
    execute_claimed(first)
    wait(
        lambda: db.execute(
            "SELECT status FROM automation.runs WHERE id=%s", (run["id"],)
        ).fetchone()["status"]
        == "WAITING_INPUT"
    )
    action = client.get("/api/v1/actions").json()["items"][0]
    assert (
        action["kind"] == "computer.step"
        and action["request"]["payload"]["control"] == "测试按钮"
    )
    response = client.post(
        "/api/v1/actions/" + action["id"] + "/approve",
        json={"request_hash": action["request_hash"]},
    )
    response.raise_for_status()
    second = claim()
    assert second["id"] == str(run["id"]) and second["epoch"] > first["epoch"]
    execute_claimed(second)
    state = db.execute(
        "SELECT status FROM automation.runs WHERE id=%s", (run["id"],)
    ).fetchone()
    assert state["status"] == "COMPLETED", state
    assert (
        db.execute(
            "SELECT state FROM tools.effects WHERE tool_id='computer.step' AND owner_id=%s",
            (run["owner_id"],),
        ).fetchone()["state"]
        == "SUCCEEDED"
    )
    wait(
        lambda: any(
            "已观察到操作回执" in m["content"]
            for m in client.get(f"/api/v1/conversations/{conv}/messages").json()[
                "items"
            ]
        )
    )


@pytest.mark.skipif(
    os.getenv("ADEX_TEST_REAL_COMPUTER") != "1",
    reason="Opt-in actual Mac UI; no personal documents",
)
def test_actual_calculator_with_isolated_effect_ledger(client, db):
    owner = client.get("/api/v1/me").json()["id"]
    conv = client.post(
        "/api/v1/conversations", json={"title": "TEST_FIXTURE real calculator"}
    ).json()["id"]
    response = client.post(
        "/api/v1/tasks",
        headers={"Idempotency-Key": str(uuid4())},
        json={
            "kind": "COMPUTER",
            "instruction": "验证计算器1+2",
            "origin_conversation_id": conv,
            "idempotency_key": str(uuid4()),
            "params": {"app_name": "计算器"},
        },
    )
    response.raise_for_status()
    rid = response.json()["id"]
    run = claim()
    assert run["id"] == rid
    execution = {k: run[k] for k in ("epoch", "attempt_id")}
    execution.update(run_id=rid, app_name="计算器")
    tools = os.environ["ADEX_TOOLS_URL"]
    headers = sign("agent", "tools", "computer:operate", owner, rid)
    with httpx.Client(trust_env=False, timeout=30) as http:

        def observe():
            result = http.post(
                tools + "/internal/computer/observe", headers=headers, json=execution
            )
            result.raise_for_status()
            return result.json()

        for index, identifier in enumerate(["AllClear", "One", "Add", "Two", "Equals"]):
            view = observe()
            node = next(
                (n for n in view["nodes"] if n.get("identifier") == identifier), None
            )
            assert node, [
                (n.get("identifier"), n.get("title"))
                for n in view["nodes"]
                if n.get("role") == "AXButton"
            ]
            step = {
                **execution,
                "observation_id": view["observation_id"],
                "command_key": str(index),
                "step": {"action": "press", "element_id": node["id"], "text": ""},
            }
            pending = http.post(
                tools + "/internal/computer/step", headers=headers, json=step
            )
            pending.raise_for_status()
            aid = pending.json()["action_id"]
            ah = sign("app", "tools", "approval:read", owner, aid)
            approval = http.get(tools + "/internal/actions/" + aid, headers=ah).json()
            approved = http.post(
                tools + "/internal/actions/" + aid + "/approve",
                headers=sign("app", "tools", "approval:write", owner, aid),
                json={"request_hash": approval["request_hash"]},
            )
            approved.raise_for_status()
            applied = http.post(
                tools + "/internal/computer/step",
                headers=headers,
                json={**step, "approval_id": aid},
            )
            assert applied.is_success, applied.text
            assert applied.json()["status"] == "COMMAND_APPLIED"
        final = observe()
        assert any(
            n.get("role") == "AXStaticText"
            and str(n.get("value") or n.get("title", "")).strip("\u200e\u200f") == "3"
            for n in final["nodes"]
        ), final["nodes"]
    client.post("/api/v1/tasks/" + rid + "/cancel").raise_for_status()


def test_computer_security_and_unknown_are_fail_closed(client, db):
    """Real PG/HTTP fault checks; fixture command receipt is not native evidence."""
    owner = client.get("/api/v1/me").json()["id"]
    conv = client.post(
        "/api/v1/conversations", json={"title": "TEST_FIXTURE computer faults"}
    ).json()["id"]
    created = client.post(
        "/api/v1/tasks",
        headers={"Idempotency-Key": str(uuid4())},
        json={
            "kind": "COMPUTER",
            "instruction": "TEST_FIXTURE",
            "origin_conversation_id": conv,
            "idempotency_key": str(uuid4()),
            "params": {"app_name": "测试应用"},
        },
    )
    created.raise_for_status()
    rid = created.json()["id"]
    run = claim()
    assert run["id"] == rid
    execution = {
        "run_id": rid,
        "epoch": run["epoch"],
        "attempt_id": run["attempt_id"],
        "app_name": "测试应用",
    }
    denied = client.post(
        "/api/v1/tasks",
        headers={"Idempotency-Key": str(uuid4())},
        json={
            "kind": "COMPUTER",
            "instruction": "TEST_FIXTURE denied app",
            "origin_conversation_id": conv,
            "params": {"app_name": "TEST_FIXTURE not granted"},
        },
    )
    assert denied.is_error
    assert (
        db.execute(
            "SELECT count(*) n FROM automation.runs WHERE origin_conversation_id=%s",
            (conv,),
        ).fetchone()["n"]
        == 1
    )
    base = os.environ["ADEX_TOOLS_URL"] + "/internal/computer/"
    headers = sign("agent", "tools", "computer:operate", owner, rid)
    with httpx.Client(trust_env=False, timeout=20) as http:

        def observe(body=execution, auth=headers):
            return http.post(base + "observe", headers=auth, json=body)

        assert observe({**execution, "epoch": run["epoch"] + 1}).is_error
        assert (
            observe(
                auth=sign("agent", "tools", "computer:operate", str(uuid4()), rid)
            ).status_code
            == 403
        )
        attempted_file = http.post(base + "export-file", headers=headers, json={**execution, "file_path": "fixture-document.pdf", "command_key": "unexpected"})
        assert attempted_file.status_code == 403 and "COMPUTER_FILE_NOT_REQUESTED" in attempted_file.text
        view = observe().json()
        step = {
            **execution,
            "observation_id": view["observation_id"],
            "command_key": "fault",
            "step": {"action": "press", "element_id": "0.0", "text": ""},
        }
        pending = http.post(base + "step", headers=headers, json=step)
        pending.raise_for_status()
        aid = pending.json()["action_id"]
        approval = db.execute(
            "SELECT * FROM tools.approvals WHERE id=%s", (aid,)
        ).fetchone()
        assert (
            http.post(
                base + "step",
                headers=headers,
                json={**step, "approval_id": str(uuid4())},
            ).status_code
            == 403
        )
        # Simulate parent death after the durable IN_FLIGHT boundary. Recovery must
        # preserve ambiguity and never dispatch the synthetic/native action again.
        db.execute("UPDATE tools.approvals SET state='APPROVED' WHERE id=%s", (aid,))
        db.execute(
            "INSERT INTO tools.effects(owner_id,effect_key,request_hash,tool_id,state) VALUES(%s,%s,%s,'computer.step','IN_FLIGHT')",
            (owner, "computer:" + rid + ":fault", approval["request_hash"]),
        )
        result = http.post(
            base + "step", headers=headers, json={**step, "approval_id": aid}
        )
        result.raise_for_status()
        assert result.json()["status"] == "UNKNOWN"
        assert (
            db.execute(
                "SELECT state FROM tools.approvals WHERE id=%s", (aid,)
            ).fetchone()["state"]
            == "UNKNOWN"
        )
        # Definitive native stale guards precede dispatch. They must be FAILED /
        # REVOKED and replay a readback instruction, never become UNKNOWN.
        stale_view = observe().json()
        stale_step = {**execution, "observation_id": stale_view["observation_id"], "command_key": "stale", "step": {"action": "press", "element_id": "0.0", "text": ""}}
        stale_action = http.post(base + "step", headers=headers, json=stale_step).json()["action_id"]
        db.execute("UPDATE tools.approvals SET state='APPROVED' WHERE id=%s", (stale_action,))
        db.execute("UPDATE tools.computer_observations SET snapshot=jsonb_set(snapshot,'{tree_hash}',to_jsonb('TEST_FIXTURE_STALE'::text)) WHERE id=%s", (stale_view["observation_id"],))
        for replay in range(2):
            stale = http.post(base + "step", headers=headers, json={**stale_step, "approval_id": stale_action})
            stale.raise_for_status()
            assert stale.json()["status"] == "REOBSERVE_REQUIRED"
        assert db.execute("SELECT state FROM tools.effects WHERE owner_id=%s AND effect_key=%s",(owner,"computer:"+rid+":stale")).fetchone()["state"] == "FAILED"
        assert db.execute("SELECT state FROM tools.approvals WHERE id=%s",(stale_action,)).fetchone()["state"] == "REVOKED"
        db.execute(
            "UPDATE tools.computer_observations SET created_at=clock_timestamp()-interval '11 minutes' WHERE id=%s",
            (view["observation_id"],),
        )
        assert http.post(base + "step", headers=headers, json=step).status_code == 409
        db.execute(
            "UPDATE tools.computer_host_mutex SET command_id=%s,lease_until=clock_timestamp()+interval '30 seconds'",
            (uuid4(),),
        )
        assert observe().status_code == 409
        db.execute("UPDATE tools.computer_host_mutex SET lease_until='-infinity'")
        client.delete("/api/v1/conversations/" + conv).raise_for_status()
        assert observe().is_error
    client.post("/api/v1/tasks/" + rid + "/cancel").raise_for_status()


@pytest.mark.skipif(
    os.getenv("ADEX_TEST_REAL_CHROME") != "1",
    reason="Opt-in real Chrome and Qwen search; isolated DB",
)
def test_actual_chrome_search_returns_to_original_conversation(client, db):
    conv = client.post(
        "/api/v1/conversations", json={"title": "TEST_FIXTURE real Chrome CET search"}
    ).json()["id"]
    response = client.post(
        f"/api/v1/conversations/{conv}/messages",
        json={
            "client_message_id": str(uuid4()),
            "content": "帮我打开Mac上的浏览器Chrome浏览器然后搜一下CET版结果给我",
        },
    )
    response.raise_for_status()
    run = wait(
        lambda: db.execute(
            "SELECT * FROM automation.runs WHERE origin_conversation_id=%s AND kind='COMPUTER'",
            (conv,),
        ).fetchone(),
        timeout=60,
    )
    first = claim()
    assert first["id"] == str(run["id"])
    execute_claimed(first)
    current = db.execute(
        "SELECT status,error_code FROM automation.runs WHERE id=%s", (run["id"],)
    ).fetchone()
    assert current["status"] == "COMPLETED", current

    def final_message():
        items = client.get(f"/api/v1/conversations/{conv}/messages").json()["items"]
        return next(
            (
                m
                for m in items
                if m["role"] == "assistant"
                and "https://" in m["content"]
                and "CET" in m["content"]
            ),
            None,
        )

    message = wait(final_message, timeout=30)
    assert "cet.neea" in message["content"].lower(), message["content"]
    # Assert structured source readback, not a golden wording from a live model.
    heading = message["content"].splitlines()[0]
    assert (
        heading.startswith("### “")
        and "CET版" in heading
        and heading.endswith("的搜索结果")
    ), heading
    assert "1. **[" in message["content"] and "桌面操作已停止" not in message["content"]
    (ROOT / ".local-data/chrome-e2e-result.md").write_text(message["content"])
    assert not db.execute(
        "SELECT id FROM tools.approvals WHERE kind='computer.step'"
    ).fetchone()


def test_computer_document_becomes_owned_chat_attachment_with_idempotent_readback(
    client, db
):
    conv = client.post(
        "/api/v1/conversations", json={"title": "TEST_FIXTURE document return"}
    ).json()["id"]
    response = client.post(
        f"/api/v1/conversations/{conv}/messages",
        json={"client_message_id": str(uuid4()), "content": "COMPUTER_FILE_FIXTURE"},
    )
    response.raise_for_status()
    run = wait(
        lambda: db.execute(
            "SELECT * FROM automation.runs WHERE origin_conversation_id=%s AND kind='COMPUTER'",
            (conv,),
        ).fetchone()
    )
    current = claim()
    assert current["id"] == str(run["id"])
    execute_claimed(current)

    def attachment():
        messages = client.get(f"/api/v1/conversations/{conv}/messages").json()["items"]
        return next(
            (
                card
                for message in messages
                for card in message.get("cards") or []
                if card["type"] == "file_attachment"
            ),
            None,
        )

    card = wait(attachment)
    fid = card["data"]["id"]
    downloaded = client.get("/api/v1/files/" + fid + "/content")
    downloaded.raise_for_status()
    assert b"TEST_FIXTURE document transfer" in downloaded.content
    assert db.execute(
        "SELECT owner_id,status FROM app.files WHERE id=%s", (fid,)
    ).fetchone() == {"owner_id": run["owner_id"], "status": "READY"}
    # Explicitly replay the idempotent App file port after a lost import reply.
    with httpx.Client(trust_env=False) as internal:
        replay = internal.post(
            os.environ["ADEX_APP_URL"] + "/internal/files",
            headers={
                **sign("tools", "app", "file:write", run["owner_id"]),
                "Idempotency-Key": "computer-file:" + str(run["id"]) + ":file:0",
            },
            files={
                "file": (
                    "fixture-document.pdf",
                    b"%PDF-1.4\nTEST_FIXTURE document transfer\n",
                    "application/pdf",
                )
            },
        )
        replay.raise_for_status()
        assert replay.json()["id"] == fid
    assert (
        db.execute(
            "SELECT count(*) n FROM app.files WHERE idempotency_key=%s",
            ("computer-file:" + str(run["id"]) + ":file:0",),
        ).fetchone()["n"]
        == 1
    )
    with httpx.Client(base_url=os.environ["ADEX_TEST_URL"], trust_env=False) as other:
        other.post(
            "/api/v1/auth/register",
            json={"username": "file_" + uuid4().hex[:10], "password": "fixture"},
        ).raise_for_status()
        assert other.get("/api/v1/files/" + fid + "/content").is_error


@pytest.mark.skipif(os.getenv('ADEX_TEST_REAL_CHROME') != '1',reason='Opt-in actual Chrome/Qwen; isolated DB')
def test_actual_chrome_youtube_navigation_returns_observed_video_without_approval(client,db):
    conv=client.post('/api/v1/conversations',json={'title':'TEST_FIXTURE requested YouTube navigation'}).json()['id']
    client.post(f'/api/v1/conversations/{conv}/messages',json={'client_message_id':str(uuid4()),'content':'打开我的Mac上的Chrome，直接访问YouTube首页，把首页推荐的第一个视频标题和链接发给我。不要用Google搜索YouTube。'}).raise_for_status()
    run=wait(lambda:db.execute("SELECT * FROM automation.runs WHERE origin_conversation_id=%s AND kind='COMPUTER'",(conv,)).fetchone(),timeout=60)
    active=claim();assert active['id']==str(run['id'])
    execute_claimed(active)
    current=db.execute('SELECT status,error_code FROM automation.runs WHERE id=%s',(run['id'],)).fetchone()
    if current['status']!='COMPLETED':
        debug=db.execute("SELECT result FROM agent.invocations WHERE invocation_key LIKE %s ORDER BY created_at",('%'+str(run['id'])+'%',)).fetchall()
        (ROOT/'.local-data/youtube-e2e-debug.json').write_text(json.dumps(debug,default=str,ensure_ascii=False))
    assert current['status']=='COMPLETED',current
    result=wait(lambda:next((m for m in client.get(f'/api/v1/conversations/{conv}/messages').json()['items'] if m['role']=='assistant' and 'youtube.com/watch?v=' in m['content']),None),timeout=30)
    assert '桌面操作受阻' not in result['content']
    snapshots=db.execute('SELECT snapshot FROM tools.computer_observations WHERE run_id=%s',(run['id'],)).fetchall()
    from urllib.parse import urlsplit
    homepage_seen=False
    observed_urls=set()
    for row in snapshots:
        for node in row['snapshot'].get('nodes',[]):
            url=node.get('url','')
            observed_urls.add(url)
            if node.get('role')=='AXWebArea' and urlsplit(url).hostname in ('youtube.com','www.youtube.com') and urlsplit(url).path in ('','/'):
                homepage_seen=True
    assert homepage_seen, 'Must actually observe the homepage, not search snippets or another page'
    assert any('youtube.com/watch?v=' in url and url in result['content'] for url in observed_urls)
    assert not db.execute("SELECT id FROM tools.approvals WHERE kind='computer.step'").fetchone()
    (ROOT/'.local-data/youtube-e2e-result.md').write_text(result['content'])


@pytest.mark.skipif(os.getenv('ADEX_TEST_REAL_CHROME') != '1',reason='Opt-in actual Chrome/Qwen site search')
def test_actual_youtube_site_search_does_not_request_typing_approval(client,db):
    conv=client.post('/api/v1/conversations',json={'title':'TEST_FIXTURE requested site search'}).json()['id']
    client.post(f'/api/v1/conversations/{conv}/messages',json={'client_message_id':str(uuid4()),'content':'帮我打开Mac的Chrome，在UTube也就是YouTube网站搜一下特别好玩的视频，给我三条实际搜索到的视频标题和链接。'}).raise_for_status()
    run=wait(lambda:db.execute("SELECT * FROM automation.runs WHERE origin_conversation_id=%s AND kind='COMPUTER'",(conv,)).fetchone(),timeout=60)
    active=claim();assert active['id']==str(run['id'])
    execute_claimed(active)
    assert not db.execute("SELECT id FROM tools.approvals WHERE kind='computer.step'").fetchone(),'Read-only site search must not prepare a control-write approval'
    current=db.execute('SELECT status,error_code FROM automation.runs WHERE id=%s',(run['id'],)).fetchone()
    assert current['status']=='COMPLETED',current
    observations=db.execute('SELECT snapshot FROM tools.computer_observations WHERE run_id=%s',(run['id'],)).fetchall()
    assert any('youtube.com/results?search_query=' in node.get('url','') for row in observations for node in row['snapshot'].get('nodes',[]) if node.get('role')=='AXWebArea')
    (ROOT/'.local-data/youtube-site-search-debug.json').write_text(json.dumps({'run':dict(db.execute('SELECT result FROM automation.runs WHERE id=%s',(run['id'],)).fetchone()),'observations':observations},default=str,ensure_ascii=False))
    result=wait(lambda:next((m for m in client.get(f'/api/v1/conversations/{conv}/messages').json()['items'] if m['role']=='assistant' and ('youtube.com/watch?v=' in m['content'] or 'youtube.com/shorts/' in m['content'])),None),timeout=30)
    observed={node.get('url','') for row in observations for node in row['snapshot'].get('nodes',[])}
    import re
    links=re.findall(r'https://www.youtube.com/(?:watch\?v=|shorts/)[^\s)\]<>]+',result['content'])
    assert links and all(url.rstrip('。，；') in observed for url in links)
    (ROOT/'.local-data/youtube-site-search-result.md').write_text(result['content'])


@pytest.mark.skipif(os.getenv("ADEX_TEST_REAL_CHROME") != "1", reason="Opt-in real installed Futu and Qwen; no simulated quotes")
def test_actual_futu_localized_name_and_login_boundary(client, db):
    binary = ROOT / ".local-data/computer-runner/AdexComputerRunner"
    for name in ("富途", "富途牛牛", "富途牛牛经典版"):
        response = subprocess.run([str(binary)], input=json.dumps({"command": "resolve", "bundle_id": name}), text=True, capture_output=True, timeout=20)
        assert json.loads(response.stdout).get("bundle_id") == "cn.futu.Niuniu"
    observation = subprocess.run([str(binary)], input=json.dumps({"bundle_id": "cn.futu.Niuniu"}), text=True, capture_output=True, timeout=20)
    view = json.loads(observation.stdout)
    if not any("登录" in (n.get("title", "") + n.get("value", "")) for n in view.get("nodes", [])):
        pytest.skip("Real Futu already signed in; login-boundary acceptance requires signed-out UI")
    conv = client.post("/api/v1/conversations", json={"title": "TEST_FIXTURE Futu login boundary"}).json()["id"]
    response = client.post("/api/v1/tasks", headers={"Idempotency-Key": str(uuid4())}, json={"kind": "COMPUTER", "instruction": "打开富途牛牛查看携程股票价格，未登录时告知需要在应用中登录，不要编造行情，不要操作交易", "origin_conversation_id": conv, "idempotency_key": str(uuid4()), "params": {"app_name": "富途牛牛"}})
    response.raise_for_status()
    run = claim()
    assert run["id"] == response.json()["id"]
    execute_claimed(run)
    result = db.execute("SELECT status,result,error_code FROM automation.runs WHERE id=%s", (run["id"],)).fetchone()
    assert result["status"] == "COMPLETED", result
    assert "登录" in result["result"], result
    assert not db.execute("SELECT id FROM tools.approvals WHERE request->>'computer_run_id'=%s", (run["id"],)).fetchall()


@pytest.mark.skipif(os.getenv("ADEX_TEST_REAL_CHROME") != "1", reason="Opt-in real signed-in Futu quote page and Qwen")
def test_actual_futu_current_quote_uses_visual_evidence(client, db):
    # Prove a real instrument change, not just successful extraction of the
    # instrument a human already opened before the test.
    binary = ROOT / ".local-data/computer-runner/AdexComputerRunner"
    preparation = subprocess.run([str(binary)], input=json.dumps({"bundle_id": "cn.futu.Niuniu", "search_query": "TCOM"}), text=True, capture_output=True, timeout=22)
    initial = json.loads(preparation.stdout)
    assert any(n.get("role") == "AXStaticText" and n.get("value", "").startswith("TCOM") for n in initial.get("nodes", [])), "Native toolbar lookup did not open TCOM"
    conv = client.post("/api/v1/conversations", json={"title": "TEST_FIXTURE actual Futu quote readback"}).json()["id"]
    response = client.post(f"/api/v1/conversations/{conv}/messages", json={"client_message_id": str(uuid4()), "content": "帮我打开Mac上的富途牛牛，搜索携程港股09961，读取搜索后默认行情页面的价格及可见BOLL指标数值，区分美股TCOM。不需要切换周期或点击其他按钮；基于实际可见指标给出两个条件走势情景，说明数据的时间边界和历史数据不足，不要操作交易。"})
    response.raise_for_status()
    pending = wait(lambda: db.execute("SELECT id FROM automation.runs WHERE origin_conversation_id=%s AND kind='COMPUTER'", (conv,)).fetchone(), timeout=60)
    run = claim()
    assert run["id"] == str(pending["id"])
    execute_claimed(run, timeout=120)
    result = db.execute("SELECT status,result,error_code FROM automation.runs WHERE id=%s", (run["id"],)).fetchone()
    if result["status"] == "WAITING_INPUT":
        pending_actions = db.execute("SELECT request FROM tools.approvals WHERE request->>'computer_run_id'=%s", (run["id"],)).fetchall()
        (ROOT / ".local-data/futu-live-pending.json").write_text(json.dumps(pending_actions, default=str, ensure_ascii=False))
    assert result["status"] == "COMPLETED", result
    (ROOT / ".local-data/futu-last-acceptance.json").write_text(json.dumps({"result": result, "plans": db.execute("SELECT result FROM agent.invocations ORDER BY created_at").fetchall()}, default=str, ensure_ascii=False))
    observations = db.execute("SELECT snapshot FROM tools.computer_observations WHERE run_id=%s", (run["id"],)).fetchall()
    evidence = "\n".join(row["snapshot"].get("visual_text", "") for row in observations)
    assert "09961" in evidence and "BOLL" in evidence, "Actual quote page / visual evidence unavailable"
    assert any(n.get("role") == "AXStaticText" and n.get("value") == "09961" for row in observations for n in row["snapshot"].get("nodes", [])), "Main instrument never switched from TCOM to 09961"
    assert "09961" in result["result"] and "BOLL" in result["result"], result
    readbacks = [row["snapshot"].get("primary_numeric_readback", {}) for row in observations]
    native_quotes = [q for q in readbacks if q.get("context") == "09961" and q.get("value")]
    assert native_quotes, "No spatially corroborated quote exists"
    from decimal import Decimal
    quote = native_quotes[-1]
    normalized = str(Decimal(quote["value"]).normalize())
    assert normalized in result["result"], "Returned quote omits the native price-axis value"

    wait(lambda: any(m["role"] == "assistant" and "09961" in m["content"] and "BOLL" in m["content"] for m in client.get(f"/api/v1/conversations/{conv}/messages").json()["items"]), timeout=30)
    import re
    numbers = re.findall(r"(?<![0-9])\d{3}\.\d{3}(?![0-9])", evidence)
    assert any(number in result["result"] for number in numbers), "No actual observed indicator/price returned"
    assert not db.execute("SELECT id FROM tools.approvals WHERE request->>'computer_run_id'=%s", (run["id"],)).fetchall()
