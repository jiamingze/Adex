"""Only synthetic loopback handlers: no account, model, browser or database execution."""

from contextlib import contextmanager
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
from threading import Thread

import httpx

FIXTURES = Path(__file__).resolve().parents[3] / "tests/fixtures"
sys.path.insert(0, str(FIXTURES))
import experience_server  # noqa: E402
import product_gallery_server  # noqa: E402
import browser_chat_server  # noqa: E402


@contextmanager
def serve(handler, root):
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(handler, directory=str(root)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False) as client:
            yield client
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_fixture_fault_cannot_split_headers_and_known_flags_still_work(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<body>TEST_FIXTURE</body>")
    monkeypatch.setattr(experience_server, "ROOT", tmp_path)
    with serve(experience_server.Handler, tmp_path) as client:
        response = client.get("/?fault=x%0D%0AX-Injected%3A%20yes")
        assert response.status_code == 200
        assert "set-cookie" not in response.headers
        assert "x-injected" not in response.headers
        response = client.get("/?fault=calendar-plan")
        assert response.headers["set-cookie"] == "fixture_fault=calendar-plan; Path=/; SameSite=Strict"


def test_browser_fixture_uses_canonical_stage_cookie(tmp_path, monkeypatch):
    monkeypatch.setitem(browser_chat_server.STAGES, "login", {})
    with serve(browser_chat_server.InlineHandler, tmp_path) as client:
        response = client.get("/demo/login")
        assert response.status_code == 302
        assert response.headers["set-cookie"] == "adex_browser_demo=login; Path=/; SameSite=Lax"
        response = client.get("/demo/login%0D%0AX-Injected%3Ayes")
        assert response.status_code == 404
        assert "set-cookie" not in response.headers


def test_gallery_serves_brand_image_instead_of_spa_html(tmp_path, monkeypatch):
    monkeypatch.setattr(product_gallery_server, "ROOT", tmp_path)
    monkeypatch.setattr(experience_server, "ROOT", tmp_path)
    (tmp_path / "brand").mkdir()
    image = b"TEST_FIXTURE_IMAGE_BYTES"
    (tmp_path / "brand/adex-icon.png").write_bytes(image)
    with serve(product_gallery_server.GalleryHandler, tmp_path) as client:
        response = client.get("/brand/adex-icon.png")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content == image
