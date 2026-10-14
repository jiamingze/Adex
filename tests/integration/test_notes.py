"""Private notes: actual HTTP and isolated PostgreSQL, no personal DB writes."""

from uuid import uuid4
import httpx
from test_reliability import client


def test_notes_crud_cas_and_owner_isolation(client):
    body = {
        "id": str(uuid4()),
        "title": "会议记录",
        "content": "私有正文 <script>not executed</script>",
        "pinned": False,
    }
    created = client.post("/api/v1/notes", json=body)
    created.raise_for_status()
    note = created.json()
    path = "/api/v1/notes/" + note["id"]
    assert client.post("/api/v1/notes", json=body).json()["id"] == note["id"]
    assert client.get(path).json()["content"] == body["content"]
    listed = client.get("/api/v1/notes", params={"query": "会议记录"}).json()
    assert note["id"] in [n["id"] for n in listed["items"]]
    update = {**body, "revision": note["revision"], "pinned": True}
    saved = client.patch(path, json=update)
    saved.raise_for_status()
    assert saved.json()["revision"] == note["revision"] + 1
    assert client.patch(path, json=update).status_code == 409
    other = "notes-" + str(uuid4())[:12]
    with httpx.Client(base_url=str(client.base_url), trust_env=False) as registration:
        response = registration.post(
            "/api/v1/auth/register", json={"username": other, "password": "notes-test"}
        )
        response.raise_for_status()
    with httpx.Client(
        base_url=str(client.base_url),
        trust_env=False,
        headers={"Authorization": "Bearer " + response.json()["token"]},
    ) as stranger:
        assert stranger.get(path).status_code == 404
        assert stranger.patch(path, json=update).status_code == 404
        assert stranger.delete(path, params={"revision": 2}).status_code == 404
        assert stranger.post("/api/v1/notes", json=body).status_code == 404
    assert client.delete(path, params={"revision": 1}).status_code == 409
    assert (
        client.delete(path, params={"revision": saved.json()["revision"]}).status_code
        == 200
    )
    assert client.get(path).status_code == 404
    assert client.post("/api/v1/notes", json=body).status_code == 404


def test_notes_require_auth_and_validate_body(client):
    assert (
        client.post(
            "/api/v1/notes",
            json={
                "id": str(uuid4()),
                "title": "ok",
                "content": "x" * 100001,
                "pinned": False,
            },
        ).status_code
        == 413
    )
    assert (
        client.post(
            "/api/v1/notes",
            json={"id": str(uuid4()), "title": "ok", "content": "", "pinned": "true"},
        ).status_code
        == 400
    )
    with httpx.Client(base_url=str(client.base_url), trust_env=False) as anonymous:
        assert anonymous.get("/api/v1/notes").status_code == 401
