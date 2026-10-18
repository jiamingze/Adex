import os
from uuid import uuid4
import httpx
import pytest


@pytest.fixture(scope="module")
def client():
    with httpx.Client(
        base_url=os.environ["ADEX_TEST_URL"], trust_env=False, timeout=30
    ) as c:
        r = c.post(
            "/api/v1/auth/login",
            json={
                "username": os.environ["ADEX_OWNER_USERNAME"],
                "password": os.environ["ADEX_OWNER_PASSWORD"],
            },
        )
        r.raise_for_status()
        c.headers["Authorization"] = "Bearer " + r.json()["token"]
        yield c


def test_private_files_ranges_and_idempotency(client):
    key = str(uuid4())

    def upload(data):
        return client.post(
            "/api/v1/files",
            files={"file": ("../../evil.html", data, "text/html")},
            headers={"Idempotency-Key": key},
        )

    r = upload(b"hello private file")
    r.raise_for_status()
    f = r.json()
    assert f["status"] == "READY" and f["mime_type"] == "application/octet-stream"
    assert upload(b"hello private file").json()["id"] == f["id"]
    assert upload(b"changed").status_code == 409
    path = f"/api/v1/files/{f['id']}/content"
    assert client.get(path).content == b"hello private file"
    ranged = client.get(path, headers={"Range": "bytes=6-12"})
    assert ranged.status_code == 206 and ranged.content == b"private"
    assert client.get(path, headers={"Range": "bytes=999-"}).status_code == 416
    assert (
        httpx.get(os.environ["ADEX_TEST_URL"] + path, trust_env=False).status_code
        == 401
    )
    artifact = client.post(
        "/api/v1/artifacts", json={"kind": "REPORT", "title": "test"}
    ).json()
    version = client.post(
        f"/api/v1/artifacts/{artifact['id']}/versions",
        json={
            "expected_revision": 0,
            "source": {"content": "report"},
            "file_id": f["id"],
        },
    )
    version.raise_for_status()
    assert client.delete(f"/api/v1/files/{f['id']}").status_code == 409
    assert (
        client.post(
            f"/api/v1/artifacts/{artifact['id']}/versions",
            json={"expected_revision": 0, "source": {"content": "stale"}},
        ).status_code
        == 409
    )


def test_background_task_submission(client):
    conv = client.post("/api/v1/conversations", json={"title": "Research test"}).json()[
        "id"
    ]
    key = str(uuid4())
    body = {
        "kind": "RESEARCH",
        "instruction": "Research test",
        "origin_conversation_id": conv,
    }
    r = client.post("/api/v1/tasks", json=body, headers={"Idempotency-Key": key})
    r.raise_for_status()
    assert (
        client.post(
            "/api/v1/tasks", json=body, headers={"Idempotency-Key": key}
        ).json()["id"]
        == r.json()["id"]
    )
    assert (
        client.post(
            "/api/v1/tasks",
            json=body | {"instruction": "different"},
            headers={"Idempotency-Key": key},
        ).status_code
        == 409
    )
    assert client.post(f"/api/v1/tasks/{r.json()['id']}/cancel").status_code == 200


def test_settings_and_conversation_lifecycle(client):
    response = client.get("/api/v1/settings")
    response.raise_for_status()
    assert isinstance(response.json()["settings"], dict)
    assert (
        client.patch("/api/v1/settings", json={"memory_enabled": False}).status_code
        == 200
    )
    assert (
        client.patch("/api/v1/settings", json={"memory_enabled": True}).status_code
        == 200
    )
    assert client.patch("/api/v1/settings", json={"email": "test@example.com"}).status_code == 200
    assert client.patch("/api/v1/settings", json={"email": ""}).status_code == 200
    assert client.get("/api/v1/settings").json()["settings"]["email"] == ""
    assert client.patch("/api/v1/settings", json={"email": None}).status_code == 400
    assert client.patch("/api/v1/settings", json={"email": "invalid"}).status_code == 400
    conv = client.post("/api/v1/conversations", json={"title": "temporary"}).json()[
        "id"
    ]
    assert (
        client.patch(f"/api/v1/conversations/{conv}", json={"title": "renamed"}).json()[
            "title"
        ]
        == "renamed"
    )
    assert client.post(f"/api/v1/conversations/{conv}/stop").status_code == 200
    assert client.delete(f"/api/v1/conversations/{conv}").status_code == 200
    assert client.get(f"/api/v1/conversations/{conv}/messages").status_code == 404


def test_calendar_approval_revocation(client):
    conv = client.post("/api/v1/conversations", json={"title": "Calendar test"}).json()[
        "id"
    ]
    response = client.post(
        "/api/v1/approvals",
        json={
            "title": "test event",
            "origin_conversation_id": conv,
            "start": "2026-12-10T10:00:00Z",
            "end": "2026-12-10T11:00:00Z",
        },
    )
    response.raise_for_status()
    approval = response.json()["id"]
    assert (
        client.post(f"/api/v1/approvals/{approval}/revoke").json()["state"] == "REVOKED"
    )
    assert client.post(f"/api/v1/approvals/{approval}/approve").status_code == 409


def test_monitor_cancel(client):
    conv = client.post(
        "/api/v1/conversations", json={"title": "monitor fixture"}
    ).json()["id"]
    response = client.post(
        "/api/v1/monitors",
        json={
            "query": "fixture " + str(uuid4()),
            "keyword": "test",
            "origin_conversation_id": conv,
        },
    )
    response.raise_for_status()
    monitor = response.json()["id"]
    assert client.delete(f"/api/v1/monitors/{monitor}").status_code == 200


def test_mock_media_effect_deduplication(client):
    from test_reliability import sign

    owner = client.get("/api/v1/me").json()["id"]
    body = {
        "kind": "AUDIO",
        "prompt": "deterministic licensed fixture",
        "request_key": str(uuid4()),
        "provider": "mock",
        "rights_confirmed": True,
    }
    with httpx.Client(
        base_url=os.environ["ADEX_TOOLS_URL"], trust_env=False, timeout=30
    ) as tools:
        headers = sign("agent", "tools", "creative:write", owner)
        first = tools.post("/internal/creative/generate", json=body, headers=headers)
        first.raise_for_status()
        second = tools.post("/internal/creative/generate", json=body, headers=headers)
        assert first.json() == second.json()
        assert (
            tools.post(
                "/internal/creative/generate",
                json=body | {"prompt": "changed"},
                headers=headers,
            ).status_code
            == 409
        )
        file = first.json()["artifact"]["file_id"]
        response = client.get(
            f"/api/v1/files/{file}/content", headers={"Range": "bytes=0-43"}
        )
        assert response.status_code == 206 and response.content[:4] == b"RIFF"


def test_edited_artifact_download_and_share_revocation(client):
    report = client.post(
        "/api/v1/artifacts", json={"kind": "REPORT", "title": "revision download"}
    ).json()
    v1 = client.post(
        f"/api/v1/artifacts/{report['id']}/versions",
        json={"expected_revision": 0, "source": {"content": "first"}},
    ).json()
    v2 = client.post(
        f"/api/v1/artifacts/{report['id']}/versions",
        json={"expected_revision": 1, "source": {"content": "second"}},
    ).json()
    assert v1["file_id"] != v2["file_id"]
    assert client.get(f"/api/v1/files/{v1['file_id']}/content").text == "first"
    assert client.get(f"/api/v1/files/{v2['file_id']}/content").text == "second"
    game = client.post(
        "/api/v1/artifacts", json={"kind": "GAME", "title": "sandbox"}
    ).json()
    source = '<html><script>document.body.innerText="fixture"</script></html>'
    client.post(
        f"/api/v1/artifacts/{game['id']}/versions",
        json={"expected_revision": 0, "source": {"content": source}},
    ).raise_for_status()
    path = client.post(f"/api/v1/artifacts/{game['id']}/share").json()["url"]
    preview = httpx.get(os.environ["ADEX_TEST_URL"] + path, trust_env=False)
    assert preview.status_code == 200
    assert "sandbox allow-scripts;" in preview.headers["content-security-policy"]
    assert "connect-src 'none'" in preview.headers["content-security-policy"]
    client.delete(f"/api/v1/artifacts/{game['id']}/share").raise_for_status()
    assert (
        httpx.get(os.environ["ADEX_TEST_URL"] + path, trust_env=False).status_code
        == 404
    )


def test_calendar_approval_creates_one_durable_run(client):
    conv = client.post(
        "/api/v1/conversations", json={"title": "approval durable run"}
    ).json()["id"]
    approval = client.post(
        "/api/v1/approvals",
        json={
            "title": "event",
            "start": "2026-12-10T10:00:00Z",
            "end": "2026-12-10T11:00:00Z",
            "origin_conversation_id": conv,
        },
    ).json()["id"]
    first = client.post(f"/api/v1/approvals/{approval}/approve")
    first.raise_for_status()
    second = client.post(f"/api/v1/approvals/{approval}/approve")
    second.raise_for_status()
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["kind"] == "CALENDAR"


def test_webhook_duplicate_order_and_unknown_media_reconcile(client):
    import hashlib, hmac, json, time, psycopg
    from test_reliability import sign

    owner = client.get("/api/v1/me").json()["id"]
    body = {
        "kind": "IMAGE",
        "prompt": "fixture",
        "request_key": str(uuid4()),
        "provider": "mock",
        "rights_confirmed": True,
    }
    with httpx.Client(
        base_url=os.environ["ADEX_TOOLS_URL"], trust_env=False, timeout=30
    ) as tools:
        headers = sign("agent", "tools", "creative:write", owner)
        first = tools.post("/internal/creative/generate", json=body, headers=headers)
        first.raise_for_status()
        with psycopg.connect(
            host=os.environ["ADEX_PG_HOST"],
            port=os.environ["ADEX_PG_PORT"],
            dbname=os.environ["ADEX_PG_DB"],
            user="adex_admin",
            password=os.environ["ADEX_ADMIN_PASSWORD"],
        ) as db:
            job = db.execute(
                "SELECT id FROM tools.media_jobs WHERE owner_id=%s AND request_key=%s",
                (owner, body["request_key"]),
            ).fetchone()[0]
            db.execute(
                "UPDATE tools.media_jobs SET status='UNKNOWN' WHERE id=%s", (job,)
            )
        recovered = tools.post(
            "/internal/creative/generate", json=body, headers=headers
        )
        recovered.raise_for_status()
        assert recovered.json() == first.json()

        def callback(version, status, event):
            raw = json.dumps(
                {
                    "job_id": str(job),
                    "event_id": event,
                    "version": version,
                    "status": status,
                }
            ).encode()
            timestamp = str(int(time.time()))
            signature = hmac.new(
                os.environ["ADEX_MEDIA_WEBHOOK_SECRET"].encode(),
                timestamp.encode() + b"." + raw,
                hashlib.sha256,
            ).hexdigest()
            return tools.post(
                "/internal/creative/webhook",
                content=raw,
                headers={"X-Timestamp": timestamp, "X-Signature": signature},
            )

        callback(3, "SUCCEEDED", "completed-fixture").raise_for_status()
        assert callback(3, "SUCCEEDED", "completed-fixture").json()["deduplicated"]
        callback(2, "RUNNING", "old-fixture").raise_for_status()
        assert (
            tools.post(
                "/internal/creative/webhook",
                content=b"{}",
                headers={"X-Timestamp": str(int(time.time())), "X-Signature": "bad"},
            ).status_code
            == 401
        )
        with psycopg.connect(
            host=os.environ["ADEX_PG_HOST"],
            port=os.environ["ADEX_PG_PORT"],
            dbname=os.environ["ADEX_PG_DB"],
            user="adex_admin",
            password=os.environ["ADEX_ADMIN_PASSWORD"],
        ) as db:
            status = db.execute(
                "SELECT provider_status FROM tools.media_jobs WHERE id=%s", (job,)
            ).fetchone()[0]
            assert status == "SUCCEEDED"


def test_diagram_source_edit_validates_arrows_and_rejects_active_content(client):
    diagram = client.post(
        "/api/v1/artifacts", json={"kind": "DIAGRAM", "title": "source validation"}
    ).json()["id"]
    response = client.post(
        f"/api/v1/artifacts/{diagram}/versions",
        json={
            "expected_revision": 0,
            "source": {"content": "flowchart TD\n A[App] --> B[Agent]"},
        },
    )
    response.raise_for_status()
    assert client.get(
        f"/api/v1/files/{response.json()['file_id']}/content"
    ).text.startswith("flowchart TD")
    fenced = client.post(
        f"/api/v1/artifacts/{diagram}/versions",
        json={
            "expected_revision": 1,
            "source": {"content": "说明\n```mermaid\nsequenceDiagram\n A-->>B: hello\n```\n结束"},
        },
    )
    fenced.raise_for_status()
    assert client.get(
        f"/api/v1/files/{fenced.json()['file_id']}/content"
    ).text == "sequenceDiagram\n A-->>B: hello\n"
    assert (
        client.post(
            f"/api/v1/artifacts/{diagram}/versions",
            json={
                "expected_revision": 2,
                "source": {"content": "flowchart TD\n A[<script>alert(1)</script>]"},
            },
        ).status_code
        == 400
    )


def test_mock_video_has_private_poster_and_range(client):
    from test_reliability import sign

    owner = client.get("/api/v1/me").json()["id"]
    body = {
        "kind": "VIDEO",
        "prompt": "fixture video",
        "request_key": str(uuid4()),
        "provider": "mock",
        "rights_confirmed": True,
    }
    r = httpx.post(
        os.environ["ADEX_TOOLS_URL"] + "/internal/creative/generate",
        json=body,
        headers=sign("agent", "tools", "creative:write", owner),
        trust_env=False,
        timeout=30,
    )
    r.raise_for_status()
    media = r.json()["artifact"]
    assert client.get(
        f"/api/v1/files/{media['poster_file_id']}/content"
    ).content.startswith(b"\x89PNG")
    assert (
        client.get(
            f"/api/v1/files/{media['file_id']}/content", headers={"Range": "bytes=0-31"}
        ).status_code
        == 206
    )


def test_media_effect_rejects_missing_run_authority(client):
    from test_reliability import sign

    owner = client.get("/api/v1/me").json()["id"]
    run = str(uuid4())
    body = {
        "kind": "IMAGE",
        "prompt": "should not dispatch",
        "request_key": run,
        "provider": "mock",
        "rights_confirmed": True,
        "run_id": run,
        "epoch": 1,
        "attempt_id": str(uuid4()),
    }
    r = httpx.post(
        os.environ["ADEX_TOOLS_URL"] + "/internal/creative/generate",
        json=body,
        headers=sign("agent", "tools", "creative:write", owner),
        trust_env=False,
        timeout=10,
    )
    assert r.status_code == 404


def test_diagram_exports_persist_and_reject_active_svg(client):
    diagram = client.post(
        "/api/v1/artifacts", json={"kind": "DIAGRAM", "title": "export persistence"}
    ).json()["id"]
    version = client.post(
        f"/api/v1/artifacts/{diagram}/versions",
        json={"expected_revision": 0, "source": {"content": "flowchart TD\n A --> B"}},
    ).json()["id"]

    def upload(data):
        response = client.post(
            "/api/v1/files",
            headers={"Idempotency-Key": str(uuid4())},
            files={"file": ("diagram.svg", data, "image/svg+xml")},
        )
        response.raise_for_status()
        return response.json()["id"]

    valid = upload(
        b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>'
    )
    client.post(
        f"/api/v1/artifacts/{diagram}/exports",
        json={"version_id": version, "file_id": valid, "format": "SVG"},
    ).raise_for_status()
    assert (
        client.get(f"/api/v1/artifacts/{diagram}/exports").json()["items"][0]["file_id"]
        == valid
    )
    assert client.delete(f"/api/v1/files/{valid}").status_code == 409
    malicious = upload(
        b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    )
    assert (
        client.post(
            f"/api/v1/artifacts/{diagram}/exports",
            json={"version_id": version, "file_id": malicious, "format": "SVG"},
        ).status_code
        == 400
    )


def test_task_cancellation_preserves_scoped_gateway_contract(client):
    conv = client.post('/api/v1/conversations', json={'title': 'task cancel authorization fixture'}).json()['id']
    task = client.post('/api/v1/tasks', json={'kind': 'RESEARCH', 'instruction': 'fixture:slow-stream', 'origin_conversation_id': conv}, headers={'Idempotency-Key': str(uuid4())})
    task.raise_for_status()
    run = task.json()
    cancelled = client.post(f"/api/v1/tasks/{run['id']}/cancel")
    cancelled.raise_for_status()
    assert cancelled.json()['status'] == 'CANCELLED'
    assert cancelled.json()['epoch'] > run['epoch']
