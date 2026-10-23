import os
import pytest
from fastapi import HTTPException
from adex_tools.computer.files import read_document, LIMIT


def test_document_read_is_root_bounded_and_denies_secrets_directories_and_symlink_escape(
    tmp_path, monkeypatch
):
    root = tmp_path / "Desktop"
    root.mkdir()
    monkeypatch.setenv("ADEX_COMPUTER_FILE_ROOTS", str(root))
    (root / "fixture.pdf").write_bytes(b"%PDF-1.4 TEST_FIXTURE")
    assert read_document("fixture.pdf") == ("fixture.pdf", b"%PDF-1.4 TEST_FIXTURE")
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"TEST_FIXTURE")
    (root / "escape.pdf").symlink_to(outside)
    (root / ".env").write_text("TEST_FIXTURE")
    (root / "folder").mkdir()
    for source in ("../outside.pdf", "escape.pdf", ".env", "folder"):
        with pytest.raises(HTTPException):
            read_document(source)
    with (root / "large.pdf").open("wb") as file:
        file.truncate(LIMIT + 1)
    with pytest.raises(HTTPException) as error:
        read_document("large.pdf")
    assert error.value.status_code == 413
    fifo = root / "fifo"
    os.mkfifo(fifo)
    with pytest.raises(HTTPException):
        read_document(str(fifo))


def test_file_return_is_disabled_without_an_explicit_root(monkeypatch):
    monkeypatch.delenv("ADEX_COMPUTER_FILE_ROOTS", raising=False)
    with pytest.raises(HTTPException) as error:
        read_document("fixture.pdf")
    assert error.value.detail == "COMPUTER_FILE_ROOT_NOT_GRANTED"
