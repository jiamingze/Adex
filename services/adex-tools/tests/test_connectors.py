import base64
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from adex_tools.connectors.vault import CredentialVault
from adex_tools.connectors import google
from adex_tools.connectors.contracts import ActionDraft
from adex_tools.connectors.service import ConnectorService


def test_cipher_bound_to_resource_and_missing_key_blocks(monkeypatch):
    monkeypatch.delenv("ADEX_CONNECTOR_ENCRYPTION_KEY", raising=False)
    with pytest.raises(HTTPException) as exc:
        CredentialVault()
    assert exc.value.detail == "BLOCKED_EXTERNAL"
    monkeypatch.setenv("ADEX_CONNECTOR_ENCRYPTION_KEY", base64.b64encode(os.urandom(32)).decode())
    vault = CredentialVault()
    cipher = vault.seal({"refresh_token": "fixture"}, "owner:one")
    assert "fixture" not in cipher
    assert vault.open(cipher, "owner:one")["refresh_token"] == "fixture"
    with pytest.raises(HTTPException):
        vault.open(cipher, "owner:two")


def test_fixture_cannot_redirect_production(monkeypatch):
    monkeypatch.setenv("ADEX_CONNECTOR_TEST_FIXTURE", "true")
    monkeypatch.setenv("ADEX_DB_URL", "postgresql://localhost/adex_dev")
    assert google.endpoint("gmail").startswith("https://gmail.googleapis.com")


def test_action_headers_and_fields_validated():
    value = dict(
        connection_id=uuid4(),
        origin_conversation_id=uuid4(),
        kind="gmail.send",
        payload={"to": "a@example.com", "subject": "hello", "text": "body"},
    )
    assert ActionDraft(**value).kind == "gmail.send"
    with pytest.raises(ValidationError):
        ActionDraft(
            **{**value, "payload": {**value["payload"], "subject": "hello\r\nBcc: victim@example.com"}}
        )
    with pytest.raises(ValidationError):
        ActionDraft(**{**value, "payload": {**value["payload"], "start": "unexpected"}})


async def test_scopes_and_revoke_checked_before_io(monkeypatch):
    core = SimpleNamespace(
        query=AsyncMock(
            return_value={
                "id": uuid4(),
                "status": "ACTIVE",
                "service": "gmail",
                "scopes": [google.SCOPES[("gmail", "read")]],
            }
        )
    )
    service = ConnectorService(core)
    with pytest.raises(HTTPException) as exc:
        await service.credential(uuid4(), uuid4(), "send")
    assert exc.value.detail == "CONNECTOR_SCOPE_REQUIRED"
    core.query.return_value["status"] = "REVOKE_PENDING"
    with pytest.raises(HTTPException) as exc:
        await service.credential(uuid4(), uuid4(), "read")
    assert "REVOKED" in exc.value.detail


async def test_calendar_conflicts_use_provider_timezones(monkeypatch):
    events = [
        {
            "id": "one",
            "start": {"dateTime": "2026-10-12T10:00:00+08:00"},
            "end": {"dateTime": "2026-10-12T11:00:00+08:00"},
        },
        {
            "id": "two",
            "start": {"dateTime": "2026-10-12T02:30:00Z"},
            "end": {"dateTime": "2026-10-12T03:30:00Z"},
        },
    ]
    monkeypatch.setattr(
        google, "http", AsyncMock(return_value=SimpleNamespace(json=lambda: {"items": events}))
    )
    value = await google.calendar_query(
        "fixture", {"start": "2026-10-12T00:00:00Z", "end": "2026-10-13T00:00:00Z"}
    )
    assert value["conflicts"] == [{"first": "one", "second": "two"}]


async def test_stale_calendar_write_never_claims_success(monkeypatch):
    request = {
        "kind": "calendar.update",
        "payload": {"event_id": "fixture", "start": "2026-10-13T10:00:00Z", "end": "2026-10-13T11:00:00Z"},
        "before": {"etag": "old"},
    }
    http = AsyncMock(side_effect=HTTPException(409, "RESOURCE_CHANGED_REAPPROVAL_REQUIRED"))
    monkeypatch.setattr(google, "http", http)
    with pytest.raises(HTTPException) as exc:
        await google.write("fixture", uuid4(), request)
    assert exc.value.detail == "RESOURCE_CHANGED_REAPPROVAL_REQUIRED"
    assert http.await_count == 1


def test_connector_registry_cannot_load_arbitrary_provider():
    from adex_tools.connectors.adapters import adapter, GoogleAdapter

    assert isinstance(adapter("google"), GoogleAdapter)
    with pytest.raises(HTTPException):
        adapter("os.system")
