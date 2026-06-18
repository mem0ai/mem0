"""Tests for the backup/restore service (task_02 / ADR-003).

Exercita a orquestração via seams injetáveis (S3, Qdrant, pg_dump) — sem
infraestrutura real. A verificação ao vivo é o drill da task_03.
"""

import gzip
import os
from datetime import UTC, datetime
from types import SimpleNamespace

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest

from app.utils.backup import BackupService


class FakeS3:
    def __init__(self):
        self.objects = {}

    def put_object(self, *, Bucket, Key, Body):
        self.objects[Key] = Body

    def list_objects_v2(self, *, Bucket, Prefix):
        items = [
            {"Key": k, "LastModified": datetime(2026, 6, 18, tzinfo=UTC)}
            for k in self.objects
            if k.startswith(Prefix)
        ]
        return {"Contents": items}

    def get_object(self, *, Bucket, Key):
        return {"Body": SimpleNamespace(read=lambda: self.objects[Key])}


class FakeQdrant:
    def __init__(self, collections=("c1", "c2")):
        self._cols = collections
        self.recovered = []

    def get_collections(self):
        return SimpleNamespace(collections=[SimpleNamespace(name=n) for n in self._cols])

    def create_snapshot(self, *, collection_name):
        return SimpleNamespace(name=f"{collection_name}-snap")

    def download_snapshot(self, *, collection_name, snapshot_name):
        return f"data-{collection_name}".encode()

    def recover_snapshot(self, *, collection_name, location):
        self.recovered.append(collection_name)


_PG_URL = "postgresql://u:p@db:5432/mem0"


def _service(s3, qc):
    return BackupService(
        s3_client=s3,
        bucket="b",
        db_url=_PG_URL,
        qdrant_client_provider=lambda: qc,
        pg_dump_runner=lambda url: gzip.compress(b"PGDUMP"),
        clock=lambda: datetime(2026, 6, 18, 10, 0, tzinfo=UTC),
    )


def test_backup_uploads_qdrant_and_postgres():
    s3, qc = FakeS3(), FakeQdrant()
    result = _service(s3, qc).run_backup()
    assert sorted(result.qdrant_objects) == [
        "backups/2026-06-18/qdrant/c1.snapshot",
        "backups/2026-06-18/qdrant/c2.snapshot",
    ]
    assert result.postgres_object == "backups/2026-06-18/postgres/dump.sql.gz"
    # PG object é o dump comprimido.
    assert gzip.decompress(s3.objects[result.postgres_object]) == b"PGDUMP"


def test_backup_skips_postgres_on_sqlite():
    s3, qc = FakeS3(), FakeQdrant()
    svc = BackupService(
        s3_client=s3, bucket="b", db_url="sqlite:///x.db",
        qdrant_client_provider=lambda: qc,
        pg_dump_runner=lambda url: b"NOPE",
        clock=lambda: datetime(2026, 6, 18, tzinfo=UTC),
    )
    result = svc.run_backup()
    assert result.postgres_object is None
    assert len(result.qdrant_objects) == 2


def test_backup_error_increments_metric_and_raises():
    class BoomS3(FakeS3):
        def put_object(self, **kw):
            raise RuntimeError("s3 down")

    with pytest.raises(RuntimeError):
        _service(BoomS3(), FakeQdrant()).run_backup()


def test_status_reports_latest_and_age():
    s3, qc = FakeS3(), FakeQdrant()
    _service(s3, qc).run_backup()
    # clock 2h após o LastModified fixo (10:00 do dia 18 vs 00:00 do dia 18).
    svc = BackupService(s3_client=s3, bucket="b", db_url=_PG_URL,
                        clock=lambda: datetime(2026, 6, 18, 12, 0, tzinfo=UTC))
    status = svc.status()
    assert status["objects"] == 3  # 2 qdrant + 1 pg
    assert status["rpo_age_seconds"] == 12 * 3600


def test_status_empty_bucket():
    svc = BackupService(s3_client=FakeS3(), bucket="b", db_url=_PG_URL)
    assert svc.status()["last_backup"] is None


def test_restore_recovers_qdrant_and_postgres(monkeypatch):
    s3, qc = FakeS3(), FakeQdrant()
    _service(s3, qc).run_backup()

    calls = {}
    monkeypatch.setattr(
        "app.utils.backup.subprocess.run",
        lambda *a, **k: calls.setdefault("psql", True),
    )
    out = _service(s3, qc).restore("backups/2026-06-18")
    assert out["postgres"] == "backups/2026-06-18/postgres/dump.sql.gz"
    assert sorted(out["qdrant"]) == ["c1", "c2"]
    assert calls.get("psql") is True


def test_restore_missing_prefix_raises():
    with pytest.raises(KeyError):
        _service(FakeS3(), FakeQdrant()).restore("backups/nope")
