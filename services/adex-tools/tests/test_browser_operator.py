import pytest
from pydantic import ValidationError
from adex_tools.browser.policy import BrowserStep, request_preview, request_digest, receipt_id


def test_narrow_actions_no_javascript_or_model_approval():
    for action in ("evaluate", "execute_js", "approve", "fetch", "shell"):
        with pytest.raises(ValidationError):
            BrowserStep(action=action)
    with pytest.raises(ValidationError):
        BrowserStep(action="click", approved=True)


def test_request_preview_redacts_secrets_but_binds_actual_bytes():
    raw = b'{"title":"demo","token":"secret","password":"secret"}'
    preview = request_preview("https://example.com/post?token=abc", "POST", raw, "application/json")
    assert "secret" not in str(preview) and "abc" not in str(preview)
    assert preview["fields"]["title"] == "demo"
    assert request_digest("https://example.com/post", "POST", raw) != request_digest(
        "https://example.com/post", "POST", raw + b" "
    )


def test_http_success_is_not_business_success():
    assert receipt_id({"status": "ok", "id": "auth-token"}) is None
    assert receipt_id({"success": False, "order_id": "fixture-order"}) is None
    assert receipt_id({"data": {"order_id": "fixture-order"}}) == "fixture-order"


async def test_real_chromium_fixture_holds_request_until_release():
    from adex_tools.browser.process import BrowserProcess

    actor = await BrowserProcess.start()
    try:
        value = await actor.call({"url": "https://example.com/fixture", "_test_fixture": True})
        assert value["provider"] == "TEST_FIXTURE"
        for name, text in [("标题", "TEST_FIXTURE title"), ("正文", "TEST_FIXTURE body")]:
            node = next(n for n in value["nodes"] if n.get("name") == name and n.get("id"))
            value = await actor.call(
                {
                    "action": "type",
                    "element_id": node["id"],
                    "text": text,
                    "observation_id": value["observation_id"],
                }
            )
        button = next(n for n in value["nodes"] if n.get("name") == "发布" and n.get("role") == "button")
        value = await actor.call(
            {"action": "click", "element_id": button["id"], "observation_id": value["observation_id"]}
        )
        assert value["pending"] and not value["receipt"]
        assert not any("TEST_FIXTURE_NOTE_001" in n.get("name", "") for n in value["nodes"])
        pending = value["pending"]
        value = await actor.call(
            {"action": "release", "request_id": pending["id"], "digest": pending["digest"], "allow": True}
        )
        assert value["receipt"]["business_verified"] is True
        assert value["receipt"]["test_fixture"] is True
        assert value["receipt"]["provider_receipt"] == "TEST_FIXTURE_NOTE_001"
    finally:
        await actor.close()


async def test_human_secure_input_is_not_in_agent_observation():
    from adex_tools.browser.process import BrowserProcess

    actor = await BrowserProcess.start()
    try:
        value = await actor.call({"url": "https://example.com/fixture", "_test_fixture": True})
        node = next(n for n in value["nodes"] if n.get("name") == "密码" and n.get("id"))
        assert node["protected"] is True
        from fastapi import HTTPException

        with pytest.raises(HTTPException):
            await actor.call(
                {
                    "action": "type",
                    "element_id": node["id"],
                    "text": "must-not-enter",
                    "observation_id": value["observation_id"],
                }
            )
        await actor.call({"action": "mode", "mode": "HUMAN"})
        value = await actor.call(
            {"action": "type", "element_id": node["id"], "text": "private-fixture-password", "human": True}
        )
        assert "private-fixture-password" not in str({k: v for k, v in value.items() if k != "_storage"})
        value = await actor.call({"action": "mode", "mode": "AGENT"})
        assert "private-fixture-password" not in str(value["nodes"])
    finally:
        await actor.close()


async def test_agent_handoff_alone_cannot_authorize_outbound_write():
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from adex_tools.browser.runner import Broker

    broker = Broker()
    broker.mode = "HUMAN"
    broker.test_fixture = False
    broker.pinned = {"example.com": "93.184.215.14"}
    broker.read_hosts = {"example.com"}
    req = SimpleNamespace(
        url="https://example.com/post",
        method="POST",
        resource_type="fetch",
        post_data_buffer=b"{}",
        headers={"content-type": "application/json"},
        is_navigation_request=lambda: False,
    )
    route = SimpleNamespace(request=req, continue_=AsyncMock(), abort=AsyncMock())
    task = asyncio.create_task(broker.intercept(route))
    for _ in range(10):
        if broker.pending:
            break
        await asyncio.sleep(0)
    assert broker.pending is not None
    assert not route.continue_.called
    broker.pending["future"].set_result(False)
    await task
    assert route.abort.called and not route.continue_.called


async def test_approval_snapshot_change_never_releases_request():
    from adex_tools.browser.runner import Broker

    broker = Broker()
    try:
        value = await broker.start({"url": "https://example.com/fixture", "_test_fixture": True})
        button = next(n for n in value["nodes"] if n.get("name") == "发布" and n.get("id"))
        value = await broker.operate(
            {"action": "click", "element_id": button["id"], "observation_id": value["observation_id"]}
        )
        pending = value["pending"]
        broker.pending["observation_id"] = "STALE_TEST_FIXTURE"
        with pytest.raises(ValueError, match="BROWSER_APPROVAL_SNAPSHOT_CHANGED"):
            await broker.operate(
                {"action": "validate_release", "request_id": pending["id"], "digest": pending["digest"]}
            )
        assert not broker.pending["future"].done()
        await broker.operate(
            {"action": "release", "request_id": pending["id"], "digest": pending["digest"], "allow": False}
        )
    finally:
        await broker.browser.close()
        await broker.playwright.stop()
        broker.proxy.close()


def test_opaque_or_malformed_body_is_not_automatically_reviewable():
    assert (
        request_preview("https://example.com/post", "POST", b"opaque", "application/octet-stream")[
            "reviewable"
        ]
        is False
    )
    assert (
        request_preview("https://example.com/post", "POST", b"{broken", "application/json")["reviewable"]
        is False
    )
    multipart = b'--demo\r\nContent-Disposition: form-data; name="title"\r\n\r\nTEST_FIXTURE\r\n--demo--\r\n'
    value = request_preview(
        "https://example.com/post", "POST", multipart, "multipart/form-data; boundary=demo"
    )
    assert value["reviewable"] is True
    assert value["fields"]["title"] == "TEST_FIXTURE"


def test_login_form_uses_real_page_fields_and_never_turns_publish_into_login():
    from adex_tools.browser.login import login_form

    nodes = [
        {"id": "1", "role": "textbox", "name": "手机号", "input_type": "tel"},
        {"id": "2", "role": "textbox", "name": "密码", "protected": True},
        {"id": "3", "role": "button", "name": "登录"},
    ]
    view = {"url": "https://example.com/login", "nodes": nodes, "observation_id": "v1"}
    form = login_form(view)
    assert form["origin"] == "https://example.com" and form["fields"][1]["secret"]
    assert (
        login_form({**view, "nodes": nodes[:2] + [{"id": "3", "role": "button", "name": "登录并发布"}]})
        is None
    )
    assert login_form({**view, "url": "http://example.com/login"}) is None


def test_publication_metadata_uses_frozen_title_and_never_invents_a_link():
    from adex_tools.browser.policy import publication_metadata

    before = {
        "gesture": "发布",
        "before": {"nodes": [{"role": "textbox", "name": "标题", "value": "TEST_FIXTURE Adex"}]},
    }
    result = publication_metadata(before, {"note_id": "NOTE_1"}, "https://example.com/editor", "NOTE_1")
    assert result["title"] == "TEST_FIXTURE Adex" and "permalink" not in result
    result = publication_metadata(
        before, {"note_url": "https://example.com/article/NOTE_1"}, "https://example.com/editor", "NOTE_1"
    )
    assert result["permalink_source"] == "provider_response" and result["permalink_verified"] is False
    assert "permalink" not in publication_metadata(
        before, {"note_url": "javascript:alert(1)"}, "https://example.com/editor", "NOTE_1"
    )


async def test_real_chromium_inline_login_origin_fence_and_password_nonpersistence():
    from adex_tools.browser.process import BrowserProcess
    from adex_tools.browser.login import login_form
    from fastapi import HTTPException

    actor = await BrowserProcess.start()
    try:
        value = await actor.call({"url": "https://example.com/fixture-login", "_test_fixture": True})
        await actor.call({"action": "mode", "mode": "HUMAN", "human": True})
        value = await actor.call({"action": "observe"})
        form = login_form(value)
        assert form and len(form["fields"]) == 2
        fields = [
            {"element_id": f["id"], "text": "fixture-only-password" if f["secret"] else "fixture-account"}
            for f in form["fields"]
        ]
        command = {
            "action": "secure_login",
            "human": True,
            "origin": form["origin"],
            "observation_id": form["observation_id"],
            "fields": fields,
            "submit_element_id": form["buttons"][0]["id"],
        }
        with pytest.raises(HTTPException):
            await actor.call({**command, "origin": "https://other.example.com"})
        value = await actor.call(command)
        assert value["login_submitted"] is True and not login_form(value)
        assert "fixture-only-password" not in str(value)
        assert any(c["name"] == "adex_fixture" for c in value["_storage"]["cookies"])
        assert not any(o.get("localStorage") for o in value["_storage"]["origins"])
    finally:
        await actor.close()


async def test_approved_write_does_not_follow_server_redirect_or_replay_body():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from adex_tools.browser.runner import Broker

    broker = Broker()
    broker.test_fixture = False
    response = SimpleNamespace(
        status=307,
        headers={"location": "https://example.com/second-write"},
        body=AsyncMock(return_value=b"{}"),
    )
    route = SimpleNamespace(
        request=SimpleNamespace(method="POST"), fetch=AsyncMock(return_value=response), fulfill=AsyncMock()
    )
    await broker.forward(route)
    route.fetch.assert_awaited_once_with(max_redirects=0, max_retries=0, timeout=10000)
    assert "location" not in route.fulfill.await_args.kwargs["headers"]
