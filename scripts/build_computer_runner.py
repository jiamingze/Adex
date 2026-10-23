"""Build a stable local macOS helper; never edits macOS privacy permissions."""

import platform
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if platform.system() != "Darwin":
    raise SystemExit("macOS required")
output = ROOT / ".local-data/computer-runner/AdexComputerRunner"
output.parent.mkdir(parents=True, exist_ok=True)
subprocess.run(
    ["swiftc", str(ROOT / "runners/macos/ComputerRunner.swift"), "-o", str(output)],
    check=True,
)
subprocess.run(
    [
        "codesign",
        "--force",
        "--sign",
        "-",
        "--identifier",
        "io.adex.computer-runner",
        str(output),
    ],
    check=True,
)
output.chmod(0o700)
print("Built", output)
print(
    "Grant Accessibility to this helper in macOS System Settings when explicitly enabling it."
)
