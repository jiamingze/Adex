from uuid import uuid4
import pytest
from fastapi import HTTPException
from adex_tools.computer.contracts import ComputerAction
from adex_tools.computer.service import ComputerService
from adex_tools.computer.runner import MacRunner


def test_computer_grant_is_owner_and_app_bound(monkeypatch):
    owner = uuid4()
    monkeypatch.setenv("ADEX_COMPUTER_ENABLED", "true")
    monkeypatch.setenv("ADEX_COMPUTER_OWNER_ID", str(owner))
    monkeypatch.setenv("ADEX_COMPUTER_APPS", "计算器=com.apple.calculator,终端=com.apple.Terminal")
    service = ComputerService(None)
    assert service.grant(owner, "计算器") == "com.apple.calculator"
    for user, app in [(uuid4(), "计算器"), (owner, "邮件"), (owner, "终端")]:
        with pytest.raises(HTTPException):
            service.grant(user, app)


def test_closed_native_contract_rejects_code_coordinates_and_unknown_fields():
    for body in [
        {"action": "shell", "element_id": "0", "text": "id"},
        {"action": "press", "element_id": "0", "x": 100},
    ]:
        with pytest.raises(ValueError):
            ComputerAction.model_validate(body)


async def test_fixture_never_activates_on_real_db(monkeypatch):
    monkeypatch.setenv("ADEX_COMPUTER_TEST_FIXTURE", "true")
    monkeypatch.setenv("ADEX_DB_URL", "postgresql://localhost/adex_dev")
    monkeypatch.setenv("ADEX_COMPUTER_RUNNER", "/nonexistent/adex")
    with pytest.raises(HTTPException) as error:
        await MacRunner().call({"command": "status"})
    assert error.value.status_code == 503


def test_chrome_alias_and_preflight_reject_unknown_app(monkeypatch):
    owner = uuid4()
    monkeypatch.setenv("ADEX_COMPUTER_ENABLED", "true")
    monkeypatch.setenv("ADEX_COMPUTER_OWNER_ID", str(owner))
    monkeypatch.setenv("ADEX_COMPUTER_APPS", "Chrome=com.google.Chrome,谷歌浏览器=com.google.Chrome")
    service = ComputerService(None)
    assert service.grant(owner, "Chrome") == service.grant(owner, "谷歌浏览器")
    with pytest.raises(HTTPException):
        service.grant(owner, "Safari")


def test_search_contract_is_bounded_and_not_an_arbitrary_command():
    from adex_tools.computer.contracts import ComputerObservation

    body = dict(run_id=uuid4(), epoch=1, attempt_id=uuid4(), app_name="Chrome", search_query="ChatGPT")
    assert ComputerObservation(**body).search_query == "ChatGPT"
    for extra in ({"url": "file:///etc/passwd"}, {"search_query": "x" * 501}, {"search_query": ""}):
        with pytest.raises(ValueError):
            ComputerObservation(**{**body, **extra})


def test_whole_mac_policy_is_explicit_and_still_owner_bound(monkeypatch):
    owner = uuid4()
    monkeypatch.setenv("ADEX_COMPUTER_ENABLED", "true")
    monkeypatch.setenv("ADEX_COMPUTER_OWNER_ID", str(owner))
    monkeypatch.setenv("ADEX_COMPUTER_APP_POLICY", "all_installed")
    service = ComputerService(None)
    assert service.grant(owner, "Safari") == "Safari"
    with pytest.raises(HTTPException):
        service.grant(uuid4(), "Safari")


async def test_native_search_still_requires_run_authorization_before_dispatch(monkeypatch):
    owner = uuid4()
    monkeypatch.setenv("ADEX_COMPUTER_ENABLED", "true")
    monkeypatch.setenv("ADEX_COMPUTER_OWNER_ID", str(owner))
    monkeypatch.setenv("ADEX_COMPUTER_APPS", "计算器=com.apple.calculator")
    class Runner:
        async def call(self, body):
            assert body["command"] == "resolve"
            return {"bundle_id": "com.apple.calculator"}
    class Service(ComputerService):
        async def authorize(self, *args): raise HTTPException(403, "COMPUTER_RUN_REQUIRED")
    class Core:
        async def query(self, *args): pass
    with pytest.raises(HTTPException) as error:
        await Service(Core(), Runner()).observe(owner, {"app_name": "计算器", "search_query": "CET版"})
    assert error.value.detail == "COMPUTER_RUN_REQUIRED"


async def test_navigation_rejects_private_addresses_before_runner(monkeypatch):
    from adex_tools.computer.service import ComputerService
    class Service(ComputerService):
        async def resolve(self,*args):return 'com.google.Chrome'
    service=Service(None)
    for url in ('http://example.com','https://localhost/','https://127.0.0.1/','https://user:pass@example.com/'):
        with pytest.raises(HTTPException) as error:
            await service.observe('owner',{'app_name':'Chrome','navigate_url':url})
        assert error.value.detail=='COMPUTER_PUBLIC_HTTPS_REQUIRED'


async def test_confirm_requires_current_control_capability(monkeypatch):
    class Service(ComputerService):
        async def resolve(self, *args): return "fixture"
        async def authorize(self, *args): return {"origin_conversation_id": "conversation"}
    class Core:
        async def query(self, *args, **kwargs):
            return {"bundle_id": "fixture", "snapshot": {"nodes": [{"id": "0", "actions": ["AXPress"]}]}}
    body = {"app_name": "fixture", "run_id": uuid4(), "observation_id": uuid4(), "step": {"action": "confirm", "element_id": "0", "text": ""}}
    with pytest.raises(HTTPException) as error:
        await Service(Core()).step(uuid4(), body)
    assert error.value.detail == "COMPUTER_CONTROL_NOT_ALLOWED"
