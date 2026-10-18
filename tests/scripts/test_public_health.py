"""A stale quick tunnel must never be reported as a healthy public gateway."""

import importlib.util
import io
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

spec = importlib.util.spec_from_file_location(
    'public_health', Path(__file__).resolve().parents[2] / 'scripts/public_health.py'
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize('status,body,expected', [
    (401, b'{"code":"UNAUTHENTICATED"}', True),
    (530, b'Origin DNS error', False),
    (401, b'<html>proxy login</html>', False),
    (401, b'[]', False),
])
def test_gateway_requires_app_response(monkeypatch, status, body, expected):
    def request(*args, **kwargs):
        raise HTTPError('https://example.test', status, '', {}, io.BytesIO(body))
    monkeypatch.setattr(module, 'urlopen', request)
    assert module.gateway_ready('https://example.test') is expected


def test_network_failure_is_unhealthy(monkeypatch):
    def request(*args, **kwargs):
        raise URLError('tunnel not found')
    monkeypatch.setattr(module, 'urlopen', request)
    assert not module.gateway_ready('https://example.test')
