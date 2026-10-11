"""Opt-in real Docker gateway test; uses only synthetic HTML and no business credentials."""

import asyncio
import os
import signal
import subprocess
import shutil
import sys
import time
from pathlib import Path
import httpx
from config import load, ROOT

cfg = load()
source = ROOT / "services/adex-tools/src/adex_tools"
from adex_tools.code_runner import check_game

runtime = ROOT / ".local-data/gateway-runtime"
runtime.mkdir(exist_ok=True)
shutil.copyfile(source / "code_runner.py", runtime / "code_runner.py")
shutil.copyfile(ROOT / "runners/gateway/server.py", runtime / "server.py")

child_env = {
    key: value
    for key, value in cfg.items()
    if key
    in (
        "PATH",
        "HOME",
        "TMPDIR",
        "LANG",
        "DOCKER_CONFIG",
        "DOCKER_HOST",
        "ADEX_RUNNER_KEY",
    )
}
child_env.update(
    PYTHONPATH=str(runtime),
    ADEX_CODE_RUNNER_MODE="docker",
    ADEX_RUNNER_PORT="18120",
    ADEX_CODE_RUNNER_TEMP_ROOT=str(ROOT / ".local-data/runner-tmp"),
)
with (ROOT / ".local-data/gateway-test.log").open("w") as log:
    child = subprocess.Popen(
        [sys.executable, str(runtime / "server.py")],
        env=child_env,
        stdout=log,
        stderr=log,
        start_new_session=True,
    )
    try:
        for _ in range(50):
            if child.poll() is not None:
                raise RuntimeError("Gateway exited; see gateway-test.log")
            try:
                if (
                    httpx.get(
                        "http://127.0.0.1:18120/health/live", trust_env=False
                    ).status_code
                    == 200
                ):
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.1)
        assert (
            httpx.post(
                "http://127.0.0.1:18120/internal/check",
                json={"source": "<p>fixture</p>"},
                trust_env=False,
            ).status_code
            == 401
        )
        os.environ.update(
            ADEX_CODE_RUNNER_MODE="gateway",
            ADEX_CODE_RUNNER_URL="http://127.0.0.1:18120",
            ADEX_RUNNER_KEY=cfg["ADEX_RUNNER_KEY"],
        )
        result = asyncio.run(
            check_game("<html><body><canvas></canvas><p>fixture</p></body></html>")
        )
        assert result["status"] == "PASS" and result["has_canvas"]
        try:
            asyncio.run(check_game("<script>while(true){}</script>"))
        except httpx.HTTPStatusError as exc:
            assert exc.response.status_code == 503
        else:
            raise AssertionError("CPU loop did not terminate")
        print("Signed Runner gateway auth / render / timeout PASS")
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=5)
