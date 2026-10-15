"""A failing gate stays failing and retains actionable, bounded log context."""

from pathlib import Path
import subprocess
import sys

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/ci_run.py"


def test_exit_status_and_annotation_preserved():
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            sys.executable,
            "-c",
            "print('fixture failure 50%');raise SystemExit(7)",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 7
    assert "::error title=CI command failed::fixture failure 50%25%0A" in result.stdout


def test_success_has_no_failure_annotation():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), sys.executable, "-c", "print('fixture pass')"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0 and "::error" not in result.stdout
