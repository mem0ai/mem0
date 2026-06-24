import io
import os
import tempfile
import zipfile

os.environ.setdefault("MEM0_DIR", os.path.join(tempfile.gettempdir(), "mem0-test"))
os.environ.setdefault("MEM0_TELEMETRY", "false")
os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from fastapi import HTTPException

from app.routers import backup


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _open_zip(members: dict[str, bytes]) -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(_zip_bytes(members)), "r")


def test_validate_backup_zip_rejects_too_many_files(monkeypatch):
    monkeypatch.setattr(backup, "MAX_BACKUP_MEMBER_COUNT", 1)

    with _open_zip({"memories.json": b"{}", "memories.jsonl.gz": b""}) as zf:
        with pytest.raises(HTTPException) as exc:
            backup._validate_backup_zip(zf)

    assert exc.value.status_code == 400
    assert "too many files" in exc.value.detail


def test_validate_backup_zip_rejects_large_uncompressed_member(monkeypatch):
    monkeypatch.setattr(backup, "MAX_BACKUP_MEMBER_BYTES", 16)
    monkeypatch.setattr(backup, "MAX_BACKUP_COMPRESSION_RATIO", 1000)

    with _open_zip({"memories.json": b"{}" * 32}) as zf:
        with pytest.raises(HTTPException) as exc:
            backup._validate_backup_zip(zf)

    assert exc.value.status_code == 413
    assert "too large" in exc.value.detail


def test_validate_backup_zip_rejects_high_compression_ratio(monkeypatch):
    monkeypatch.setattr(backup, "MAX_BACKUP_MEMBER_BYTES", 1024 * 1024)
    monkeypatch.setattr(backup, "MAX_BACKUP_COMPRESSION_RATIO", 10)

    with _open_zip({"memories.json": b"x" * 10_000}) as zf:
        with pytest.raises(HTTPException) as exc:
            backup._validate_backup_zip(zf)

    assert exc.value.status_code == 400
    assert "compression ratio" in exc.value.detail


def test_read_backup_member_accepts_normal_backup_member():
    with _open_zip({"memories.json": b'{"memories": []}'}) as zf:
        assert backup._read_backup_member(zf, "memories.json") == b'{"memories": []}'
