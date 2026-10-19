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
        await broker.egress.close()


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


async def test_unprompted_cross_origin_post_is_denied_not_sent_or_approved():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from adex_tools.browser.runner import Broker

    broker = Broker()
    broker.mode = "AGENT"
    broker.test_fixture = False
    broker.page = SimpleNamespace(url="https://example.com/")
    broker.admit = AsyncMock(return_value=True)
    request = SimpleNamespace(
        url="https://telemetry.example.net/collect", method="POST", resource_type="fetch"
    )
    route = SimpleNamespace(request=request, abort=AsyncMock(), continue_=AsyncMock())
    await broker.intercept(route)
    route.abort.assert_awaited_once()
    assert broker.pending is None
    route.continue_.assert_not_awaited()


async def test_transport_read_approval_does_not_cancel_actual_login_handoff():
    from types import SimpleNamespace
    from adex_tools.browser.service import BrowserService

    states = []

    async def query(sql, params, **kwargs):
        if sql.startswith("UPDATE browser_sessions"):
            states.append(params[3])
            return {"id": "session", "revision": 1}
        return None

    row = {
        "id": "session",
        "owner_id": "owner",
        "run_id": "run",
        "status": "AGENT",
        "snapshot": {},
        "storage_cipher": None,
        "pending_cipher": None,
        "action_id": None,
        "active_command": "command",
    }
    service = BrowserService(SimpleNamespace(query=query))
    result = await service.record(row, {"url": "https://example.com/login", "nodes": [], "mode": "HUMAN"})
    assert result["status"] == "HUMAN" and states == ["HUMAN"]
    row["status"] = "UNKNOWN"
    result = await service.record(row, {"url": "https://example.com/login", "nodes": [], "mode": "HUMAN"})
    assert result["status"] == "UNKNOWN"


async def test_visible_embedded_login_opens_real_form_only_on_bound_human_command():
    from adex_tools.browser.process import BrowserProcess
    from fastapi import HTTPException
    from adex_tools.browser.login import login_form

    actor = await BrowserProcess.start()
    try:
        value = await actor.call({"url": "https://example.com/fixture-login-frame", "_test_fixture": True})
        for _ in range(5):
            if value.get("embedded_login"):
                break
            value = await actor.call({"action": "observe", "screenshot": True})
        embedded = value["embedded_login"]
        assert embedded and embedded["origin"] == "https://example.com"
        assert "url" not in embedded
        with pytest.raises(HTTPException):
            await actor.call(
                {"action": "open_login_frame", "frame_id": embedded["id"], "origin": embedded["origin"]}
            )
        await actor.call({"action": "mode", "mode": "HUMAN"})
        with pytest.raises(HTTPException):
            await actor.call(
                {
                    "action": "open_login_frame",
                    "human": True,
                    "frame_id": embedded["id"],
                    "origin": "https://other.example",
                }
            )
        value = await actor.call(
            {
                "action": "open_login_frame",
                "human": True,
                "frame_id": embedded["id"],
                "origin": embedded["origin"],
            }
        )
        form = login_form(value)
        assert form and form["origin"] == "https://example.com"
        assert any(field["secret"] for field in form["fields"])
    finally:
        await actor.close()


async def test_read_host_redirect_is_transport_only_not_business_success():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from adex_tools.browser.runner import Broker

    for method, read_host, status, verified in [
        ("GET", "login.example.com", 302, True),
        ("GET", "login.example.com", 403, False),
        ("POST", None, 302, False),
        ("GET", None, 302, False),
    ]:
        broker = Broker()
        broker.test_fixture = True
        request = SimpleNamespace(method=method)
        broker.pending = {
            "request": request,
            "released": True,
            "id": "request",
            "digest": "hash",
            "transport_only": True,
            "grant_read_host": read_host,
        }
        response = SimpleNamespace(
            request=request,
            status=status,
            url="https://login.example.com/",
            headers={},
            json=AsyncMock(side_effect=ValueError()),
        )
        await broker.response(response)
        assert broker.last_receipt["verified"] is verified
        assert broker.last_receipt["business_verified"] is False


def test_inline_login_control_contract_and_read_recovery_are_narrow(monkeypatch):
    monkeypatch.setenv("ADEX_TOOLS_KEY", "local-unit-fixture-key-" * 3)
    monkeypatch.setenv("ADEX_DB_URL", "postgresql://localhost/adex_test_unit")
    from adex_tools.api.browser import Control
    from adex_tools.browser.policy import read_host_permission

    assert (
        Control(action="open_login_frame", frame_id="visible-frame", origin="https://example.com").frame_id
        == "visible-frame"
    )
    assert Control(action="recover_read").action == "recover_read"
    payload = {
        "method": "GET",
        "destination": "https://pages.example.com/",
        "additional_permission": {"scope": "READ_HOST_FOR_THIS_TASK", "host": "pages.example.com"},
    }
    assert read_host_permission(payload)
    assert not read_host_permission({**payload, "method": "POST"})
    assert not read_host_permission({**payload, "destination": "https://evil.example/"})
    assert not read_host_permission({**payload, "additional_permission": {"scope": "WRITE"}})


def test_network_restriction_is_not_a_login_form():
    from adex_tools.browser.login import access_block, login_form

    blocked = {
        "url": "https://example.com/error",
        "nodes": [
            {"role": "heading", "name": "安全限制"},
            {"role": "StaticText", "name": "IP存在风险，请切换可靠网络环境后重试"},
        ],
    }
    assert access_block(blocked)["code"] == "NETWORK_ACCESS_RESTRICTED"
    assert login_form(blocked) is None
    assert access_block({"nodes": [{"role": "StaticText", "name": "请登录后继续"}]}) is None
    assert access_block({"nodes": [{"role": "heading", "name": "如何解决IP风险"}]}) is None


async def test_handoff_prepares_observed_login_without_second_takeover_question():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from adex_tools.browser.service import BrowserService

    actor = SimpleNamespace(
        call=AsyncMock(
            side_effect=[
                {
                    "url": "https://example.com",
                    "mode": "HUMAN",
                    "nodes": [],
                    "embedded_login": {"id": "visible", "origin": "https://example.com"},
                },
                {
                    "url": "https://example.com/login",
                    "mode": "HUMAN",
                    "nodes": [
                        {"id": "account", "role": "textbox", "name": "手机号"},
                        {"id": "login", "role": "button", "name": "登录"},
                    ],
                },
            ]
        )
    )
    value = await BrowserService(SimpleNamespace()).login_handoff(actor)
    assert value["mode"] == "HUMAN"
    assert actor.call.await_args.args[0] == {
        "action": "open_login_frame",
        "prepare_only": True,
        "human": True,
        "frame_id": "visible",
        "origin": "https://example.com",
    }


async def test_chromium_inline_login_is_ready_without_takeover_button():
    """Actual Chromium, synthetic login only; never a real merchant credential."""
    from types import SimpleNamespace
    from adex_tools.browser.process import BrowserProcess
    from adex_tools.browser.service import BrowserService
    from adex_tools.browser.login import login_form
    import json

    actor = await BrowserProcess.start()
    try:
        await actor.call({"url": "https://example.com/fixture-login-frame", "_test_fixture": True})
        value = await BrowserService(SimpleNamespace()).login_handoff(actor)
        form = login_form(value)
        assert value["mode"] == "HUMAN" and form
        assert any(field["secret"] for field in form["fields"])
        secret = "TEST_FIXTURE_private_pass"
        result = await actor.call(
            {
                "action": "secure_login",
                "human": True,
                "origin": form["origin"],
                "observation_id": form["observation_id"],
                "submit_element_id": form["buttons"][0]["id"],
                "fields": [
                    {"element_id": field["id"], "text": secret if field["secret"] else "TEST_FIXTURE_account"}
                    for field in form["fields"]
                ],
            }
        )
        assert secret not in json.dumps(result)
        assert login_form(result) is None
    finally:
        await actor.close()


async def test_automatic_login_preparation_does_not_authorize_network_writes():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from adex_tools.browser.runner import Broker

    broker = Broker()
    broker.mode = "HUMAN"
    broker.embedded_login = {
        "id": "frame",
        "origin": "https://example.com",
        "url": "https://example.com/login",
    }
    broker.observe = AsyncMock(return_value={})
    broker.admit = AsyncMock(return_value=True)
    broker.page = SimpleNamespace(goto=AsyncMock())
    await broker.operate(
        {
            "action": "open_login_frame",
            "human": True,
            "prepare_only": True,
            "frame_id": "frame",
            "origin": "https://example.com",
        }
    )
    assert broker.human_authorized is False
    assert broker.human_until == 0


async def test_agent_can_submit_search_by_enter_but_not_secret_or_arbitrary_keys():
    from adex_tools.browser.process import BrowserProcess

    actor = await BrowserProcess.start()
    try:
        value = await actor.call({"url": "https://example.com/fixture", "_test_fixture": True})
        field = next(n for n in value["nodes"] if n.get("name") == "搜索商品" and n.get("id"))
        value = await actor.call(
            {
                "action": "type",
                "element_id": field["id"],
                "text": "TEST_FIXTURE phone",
                "observation_id": value["observation_id"],
            }
        )
        value = await actor.call(
            {
                "action": "key",
                "element_id": field["id"],
                "text": "Enter",
                "observation_id": value["observation_id"],
            }
        )
        assert any("TEST_FIXTURE商品结果" in n.get("name", "") for n in value["nodes"])
        with pytest.raises(Exception):
            await actor.call(
                {
                    "action": "key",
                    "element_id": field["id"],
                    "text": "Control+L",
                    "observation_id": value["observation_id"],
                }
            )
        protected = next(n for n in value["nodes"] if n.get("name") == "密码" and n.get("id"))
        with pytest.raises(Exception):
            await actor.call(
                {
                    "action": "key",
                    "element_id": protected["id"],
                    "text": "Enter",
                    "observation_id": value["observation_id"],
                }
            )
    finally:
        await actor.close()


async def test_search_control_survives_large_feed_snapshot():
    from adex_tools.browser.process import BrowserProcess

    actor = await BrowserProcess.start()
    try:
        value = await actor.call({"url": "https://example.com/fixture-feed", "_test_fixture": True})
        assert any(n.get("name") == "搜索商品" and n.get("id") for n in value["nodes"])
        assert len([n for n in value["nodes"] if n.get("role") == "StaticText"]) <= 100
    finally:
        await actor.close()


@pytest.mark.parametrize("url,method,critical,forwarded", [
    ("https://www.google.com/search?q=Adex", "GET", False, True),
    ("https://other.example.net/news", "GET", False, True),
    ("https://other.example.net/delete?id=1", "GET", False, False),
        ("https://other.example.net/?action=delete&id=1", "GET", False, False),
    ("https://other.example.net/search", "GET", True, False),
    ("https://other.example.net/publish", "POST", False, False),
])
async def test_public_navigation_is_automatic_without_granting_actions(url, method, critical, forwarded):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from adex_tools.browser.runner import Broker

    broker = Broker()
    broker.test_fixture = False
    broker.page = SimpleNamespace(url="https://example.com/")
    broker.read_hosts = {"example.com"}
    broker.admit = AsyncMock(return_value=True)
    broker.forward = AsyncMock()
    broker.gesture = "搜索"
    broker.critical = critical
    req = SimpleNamespace(url=url, method=method, resource_type="document",
        is_navigation_request=lambda: True, post_data_buffer=b"", headers={})
    route = SimpleNamespace(request=req, abort=AsyncMock())
    task = asyncio.create_task(broker.intercept(route))
    for _ in range(20):
        if task.done() or broker.pending:
            break
        await asyncio.sleep(0)
    assert bool(broker.pending) is (not forwarded)
    if broker.pending:
        broker.pending["future"].set_result(False)
    await task
    assert broker.forward.await_count == int(forwarded)


async def test_failed_public_dns_admission_never_prompts_or_forwards():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from adex_tools.browser.runner import Broker
    broker = Broker()
    broker.test_fixture = False
    broker.admit = AsyncMock(return_value=False)
    broker.forward = AsyncMock()
    route = SimpleNamespace(request=SimpleNamespace(url="https://127.0.0.1/", method="GET"), abort=AsyncMock())
    await broker.intercept(route)
    route.abort.assert_awaited_once()
    broker.forward.assert_not_awaited()
    assert broker.pending is None


async def test_google_background_log_is_dropped_without_approval():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from adex_tools.browser.runner import Broker
    broker = Broker()
    broker.test_fixture = False
    broker.page = SimpleNamespace(url="https://www.google.com/search?q=Adex")
    broker.gesture = "搜索"
    broker.admit = AsyncMock(return_value=True)
    broker.forward = AsyncMock()
    req = SimpleNamespace(url="https://play.google.com/log", method="POST", resource_type="fetch", is_navigation_request=lambda: False)
    route = SimpleNamespace(request=req, abort=AsyncMock())
    await broker.intercept(route)
    route.abort.assert_awaited_once()
    broker.forward.assert_not_awaited()
    assert broker.pending is None
