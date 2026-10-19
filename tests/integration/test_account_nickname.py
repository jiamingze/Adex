"""Account profile changes use disposable isolated accounts, never the user's account."""

from uuid import uuid4
import httpx
from test_reliability import client


def test_nickname_persists_without_renaming_login_and_is_owner_scoped(client):
    other_before = client.get("/api/v1/me").json()
    username = "nick_" + uuid4().hex[:12]
    with httpx.Client(
        base_url=str(client.base_url), trust_env=False, timeout=15
    ) as account:
        account.post(
            "/api/v1/auth/register", json={"username": username, "password": "test"}
        ).raise_for_status()
        before = account.get("/api/v1/me").json()
        saved = account.patch("/api/v1/me", json={"nickname": "  星河 🌅  "})
        saved.raise_for_status()
        assert saved.json()["nickname"] == "星河 🌅"
        assert (
            saved.json()["username"] == username and saved.json()["id"] == before["id"]
        )
        assert client.get("/api/v1/me").json()["id"] != before["id"]
        assert (
            account.patch(
                "/api/v1/me",
                json={
                    "nickname": "bad",
                    "owner_id": client.get("/api/v1/me").json()["id"],
                },
            ).status_code
            == 400
        )
        assert client.get("/api/v1/me").json() == other_before
        account.post("/api/v1/auth/logout").raise_for_status()
        account.post(
            "/api/v1/auth/login", json={"username": username, "password": "test"}
        ).raise_for_status()
        assert account.get("/api/v1/me").json()["nickname"] == "星河 🌅"
        for invalid in [None, 123, "x" * 41, "a\nb"]:
            assert (
                account.patch("/api/v1/me", json={"nickname": invalid}).status_code
                == 400
            )
        assert (
            account.patch("/api/v1/me", json={"nickname": "🌅" * 40}).status_code == 200
        )
        assert (
            account.patch("/api/v1/me", json={"nickname": "  "}).json()["nickname"]
            == ""
        )
        assert account.get("/api/v1/me").json()["username"] == username
    with httpx.Client(base_url=str(client.base_url), trust_env=False) as guest:
        guest.post("/api/v1/auth/guest", json={}).raise_for_status()
        assert guest.patch("/api/v1/me", json={"nickname": "test"}).status_code == 403
