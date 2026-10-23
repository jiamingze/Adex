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
