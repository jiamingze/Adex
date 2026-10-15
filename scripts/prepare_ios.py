"""Explicitly build the iOS bundle; dependency installation must not invoke this."""

import os
import subprocess
from pathlib import Path
from urllib.parse import urlparse


def resolve_endpoint(root, environ):
    endpoint = environ.get("ADEX_IOS_API_URL", "").strip()
    cached = root / ".local-data/public-url.txt"
    if not endpoint and cached.is_file():
        endpoint = cached.read_text().strip()
    if not endpoint:
        raise ValueError(
            "Set ADEX_IOS_API_URL=https://your-gateway.example before bundling iOS. "
            "Web/backend setup needs no tunnel or Xcode."
        )
    parsed = urlparse(endpoint)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise ValueError("ADEX_IOS_API_URL must be a public HTTPS origin")
    return endpoint.rstrip("/")


def main():
    root = Path(__file__).resolve().parents[1]
    try:
        endpoint = resolve_endpoint(root, os.environ)
    except ValueError as error:
        raise SystemExit(str(error)) from None
    env = os.environ.copy()
    env["VITE_ADEX_API_BASE"] = endpoint
    subprocess.run(
        ["pnpm", "--dir", "apps/web", "exec", "tsc", "--noEmit"],
        cwd=root,
        env=env,
        check=True,
    )
    subprocess.run(
        [
            "pnpm",
            "--dir",
            "apps/web",
            "exec",
            "vite",
            "build",
            "--outDir",
            "../ios/web-dist",
            "--emptyOutDir",
        ],
        cwd=root,
        env=env,
        check=True,
    )
    subprocess.run(["pnpm", "--dir", "apps/ios", "sync"], cwd=root, check=True)
    print("iOS bundled API:", endpoint)


if __name__ == "__main__":
    main()
