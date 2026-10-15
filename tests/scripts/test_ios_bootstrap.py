"""Fresh checkout iOS configuration must fail clearly, without touching private files."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "prepare_ios", Path(__file__).resolve().parents[2] / "scripts/prepare_ios.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_fresh_checkout_reports_explicit_configuration_without_creating_files(tmp_path):
    with pytest.raises(ValueError, match="Set ADEX_IOS_API_URL"):
        module.resolve_endpoint(tmp_path, {})
    assert list(tmp_path.iterdir()) == []


def test_explicit_endpoint_wins_over_private_development_tunnel(tmp_path):
    cache = tmp_path / ".local-data/public-url.txt"
    cache.parent.mkdir()
    cache.write_text("https://old-tunnel.example")
    assert (
        module.resolve_endpoint(
            tmp_path, {"ADEX_IOS_API_URL": "https://gateway.example/"}
        )
        == "https://gateway.example"
    )
    assert module.resolve_endpoint(tmp_path, {}) == "https://old-tunnel.example"


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://example.com",
        "https://user:pass@example.com",
        "https://example.com/?token=x",
        "https://example.com/api",
    ],
)
def test_invalid_origins_rejected_before_build(tmp_path, endpoint):
    with pytest.raises(ValueError, match="HTTPS origin"):
        module.resolve_endpoint(tmp_path, {"ADEX_IOS_API_URL": endpoint})
