import gzip
import io
import json
import os
import zipfile
from types import SimpleNamespace
from uuid import uuid4

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from fastapi import FastAPI, HTTPException, UploadFile
from httpx import ASGITransport, AsyncClient

from app.routers import backup


def _build_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _sqlite_payload(
    memories: list[dict] | None = None,
    categories: list[dict] | None = None,
    memory_categories: list[dict] | None = None,
    status_history: list[dict] | None = None,
) -> bytes:
    return json.dumps(
        {
            "categories": categories or [],
            "memories": memories or [],
            "memory_categories": memory_categories or [],
            "status_history": status_history or [],
        }
    ).encode("utf-8")


def _gzip_jsonl(lines: list[dict]) -> bytes:
    return gzip.compress(b"".join((json.dumps(line) + "\n").encode("utf-8") for line in lines))


def _gzip_bytes(content: bytes) -> bytes:
    return gzip.compress(content)


class _FakeQuery:
    def __init__(self, result):
        self.result = result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.result


class _FakeDb:
    def __init__(self):
        self.user = SimpleNamespace(id=uuid4(), user_id="user-1")
        self.query_count = 0
        self.add_count = 0
        self.commit_count = 0

    def query(self, model):
        self.query_count += 1
        if model is backup.User:
            return _FakeQuery(self.user)
        return _FakeQuery(None)

    def add(self, item):
        self.add_count += 1

    def commit(self):
        self.commit_count += 1


class _FakeZipFile:
    def __init__(self, file_size: int, content: bytes):
        self.info = SimpleNamespace(file_size=file_size)
        self.content = content

    def getinfo(self, member):
        return self.info

    def open(self, info):
        return io.BytesIO(self.content)


@pytest.mark.asyncio
async def test_read_upload_limited_rejects_oversized_archive(monkeypatch):
    monkeypatch.setattr(backup, "BACKUP_READ_CHUNK_BYTES", 4)
    monkeypatch.setattr(backup, "MAX_BACKUP_UPLOAD_BYTES", 5)
    upload = UploadFile(filename="backup.zip", file=io.BytesIO(b"123456"))

    with pytest.raises(HTTPException) as exc:
        await backup._read_upload_limited(upload)

    assert exc.value.status_code == 413
    assert exc.value.detail == "Backup archive exceeds upload limit of 5 bytes"


def test_read_zip_member_limited_rejects_underreported_member(monkeypatch):
    monkeypatch.setattr(backup, "BACKUP_READ_CHUNK_BYTES", 4)
    zf = _FakeZipFile(file_size=4, content=b"123456")

    with pytest.raises(HTTPException) as exc:
        backup._read_zip_member_limited(zf, "memories.json", 5, "memories.json")

    assert exc.value.status_code == 413
    assert exc.value.detail == "memories.json exceeds limit of 5 bytes"


def test_load_backup_archive_rejects_too_many_zip_members(monkeypatch):
    monkeypatch.setattr(backup, "MAX_BACKUP_ZIP_MEMBERS", 1)
    content = _build_zip(
        {
            "memories.json": _sqlite_payload(),
            "memories.jsonl.gz": _gzip_bytes(b""),
        }
    )

    with pytest.raises(HTTPException) as exc:
        backup._load_backup_archive(content)

    assert exc.value.status_code == 413
    assert exc.value.detail == "Backup archive exceeds file count limit of 1 records"


def test_load_backup_archive_rejects_large_central_directory(monkeypatch):
    monkeypatch.setattr(backup, "MAX_BACKUP_ZIP_CENTRAL_DIRECTORY_BYTES", 8)
    content = _build_zip({"memories.json": _sqlite_payload()})

    with pytest.raises(HTTPException) as exc:
        backup._load_backup_archive(content)

    assert exc.value.status_code == 413
    assert exc.value.detail == "Backup archive central directory exceeds limit of 8 bytes"


def test_load_backup_archive_rejects_duplicate_required_members():
    content = _build_zip(
        {
            "one/memories.json": _sqlite_payload(),
            "two/memories.json": _sqlite_payload(),
        }
    )

    with pytest.raises(HTTPException) as exc:
        backup._load_backup_archive(content)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Duplicate memories.json in zip"


def test_load_backup_archive_accepts_valid_small_archive():
    memory_id = str(uuid4())
    logical_records = [{"id": memory_id, "content": "remember this", "metadata": {}}]
    content = _build_zip(
        {
            "nested/memories.json": _sqlite_payload(),
            "nested/memories.jsonl.gz": _gzip_jsonl(logical_records),
        }
    )

    sqlite_data, memories_blob = backup._load_backup_archive(content)

    assert sqlite_data["memories"] == []
    assert list(backup._iter_limited_logical_records(memories_blob)) == logical_records


def test_load_backup_archive_rejects_oversized_sqlite_member(monkeypatch):
    monkeypatch.setattr(backup, "MAX_BACKUP_SQLITE_BYTES", 8)
    content = _build_zip({"memories.json": _sqlite_payload()})

    with pytest.raises(HTTPException) as exc:
        backup._load_backup_archive(content)

    assert exc.value.status_code == 413
    assert exc.value.detail == "memories.json exceeds limit of 8 bytes"


def test_load_backup_archive_rejects_oversized_logical_member(monkeypatch):
    monkeypatch.setattr(backup, "MAX_BACKUP_LOGICAL_GZIP_BYTES", 8)
    content = _build_zip(
        {
            "memories.json": _sqlite_payload(),
            "memories.jsonl.gz": _gzip_jsonl([{"id": str(uuid4()), "content": "remember this"}]),
        }
    )

    with pytest.raises(HTTPException) as exc:
        backup._load_backup_archive(content)

    assert exc.value.status_code == 413
    assert exc.value.detail == "memories.jsonl.gz exceeds limit of 8 bytes"


def test_validate_logical_memories_blob_rejects_oversized_decompressed_data(monkeypatch):
    monkeypatch.setattr(backup, "MAX_BACKUP_LOGICAL_DECOMPRESSED_BYTES", 16)
    blob = _gzip_jsonl([{"id": str(uuid4()), "content": "x" * 32}])

    with pytest.raises(HTTPException) as exc:
        backup._validate_logical_memories_blob(blob)

    assert exc.value.status_code == 413
    assert exc.value.detail == "memories.jsonl.gz exceeds decompressed limit of 16 bytes"


def test_validate_logical_memories_blob_accepts_exact_decompressed_limit(monkeypatch):
    record = {"id": str(uuid4()), "content": "ok", "metadata": {}}
    raw = (json.dumps(record) + "\n").encode("utf-8")
    monkeypatch.setattr(backup, "MAX_BACKUP_LOGICAL_DECOMPRESSED_BYTES", len(raw))
    monkeypatch.setattr(backup, "MAX_BACKUP_LOGICAL_RECORD_BYTES", len(raw))

    backup._validate_logical_memories_blob(_gzip_bytes(raw))


def test_validate_logical_memories_blob_rejects_oversized_record(monkeypatch):
    monkeypatch.setattr(backup, "MAX_BACKUP_LOGICAL_RECORD_BYTES", 16)
    blob = _gzip_jsonl([{"id": str(uuid4()), "content": "x" * 32}])

    with pytest.raises(HTTPException) as exc:
        backup._validate_logical_memories_blob(blob)

    assert exc.value.status_code == 413
    assert exc.value.detail == "memories.jsonl.gz contains a record that exceeds limit of 16 bytes"


def test_validate_logical_memories_blob_rejects_no_newline_oversized_record(monkeypatch):
    monkeypatch.setattr(backup, "MAX_BACKUP_LOGICAL_RECORD_BYTES", 16)
    blob = _gzip_bytes(b'{"id":"' + str(uuid4()).encode("utf-8") + b'","content":"' + (b"x" * 32) + b'"}')

    with pytest.raises(HTTPException) as exc:
        backup._validate_logical_memories_blob(blob)

    assert exc.value.status_code == 413
    assert exc.value.detail == "memories.jsonl.gz contains a record that exceeds limit of 16 bytes"


def test_validate_logical_memories_blob_rejects_too_many_records(monkeypatch):
    monkeypatch.setattr(backup, "MAX_BACKUP_LOGICAL_RECORDS", 1)
    blob = _gzip_jsonl(
        [
            {"id": str(uuid4()), "content": "one"},
            {"id": str(uuid4()), "content": "two"},
        ]
    )

    with pytest.raises(HTTPException) as exc:
        backup._validate_logical_memories_blob(blob)

    assert exc.value.status_code == 413
    assert exc.value.detail == "memories.jsonl.gz exceeds record count limit of 1 records"


def test_validate_logical_memories_blob_rejects_invalid_gzip():
    with pytest.raises(HTTPException) as exc:
        backup._validate_logical_memories_blob(b"not gzip")

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid memories.jsonl.gz"


def test_validate_logical_memories_blob_rejects_empty_gzip_member():
    with pytest.raises(HTTPException) as exc:
        backup._validate_logical_memories_blob(b"")

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid memories.jsonl.gz"


def test_validate_logical_memories_blob_accepts_zero_record_gzip_stream():
    backup._validate_logical_memories_blob(_gzip_bytes(b""))


def test_validate_logical_memories_blob_rejects_zero_records_with_manifest_memories():
    memory_id = str(uuid4())
    sqlite_data = {"memories": [{"id": memory_id}]}

    with pytest.raises(HTTPException) as exc:
        backup._validate_logical_memories_blob(_gzip_bytes(b""), sqlite_data)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid memories.jsonl.gz: no records found"


def test_validate_logical_memories_blob_rejects_missing_manifest_records():
    included_id = str(uuid4())
    missing_id = str(uuid4())
    sqlite_data = {"memories": [{"id": included_id}, {"id": missing_id}]}

    with pytest.raises(HTTPException) as exc:
        backup._validate_logical_memories_blob(
            _gzip_jsonl([{"id": included_id, "content": "included"}]),
            sqlite_data,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid memories.jsonl.gz: records do not match memories.json"


def test_validate_logical_memories_blob_rejects_duplicate_record_ids():
    memory_id = str(uuid4())
    sqlite_data = {"memories": [{"id": memory_id}]}

    with pytest.raises(HTTPException) as exc:
        backup._validate_logical_memories_blob(
            _gzip_jsonl(
                [
                    {"id": memory_id, "content": "one"},
                    {"id": memory_id, "content": "two"},
                ]
            ),
            sqlite_data,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid memories.jsonl.gz: duplicate record 2.id"


def test_validate_logical_memories_blob_rejects_malformed_jsonl():
    with pytest.raises(HTTPException) as exc:
        backup._validate_logical_memories_blob(_gzip_bytes(b"{not-json}\n"))

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid memories.jsonl.gz"


def test_validate_logical_memories_blob_rejects_non_object_record():
    with pytest.raises(HTTPException) as exc:
        backup._validate_logical_memories_blob(_gzip_bytes(b"[]\n"))

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid memories.jsonl.gz: record 1 must be an object"


def test_validate_logical_memories_blob_rejects_missing_record_id():
    with pytest.raises(HTTPException) as exc:
        backup._validate_logical_memories_blob(_gzip_jsonl([{}]))

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid memories.json: memories.jsonl.gz record 1.id must be a UUID"


def test_validate_logical_memories_blob_rejects_bad_record_uuid():
    with pytest.raises(HTTPException) as exc:
        backup._validate_logical_memories_blob(_gzip_jsonl([{"id": "not-a-uuid"}]))

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid memories.json: memories.jsonl.gz record 1.id must be a UUID"


def test_validate_logical_memories_blob_rejects_record_missing_from_manifest():
    manifest_memory_id = str(uuid4())
    logical_memory_id = str(uuid4())
    sqlite_data = {
        "memories": [{"id": manifest_memory_id}],
    }

    with pytest.raises(HTTPException) as exc:
        backup._validate_logical_memories_blob(
            _gzip_jsonl([{"id": logical_memory_id, "content": "remember this"}]),
            sqlite_data,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid memories.jsonl.gz: record 1.id is not present in memories.json"


@pytest.mark.parametrize(
    ("section", "record"),
    [
        ("categories", {"id": str(uuid4()), "name": "work"}),
        ("memories", {"id": str(uuid4())}),
        ("memory_categories", {"memory_id": str(uuid4()), "category_id": str(uuid4())}),
        ("status_history", {"id": str(uuid4()), "memory_id": str(uuid4())}),
        ("apps", {}),
        ("access_controls", {}),
    ],
)
def test_validate_sqlite_manifest_rejects_too_many_manifest_records(monkeypatch, section, record):
    monkeypatch.setattr(backup, "MAX_BACKUP_MANIFEST_RECORDS", 1)
    payload = {
        "categories": [],
        "memories": [],
        "memory_categories": [],
        "status_history": [],
        "apps": [],
        "access_controls": [],
    }
    payload[section] = [record, record]

    with pytest.raises(HTTPException) as exc:
        backup._validate_sqlite_backup_manifest(payload)

    assert exc.value.status_code == 413
    assert exc.value.detail == f"memories.json {section} exceeds record limit of 1 records"


def test_validate_sqlite_manifest_rejects_invalid_memory_id():
    payload = {
        "categories": [],
        "memories": [{"id": "not-a-uuid"}],
        "memory_categories": [],
        "status_history": [],
    }

    with pytest.raises(HTTPException) as exc:
        backup._validate_sqlite_backup_manifest(payload)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid memories.json: memories[0].id must be a UUID"


def test_validate_sqlite_manifest_rejects_non_string_memory_content():
    payload = {
        "categories": [],
        "memories": [{"id": str(uuid4()), "content": {"text": "not a string"}}],
        "memory_categories": [],
        "status_history": [],
    }

    with pytest.raises(HTTPException) as exc:
        backup._validate_sqlite_backup_manifest(payload)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid memories.json: memories[0].content must be a string"


def test_validate_sqlite_manifest_rejects_non_object_memory_metadata():
    payload = {
        "categories": [],
        "memories": [{"id": str(uuid4()), "metadata": ["not", "an", "object"]}],
        "memory_categories": [],
        "status_history": [],
    }

    with pytest.raises(HTTPException) as exc:
        backup._validate_sqlite_backup_manifest(payload)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid memories.json: memories[0].metadata must be an object"


def test_validate_sqlite_manifest_rejects_non_string_category_description():
    payload = {
        "categories": [{"id": str(uuid4()), "name": "work", "description": ["not", "a", "string"]}],
        "memories": [],
        "memory_categories": [],
        "status_history": [],
    }

    with pytest.raises(HTTPException) as exc:
        backup._validate_sqlite_backup_manifest(payload)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid memories.json: categories[0].description must be a string"


@pytest.mark.parametrize(
    ("section", "rows", "detail"),
    [
        (
            "categories",
            lambda item_id: [{"id": item_id, "name": "one"}, {"id": item_id, "name": "two"}],
            "Invalid memories.json: duplicate categories[1].id",
        ),
        (
            "memories",
            lambda item_id: [{"id": item_id, "content": "one"}, {"id": item_id, "content": "two"}],
            "Invalid memories.json: duplicate memories[1].id",
        ),
        (
            "status_history",
            lambda item_id: [
                {"id": item_id, "memory_id": str(uuid4())},
                {"id": item_id, "memory_id": str(uuid4())},
            ],
            "Invalid memories.json: duplicate status_history[1].id",
        ),
    ],
)
def test_validate_sqlite_manifest_rejects_duplicate_ids(section, rows, detail):
    item_id = str(uuid4())
    memory_id = str(uuid4())
    payload = {
        "categories": [],
        "memories": [{"id": memory_id}],
        "memory_categories": [],
        "status_history": [],
    }
    payload[section] = rows(item_id)
    if section == "status_history":
        payload["memories"] = [{"id": payload[section][0]["memory_id"]}]
        payload[section][1]["memory_id"] = payload[section][0]["memory_id"]

    with pytest.raises(HTTPException) as exc:
        backup._validate_sqlite_backup_manifest(payload)

    assert exc.value.status_code == 400
    assert exc.value.detail == detail


@pytest.mark.parametrize("timestamp_field", ["created_at", "updated_at", "archived_at", "deleted_at"])
def test_validate_sqlite_manifest_rejects_invalid_memory_timestamps(timestamp_field):
    payload = {
        "categories": [],
        "memories": [{"id": str(uuid4()), timestamp_field: "not-an-iso-timestamp"}],
        "memory_categories": [],
        "status_history": [],
    }

    with pytest.raises(HTTPException) as exc:
        backup._validate_sqlite_backup_manifest(payload)

    assert exc.value.status_code == 400
    assert exc.value.detail == f"Invalid memories.json: memories[0].{timestamp_field} must be an ISO timestamp"


@pytest.mark.parametrize("timestamp_field", ["created_at", "updated_at"])
def test_validate_logical_memories_blob_rejects_invalid_timestamps(timestamp_field):
    with pytest.raises(HTTPException) as exc:
        backup._validate_logical_memories_blob(
            _gzip_jsonl([{"id": str(uuid4()), timestamp_field: "not-an-iso-timestamp"}])
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == f"Invalid memories.jsonl.gz: record 1.{timestamp_field} must be an ISO timestamp"


def test_validate_sqlite_manifest_rejects_dangling_memory_category_link():
    category_id = str(uuid4())
    payload = {
        "categories": [{"id": category_id, "name": "work"}],
        "memories": [{"id": str(uuid4())}],
        "memory_categories": [{"memory_id": str(uuid4()), "category_id": category_id}],
        "status_history": [],
    }

    with pytest.raises(HTTPException) as exc:
        backup._validate_sqlite_backup_manifest(payload)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid memories.json: memory_categories[0].memory_id is not present in memories"


def test_validate_sqlite_manifest_rejects_dangling_status_history():
    payload = {
        "categories": [],
        "memories": [{"id": str(uuid4())}],
        "memory_categories": [],
        "status_history": [{"id": str(uuid4()), "memory_id": str(uuid4())}],
    }

    with pytest.raises(HTTPException) as exc:
        backup._validate_sqlite_backup_manifest(payload)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid memories.json: status_history[0].memory_id is not present in memories"


def test_validate_sqlite_manifest_rejects_invalid_status_history_timestamp():
    memory_id = str(uuid4())
    payload = {
        "categories": [],
        "memories": [{"id": memory_id}],
        "memory_categories": [],
        "status_history": [{"id": str(uuid4()), "memory_id": memory_id, "changed_at": "bad-ts"}],
    }

    with pytest.raises(HTTPException) as exc:
        backup._validate_sqlite_backup_manifest(payload)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid memories.json: status_history[0].changed_at must be an ISO timestamp"


@pytest.mark.asyncio
async def test_import_backup_rejects_invalid_gzip_before_db_writes():
    db = _FakeDb()
    content = _build_zip(
        {
            "memories.json": _sqlite_payload(),
            "memories.jsonl.gz": b"not gzip",
        }
    )
    upload = UploadFile(filename="backup.zip", file=io.BytesIO(content))

    with pytest.raises(HTTPException) as exc:
        await backup.import_backup(file=upload, user_id="user-1", mode="overwrite", db=db)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid memories.jsonl.gz"
    assert db.add_count == 0
    assert db.commit_count == 0
    assert db.query_count == 1


@pytest.mark.asyncio
async def test_import_backup_rejects_empty_gzip_member_before_db_writes():
    db = _FakeDb()
    content = _build_zip(
        {
            "memories.json": _sqlite_payload(),
            "memories.jsonl.gz": b"",
        }
    )
    upload = UploadFile(filename="backup.zip", file=io.BytesIO(content))

    with pytest.raises(HTTPException) as exc:
        await backup.import_backup(file=upload, user_id="user-1", mode="overwrite", db=db)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid memories.jsonl.gz"
    assert db.add_count == 0
    assert db.commit_count == 0
    assert db.query_count == 1


@pytest.mark.asyncio
async def test_import_backup_rejects_empty_logical_records_before_db_writes():
    db = _FakeDb()
    memory_id = str(uuid4())
    content = _build_zip(
        {
            "memories.json": _sqlite_payload(memories=[{"id": memory_id}]),
            "memories.jsonl.gz": _gzip_bytes(b""),
        }
    )
    upload = UploadFile(filename="backup.zip", file=io.BytesIO(content))

    with pytest.raises(HTTPException) as exc:
        await backup.import_backup(file=upload, user_id="user-1", mode="overwrite", db=db)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid memories.jsonl.gz: no records found"
    assert db.add_count == 0
    assert db.commit_count == 0
    assert db.query_count == 1


@pytest.mark.asyncio
async def test_import_backup_rejects_incomplete_logical_records_before_db_writes():
    db = _FakeDb()
    included_id = str(uuid4())
    missing_id = str(uuid4())
    content = _build_zip(
        {
            "memories.json": _sqlite_payload(memories=[{"id": included_id}, {"id": missing_id}]),
            "memories.jsonl.gz": _gzip_jsonl([{"id": included_id, "content": "included"}]),
        }
    )
    upload = UploadFile(filename="backup.zip", file=io.BytesIO(content))

    with pytest.raises(HTTPException) as exc:
        await backup.import_backup(file=upload, user_id="user-1", mode="overwrite", db=db)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid memories.jsonl.gz: records do not match memories.json"
    assert db.add_count == 0
    assert db.commit_count == 0
    assert db.query_count == 1


@pytest.mark.asyncio
async def test_import_backup_rejects_bad_category_description_before_db_writes():
    db = _FakeDb()
    content = _build_zip(
        {
            "memories.json": _sqlite_payload(
                categories=[{"id": str(uuid4()), "name": "work", "description": ["bad"]}]
            ),
        }
    )
    upload = UploadFile(filename="backup.zip", file=io.BytesIO(content))

    with pytest.raises(HTTPException) as exc:
        await backup.import_backup(file=upload, user_id="user-1", mode="overwrite", db=db)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid memories.json: categories[0].description must be a string"
    assert db.add_count == 0
    assert db.commit_count == 0
    assert db.query_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("timestamp_field", ["created_at", "updated_at", "archived_at", "deleted_at"])
async def test_import_backup_rejects_bad_manifest_timestamp_before_db_writes(timestamp_field):
    db = _FakeDb()
    content = _build_zip(
        {
            "memories.json": _sqlite_payload(
                memories=[{"id": str(uuid4()), timestamp_field: "not-an-iso-timestamp"}]
            ),
        }
    )
    upload = UploadFile(filename="backup.zip", file=io.BytesIO(content))

    with pytest.raises(HTTPException) as exc:
        await backup.import_backup(file=upload, user_id="user-1", mode="overwrite", db=db)

    assert exc.value.status_code == 400
    assert exc.value.detail == f"Invalid memories.json: memories[0].{timestamp_field} must be an ISO timestamp"
    assert db.add_count == 0
    assert db.commit_count == 0
    assert db.query_count == 1


@pytest.mark.asyncio
async def test_import_backup_rejects_bad_logical_timestamp_before_db_writes():
    db = _FakeDb()
    memory_id = str(uuid4())
    content = _build_zip(
        {
            "memories.json": _sqlite_payload(memories=[{"id": memory_id}]),
            "memories.jsonl.gz": _gzip_jsonl([{"id": memory_id, "created_at": "bad-ts"}]),
        }
    )
    upload = UploadFile(filename="backup.zip", file=io.BytesIO(content))

    with pytest.raises(HTTPException) as exc:
        await backup.import_backup(file=upload, user_id="user-1", mode="overwrite", db=db)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid memories.jsonl.gz: record 1.created_at must be an ISO timestamp"
    assert db.add_count == 0
    assert db.commit_count == 0
    assert db.query_count == 1


@pytest.mark.asyncio
async def test_import_backup_rejects_bad_history_timestamp_before_db_writes():
    db = _FakeDb()
    memory_id = str(uuid4())
    content = _build_zip(
        {
            "memories.json": _sqlite_payload(
                memories=[{"id": memory_id}],
                status_history=[{"id": str(uuid4()), "memory_id": memory_id, "changed_at": "bad-ts"}],
            ),
        }
    )
    upload = UploadFile(filename="backup.zip", file=io.BytesIO(content))

    with pytest.raises(HTTPException) as exc:
        await backup.import_backup(file=upload, user_id="user-1", mode="overwrite", db=db)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid memories.json: status_history[0].changed_at must be an ISO timestamp"
    assert db.add_count == 0
    assert db.commit_count == 0
    assert db.query_count == 1


@pytest.mark.asyncio
async def test_import_backup_rejects_bad_logical_record_before_db_writes():
    db = _FakeDb()
    memory_id = str(uuid4())
    content = _build_zip(
        {
            "memories.json": _sqlite_payload(memories=[{"id": memory_id}]),
            "memories.jsonl.gz": _gzip_jsonl([{}]),
        }
    )
    upload = UploadFile(filename="backup.zip", file=io.BytesIO(content))

    with pytest.raises(HTTPException) as exc:
        await backup.import_backup(file=upload, user_id="user-1", mode="overwrite", db=db)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid memories.json: memories.jsonl.gz record 1.id must be a UUID"
    assert db.add_count == 0
    assert db.commit_count == 0
    assert db.query_count == 1


@pytest.mark.asyncio
async def test_import_backup_rejects_bad_manifest_content_before_db_writes():
    db = _FakeDb()
    content = _build_zip(
        {
            "memories.json": _sqlite_payload(memories=[{"id": str(uuid4()), "content": {"bad": "shape"}}]),
        }
    )
    upload = UploadFile(filename="backup.zip", file=io.BytesIO(content))

    with pytest.raises(HTTPException) as exc:
        await backup.import_backup(file=upload, user_id="user-1", mode="overwrite", db=db)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid memories.json: memories[0].content must be a string"
    assert db.add_count == 0
    assert db.commit_count == 0
    assert db.query_count == 1


def test_load_backup_archive_preserves_missing_memories_json_status():
    content = _build_zip({"memories.jsonl.gz": _gzip_jsonl([])})

    with pytest.raises(HTTPException) as exc:
        backup._load_backup_archive(content)

    assert exc.value.status_code == 400
    assert exc.value.detail == "memories.json missing in zip"


def test_load_backup_archive_rejects_malformed_memories_json():
    content = _build_zip({"memories.json": b"{not-json}"})

    with pytest.raises(HTTPException) as exc:
        backup._load_backup_archive(content)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid zip file"


@pytest.mark.asyncio
async def test_import_backup_route_rejects_invalid_gzip_before_db_writes():
    db = _FakeDb()
    content = _build_zip(
        {
            "memories.json": _sqlite_payload(),
            "memories.jsonl.gz": b"not gzip",
        }
    )
    app = FastAPI()
    app.include_router(backup.router)
    app.dependency_overrides[backup.get_db] = lambda: db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/backup/import?mode=overwrite",
            data={"user_id": "user-1"},
            files={"file": ("backup.zip", content, "application/zip")},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid memories.jsonl.gz"
    assert db.add_count == 0
    assert db.commit_count == 0
    assert db.query_count == 1


@pytest.mark.asyncio
async def test_import_backup_route_rejects_oversized_upload_before_db_writes(monkeypatch):
    monkeypatch.setattr(backup, "BACKUP_READ_CHUNK_BYTES", 4)
    monkeypatch.setattr(backup, "MAX_BACKUP_UPLOAD_BYTES", 5)
    db = _FakeDb()
    app = FastAPI()
    app.include_router(backup.router)
    app.dependency_overrides[backup.get_db] = lambda: db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/backup/import?mode=overwrite",
            data={"user_id": "user-1"},
            files={"file": ("backup.zip", b"123456", "application/zip")},
        )

    assert response.status_code == 413
    assert response.json()["detail"] == "Backup archive exceeds upload limit of 5 bytes"
    assert db.add_count == 0
    assert db.commit_count == 0
    assert db.query_count == 1
