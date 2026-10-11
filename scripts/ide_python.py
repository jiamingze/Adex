"""PyCharm entry point with scoped local configuration and port handoff."""

import os
import sys
import runpy
from dev import service_env
from ide import handoff

if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) == 2 else ""
    if name not in ("agent", "tools"):
        raise SystemExit("Expected agent or tools")
    environment = service_env(name)
    os.environ.clear()
    os.environ.update(environment)
    handoff(name)
    sys.argv = [
        "uvicorn",
        f"adex_{name}.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8105" if name == "agent" else "8107",
        "--no-access-log",
    ]
    runpy.run_module("uvicorn", run_name="__main__")
