"""Emit narrowly attached AppArmor userns rules for ephemeral Ubuntu GitHub CI only.

Load the emitted file with apparmor_parser; never disable the global userns guard
or Chromium's sandbox. See Chromium's apparmor-userns-restrictions.md.
"""

import os
from pathlib import Path
import re
import sys


def profile(cache):
    cache = cache.resolve()
    browsers = []
    for name in ("chrome", "headless_shell"):
        for path in sorted(cache.glob(f"chromium*/chrome-linux/{name}")):
            resolved = path.resolve()
            # A cache symlink must not expand this permission to another executable.
            if not resolved.is_relative_to(cache) or not resolved.is_file():
                raise ValueError("CI browser executable escapes the Playwright cache")
            if not re.fullmatch(r"/[A-Za-z0-9_./-]+", str(resolved)):
                raise ValueError("Unexpected CI browser path")
            browsers.append(resolved)
    if not browsers:
        raise ValueError("Install Playwright Chromium before generating its CI profile")
    result = ["abi <abi/4.0>,", "include <tunables/global>", ""]
    for index, path in enumerate(browsers):
        result += [
            f'profile adex-ci-chromium-{index} "{path}" flags=(unconfined) {{',
            "  userns,",
            "}",
        ]
    return "\n".join(result) + "\n"


if __name__ == "__main__":
    if sys.platform != "linux" or os.environ.get("GITHUB_ACTIONS") != "true":
        raise SystemExit("Only for ephemeral Linux GitHub Actions runners")
    print(profile(Path.home() / ".cache/ms-playwright"), end="")
