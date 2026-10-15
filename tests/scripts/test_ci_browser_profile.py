"""CI permission attaches only to known, installed browser paths, never a wildcard."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "ci_chromium_profile",
    Path(__file__).resolve().parents[2] / "scripts/ci_chromium_profile.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_exact_browser_paths_only(tmp_path):
    browser = tmp_path / "chromium_headless_shell-1187/chrome-linux/headless_shell"
    browser.parent.mkdir(parents=True)
    browser.touch()
    result = module.profile(tmp_path)
    assert f'"{browser}"' in result
    assert "userns," in result and "*" not in result


def test_absent_install_or_escaping_symlink_rejected(tmp_path):
    cache = tmp_path / "cache"
    with pytest.raises(ValueError, match="Install Playwright"):
        module.profile(cache)
    outside = tmp_path / "outside"
    outside.touch()
    browser = cache / "chromium-1187/chrome-linux/chrome"
    browser.parent.mkdir(parents=True)
    browser.symlink_to(outside)
    with pytest.raises(ValueError, match="escapes"):
        module.profile(cache)
