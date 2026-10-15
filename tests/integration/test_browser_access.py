"""Real scoped HTTP/isolated PG rejection tests; no external browser execution."""

import os
from uuid import uuid4
import httpx
from test_reliability import sign


def test_browser_endpoint_auth_scope_and_private_destinations():
    assert os.environ["ADEX_PG_DB"].startswith("adex_test_")
    base = os.environ["ADEX_TOOLS_URL"]
    url = base + "/internal/browser/read"
    with httpx.Client(trust_env=False) as client:
        assert client.post(url, json={"url": "https://example.com"}).status_code == 401
        bad_scope = sign("agent", "tools", "file:read", uuid4())
        assert (
            client.post(
                url, headers=bad_scope, json={"url": "https://example.com"}
            ).status_code
            == 403
        )
        headers = sign("agent", "tools", "search:read", uuid4())
        for destination in [
            "https://127.0.0.1/",
            "https://169.254.169.254/",
            "file:///etc/passwd",
        ]:
            response = client.post(url, headers=headers, json={"url": destination})
            assert response.status_code == 400, response.text
            assert "BROWSER_URL_NOT_ALLOWED" in response.text
        assert (
            client.post(
                url,
                headers=headers,
                json={"url": "https://example.com", "max_pages": 4},
            ).status_code
            == 422
        )
