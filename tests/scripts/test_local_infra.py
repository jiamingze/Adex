"""PostgreSQL sockets must work as a non-root developer on Ubuntu and macOS."""

import importlib.util
from pathlib import Path
import shlex
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("local_infra", SCRIPTS / "local_infra.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_socket_is_private_project_owned_and_space_safe(tmp_path):
    base = tmp_path / "project with spaces"
    base.mkdir()
    args = shlex.split(module.postgres_options(base, "55432"))
    assert args == [
        "-h",
        "127.0.0.1",
        "-p",
        "55432",
        "-k",
        str(base / "postgres-socket"),
    ]
    assert (base / "postgres-socket").stat().st_mode & 0o777 == 0o700


def test_invalid_port_does_not_create_runtime_directory(tmp_path):
    with pytest.raises(ValueError):
        module.postgres_options(tmp_path, "55432; unexpected")
    assert not list(tmp_path.iterdir())
