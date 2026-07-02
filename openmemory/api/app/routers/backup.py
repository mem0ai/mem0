from datetime import UTC, datetime
import io 
import json 
import gzip 
import os
import struct
import zipfile
from typing import Optional, List, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    User, App, Memory, MemoryState, Category, memory_categories, 
    MemoryStatusHistory, AccessControl
)
from app.utils.memory import get_memory_client

from uuid import uuid4

router = APIRouter(prefix="/api/v1/backup", tags=["backup"])


def _get_positive_int_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


def _format_limit(value: int, unit: str = "bytes") -> str:
    if unit == "records":
        return f"{value:,} records"
    if value % (1024 * 1024) == 0:
        return f"{value // (1024 * 1024)} MiB"
    if value % 1024 == 0:
        return f"{value // 1024} KiB"
    return f"{value:,} bytes"


BACKUP_READ_CHUNK_BYTES = _get_positive_int_env("OPENMEMORY_BACKUP_READ_CHUNK_BYTES", 1024 * 1024)
MAX_BACKUP_UPLOAD_BYTES = _get_positive_int_env("OPENMEMORY_MAX_BACKUP_UPLOAD_BYTES", 100 * 1024 * 1024)
MAX_BACKUP_SQLITE_BYTES = _get_positive_int_env("OPENMEMORY_MAX_BACKUP_SQLITE_BYTES", 10 * 1024 * 1024)
MAX_BACKUP_LOGICAL_GZIP_BYTES = _get_positive_int_env("OPENMEMORY_MAX_BACKUP_LOGICAL_GZIP_BYTES", 100 * 1024 * 1024)
MAX_BACKUP_LOGICAL_DECOMPRESSED_BYTES = _get_positive_int_env(
    "OPENMEMORY_MAX_BACKUP_LOGICAL_DECOMPRESSED_BYTES",
    250 * 1024 * 1024,
)
MAX_BACKUP_LOGICAL_RECORD_BYTES = _get_positive_int_env(
    "OPENMEMORY_MAX_BACKUP_LOGICAL_RECORD_BYTES",
    1024 * 1024,
)
MAX_BACKUP_LOGICAL_RECORDS = _get_positive_int_env("OPENMEMORY_MAX_BACKUP_LOGICAL_RECORDS", 250_000)
MAX_BACKUP_MANIFEST_RECORDS = _get_positive_int_env("OPENMEMORY_MAX_BACKUP_MANIFEST_RECORDS", 250_000)
MAX_BACKUP_ZIP_MEMBERS = _get_positive_int_env("OPENMEMORY_MAX_BACKUP_ZIP_MEMBERS", 64)
MAX_BACKUP_ZIP_CENTRAL_DIRECTORY_BYTES = _get_positive_int_env(
    "OPENMEMORY_MAX_BACKUP_ZIP_CENTRAL_DIRECTORY_BYTES",
    1024 * 1024,
)


class ExportRequest(BaseModel):
    user_id: str
    app_id: Optional[UUID] = None
    from_date: Optional[int] = None
    to_date: Optional[int] = None
    include_vectors: bool = True

def _iso(dt: Optional[datetime]) -> Optional[str]: 
    if isinstance(dt, datetime): 
        try: 
            return dt.astimezone(UTC).isoformat()
        except Exception:
            return dt.replace(tzinfo=UTC).isoformat()
    return None

def _parse_iso(dt: Optional[str]) -> Optional[datetime]:
    if not dt:
        return None
    try:
        return datetime.fromisoformat(dt)
    except Exception:
        try:
            return datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except Exception:
            return None


def _validate_optional_iso_timestamp(value: Any, field: str, source: str = "memories.json") -> None:
    if value is None:
        return
    if not isinstance(value, str):
        raise HTTPException(status_code=400, detail=f"Invalid {source}: {field} must be a string")
    if _parse_iso(value) is None:
        raise HTTPException(status_code=400, detail=f"Invalid {source}: {field} must be an ISO timestamp")


async def _read_upload_limited(file: UploadFile) -> bytes:
    data = bytearray()
    while True:
        read_size = min(BACKUP_READ_CHUNK_BYTES, MAX_BACKUP_UPLOAD_BYTES - len(data) + 1)
        chunk = await file.read(read_size)
        if not chunk:
            break
        if len(data) + len(chunk) > MAX_BACKUP_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Backup archive exceeds upload limit of {_format_limit(MAX_BACKUP_UPLOAD_BYTES)}",
            )
        data.extend(chunk)
    return bytes(data)


def _find_backup_members(infos: List[zipfile.ZipInfo]) -> tuple[Optional[str], Optional[str]]:
    sqlite_member = None
    memories_member = None
    seen_files = 0

    for info in infos:
        if info.is_dir():
            continue
        seen_files += 1
        if seen_files > MAX_BACKUP_ZIP_MEMBERS:
            raise HTTPException(
                status_code=413,
                detail=f"Backup archive exceeds file count limit of {_format_limit(MAX_BACKUP_ZIP_MEMBERS, unit='records')}",
            )

        basename = info.filename.rsplit("/", 1)[-1]
        if basename == "memories.json":
            if sqlite_member is not None:
                raise HTTPException(status_code=400, detail="Duplicate memories.json in zip")
            sqlite_member = info.filename
        elif basename == "memories.jsonl.gz":
            if memories_member is not None:
                raise HTTPException(status_code=400, detail="Duplicate memories.jsonl.gz in zip")
            memories_member = info.filename

    return sqlite_member, memories_member


def _validate_zip_directory_limits(content: bytes) -> None:
    eocd_signature = b"PK\x05\x06"
    zip64_locator_signature = b"PK\x06\x07"
    zip64_eocd_signature = b"PK\x06\x06"
    search_start = max(0, len(content) - (65_535 + 22))
    eocd_offset = content.rfind(eocd_signature, search_start)
    if eocd_offset < 0 or eocd_offset + 22 > len(content):
        raise HTTPException(status_code=400, detail="Invalid zip file")

    (
        _signature,
        disk_number,
        central_directory_disk,
        entries_this_disk,
        total_entries,
        central_directory_size,
        central_directory_offset,
        comment_length,
    ) = struct.unpack_from("<4s4H2LH", content, eocd_offset)

    if eocd_offset + 22 + comment_length != len(content):
        raise HTTPException(status_code=400, detail="Invalid zip file")
    if disk_number != 0 or central_directory_disk != 0 or entries_this_disk != total_entries:
        raise HTTPException(status_code=400, detail="Invalid zip file")

    if total_entries == 0xFFFF or central_directory_size == 0xFFFFFFFF or central_directory_offset == 0xFFFFFFFF:
        locator_offset = eocd_offset - 20
        if locator_offset < 0 or content[locator_offset : locator_offset + 4] != zip64_locator_signature:
            raise HTTPException(status_code=400, detail="Invalid zip file")
        (_locator_signature, _locator_disk, zip64_eocd_offset, total_disks) = struct.unpack_from(
            "<4sLQL",
            content,
            locator_offset,
        )
        if total_disks != 1 or zip64_eocd_offset + 56 > len(content):
            raise HTTPException(status_code=400, detail="Invalid zip file")
        if content[zip64_eocd_offset : zip64_eocd_offset + 4] != zip64_eocd_signature:
            raise HTTPException(status_code=400, detail="Invalid zip file")
        (
            _zip64_signature,
            _zip64_record_size,
            _version_made_by,
            _version_needed,
            zip64_disk_number,
            zip64_directory_disk,
            zip64_entries_this_disk,
            zip64_total_entries,
            zip64_central_directory_size,
            zip64_central_directory_offset,
        ) = struct.unpack_from("<4sQ2H2L4Q", content, zip64_eocd_offset)
        if (
            zip64_disk_number != 0
            or zip64_directory_disk != 0
            or zip64_entries_this_disk != zip64_total_entries
        ):
            raise HTTPException(status_code=400, detail="Invalid zip file")
        total_entries = zip64_total_entries
        central_directory_size = zip64_central_directory_size
        central_directory_offset = zip64_central_directory_offset

    if total_entries > MAX_BACKUP_ZIP_MEMBERS:
        raise HTTPException(
            status_code=413,
            detail=f"Backup archive exceeds file count limit of {_format_limit(MAX_BACKUP_ZIP_MEMBERS, unit='records')}",
        )
    if central_directory_size > MAX_BACKUP_ZIP_CENTRAL_DIRECTORY_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                "Backup archive central directory exceeds limit of "
                f"{_format_limit(MAX_BACKUP_ZIP_CENTRAL_DIRECTORY_BYTES)}"
            ),
        )
    if central_directory_offset + central_directory_size > len(content):
        raise HTTPException(status_code=400, detail="Invalid zip file")


def _read_zip_member_limited(zf: zipfile.ZipFile, member: str, max_bytes: int, label: str) -> bytes:
    info = zf.getinfo(member)
    if info.file_size > max_bytes:
        raise HTTPException(status_code=413, detail=f"{label} exceeds limit of {_format_limit(max_bytes)}")

    data = bytearray()
    with zf.open(info) as member_file:
        while True:
            read_size = min(BACKUP_READ_CHUNK_BYTES, max_bytes - len(data) + 1)
            chunk = member_file.read(read_size)
            if not chunk:
                break
            if len(data) + len(chunk) > max_bytes:
                raise HTTPException(status_code=413, detail=f"{label} exceeds limit of {_format_limit(max_bytes)}")
            data.extend(chunk)
    return bytes(data)


def _load_backup_archive(content: bytes) -> tuple[Dict[str, Any], Optional[bytes]]:
    try:
        _validate_zip_directory_limits(content)
        with zipfile.ZipFile(io.BytesIO(content), "r") as zf:
            sqlite_member, memories_member = _find_backup_members(zf.infolist())
            if not sqlite_member:
                raise HTTPException(status_code=400, detail="memories.json missing in zip")

            sqlite_data = json.loads(
                _read_zip_member_limited(zf, sqlite_member, MAX_BACKUP_SQLITE_BYTES, "memories.json")
            )
            memories_blob = (
                _read_zip_member_limited(
                    zf,
                    memories_member,
                    MAX_BACKUP_LOGICAL_GZIP_BYTES,
                    "memories.jsonl.gz",
                )
                if memories_member
                else None
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid zip file")

    return sqlite_data, memories_blob


def _validate_uuid(value: Any, label: str) -> None:
    try:
        UUID(str(value))
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid memories.json: {label} must be a UUID")


def _validate_manifest_list(sqlite_data: Dict[str, Any], key: str) -> List[Any]:
    value = sqlite_data.get(key, [])
    if not isinstance(value, list):
        raise HTTPException(status_code=400, detail=f"Invalid memories.json: {key} must be a list")
    if len(value) > MAX_BACKUP_MANIFEST_RECORDS:
        raise HTTPException(
            status_code=413,
            detail=(
                f"memories.json {key} exceeds record limit of "
                f"{_format_limit(MAX_BACKUP_MANIFEST_RECORDS, unit='records')}"
            ),
        )
    return value


def _validate_unique_id(value: str, seen: set[str], label: str) -> None:
    if value in seen:
        raise HTTPException(status_code=400, detail=f"Invalid memories.json: duplicate {label}")
    seen.add(value)


def _validate_sqlite_backup_manifest(sqlite_data: Dict[str, Any]) -> None:
    if not isinstance(sqlite_data, dict):
        raise HTTPException(status_code=400, detail="Invalid memories.json: root must be an object")

    categories = _validate_manifest_list(sqlite_data, "categories")
    memories = _validate_manifest_list(sqlite_data, "memories")
    memory_categories_rows = _validate_manifest_list(sqlite_data, "memory_categories")
    history_rows = _validate_manifest_list(sqlite_data, "status_history")
    _validate_manifest_list(sqlite_data, "apps")
    _validate_manifest_list(sqlite_data, "access_controls")

    valid_states = {state.value for state in MemoryState}
    known_category_ids = set()
    for index, category in enumerate(categories):
        if not isinstance(category, dict):
            raise HTTPException(status_code=400, detail="Invalid memories.json: categories entries must be objects")
        category_id = str(category.get("id"))
        _validate_uuid(category_id, f"categories[{index}].id")
        _validate_unique_id(category_id, known_category_ids, f"categories[{index}].id")
        if not isinstance(category.get("name"), str):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid memories.json: categories[{index}].name must be a string",
            )
        description = category.get("description")
        if description is not None and not isinstance(description, str):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid memories.json: categories[{index}].description must be a string",
            )

    memory_ids = set()
    for index, memory in enumerate(memories):
        if not isinstance(memory, dict):
            raise HTTPException(status_code=400, detail="Invalid memories.json: memories entries must be objects")
        memory_id = str(memory.get("id"))
        _validate_uuid(memory_id, f"memories[{index}].id")
        _validate_unique_id(memory_id, memory_ids, f"memories[{index}].id")
        content = memory.get("content")
        if content is not None and not isinstance(content, str):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid memories.json: memories[{index}].content must be a string",
            )
        metadata = memory.get("metadata")
        if metadata is not None and not isinstance(metadata, dict):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid memories.json: memories[{index}].metadata must be an object",
            )
        state = memory.get("state", "active")
        if state not in valid_states:
            raise HTTPException(status_code=400, detail=f"Invalid memories.json: memories[{index}].state is invalid")
        for key in ("created_at", "updated_at", "archived_at", "deleted_at"):
            _validate_optional_iso_timestamp(memory.get(key), f"memories[{index}].{key}")
        memory_category_ids = memory.get("category_ids", [])
        if not isinstance(memory_category_ids, list):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid memories.json: memories[{index}].category_ids must be a list",
            )
        for cat_index, category_id in enumerate(memory_category_ids):
            category_id = str(category_id)
            _validate_uuid(category_id, f"memories[{index}].category_ids[{cat_index}]")
            if category_id not in known_category_ids:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Invalid memories.json: memories[{index}].category_ids[{cat_index}] "
                        "is not present in categories"
                    ),
                )

    for index, link in enumerate(memory_categories_rows):
        if not isinstance(link, dict):
            raise HTTPException(
                status_code=400,
                detail="Invalid memories.json: memory_categories entries must be objects",
            )
        memory_id = str(link.get("memory_id"))
        category_id = str(link.get("category_id"))
        _validate_uuid(memory_id, f"memory_categories[{index}].memory_id")
        _validate_uuid(category_id, f"memory_categories[{index}].category_id")
        if memory_id not in memory_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid memories.json: memory_categories[{index}].memory_id is not present in memories",
            )
        if category_id not in known_category_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid memories.json: memory_categories[{index}].category_id is not present in categories",
            )

    history_ids = set()
    for index, history in enumerate(history_rows):
        if not isinstance(history, dict):
            raise HTTPException(status_code=400, detail="Invalid memories.json: status_history entries must be objects")
        history_id = str(history.get("id"))
        _validate_uuid(history_id, f"status_history[{index}].id")
        _validate_unique_id(history_id, history_ids, f"status_history[{index}].id")
        memory_id = str(history.get("memory_id"))
        _validate_uuid(memory_id, f"status_history[{index}].memory_id")
        if memory_id not in memory_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid memories.json: status_history[{index}].memory_id is not present in memories",
            )
        for key in ("old_state", "new_state"):
            state = history.get(key, "active")
            if state not in valid_states:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid memories.json: status_history[{index}].{key} is invalid",
                )
        _validate_optional_iso_timestamp(history.get("changed_at"), f"status_history[{index}].changed_at")


def _validate_logical_record(record: Any, index: int, allowed_memory_ids: Optional[set[str]] = None) -> None:
    if not isinstance(record, dict):
        raise HTTPException(status_code=400, detail=f"Invalid memories.jsonl.gz: record {index} must be an object")

    memory_id = record.get("id")
    _validate_uuid(memory_id, f"memories.jsonl.gz record {index}.id")
    if allowed_memory_ids is not None and str(memory_id) not in allowed_memory_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid memories.jsonl.gz: record {index}.id is not present in memories.json",
        )

    content = record.get("content")
    if content is not None and not isinstance(content, str):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid memories.jsonl.gz: record {index}.content must be a string",
        )

    metadata = record.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid memories.jsonl.gz: record {index}.metadata must be an object",
        )
    for key in ("created_at", "updated_at"):
        _validate_optional_iso_timestamp(
            record.get(key),
            f"record {index}.{key}",
            source="memories.jsonl.gz",
        )


def _iter_limited_logical_records(memories_blob: bytes):
    total_bytes = 0
    total_records = 0

    try:
        with gzip.GzipFile(fileobj=io.BytesIO(memories_blob), mode="rb") as gz:
            while True:
                remaining_total = MAX_BACKUP_LOGICAL_DECOMPRESSED_BYTES - total_bytes
                if remaining_total < 0:
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            "memories.jsonl.gz exceeds decompressed limit of "
                            f"{_format_limit(MAX_BACKUP_LOGICAL_DECOMPRESSED_BYTES)}"
                        ),
                    )
                if remaining_total == 0:
                    if gz.read(1):
                        raise HTTPException(
                            status_code=413,
                            detail=(
                                "memories.jsonl.gz exceeds decompressed limit of "
                                f"{_format_limit(MAX_BACKUP_LOGICAL_DECOMPRESSED_BYTES)}"
                            ),
                        )
                    break

                read_limit = min(MAX_BACKUP_LOGICAL_RECORD_BYTES, remaining_total) + 1
                raw = gz.readline(read_limit)
                if not raw:
                    break

                total_records += 1
                total_bytes += len(raw)

                if total_records > MAX_BACKUP_LOGICAL_RECORDS:
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            "memories.jsonl.gz exceeds record count limit of "
                            f"{_format_limit(MAX_BACKUP_LOGICAL_RECORDS, unit='records')}"
                        ),
                    )
                if total_bytes > MAX_BACKUP_LOGICAL_DECOMPRESSED_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            "memories.jsonl.gz exceeds decompressed limit of "
                            f"{_format_limit(MAX_BACKUP_LOGICAL_DECOMPRESSED_BYTES)}"
                        ),
                    )
                if len(raw) > MAX_BACKUP_LOGICAL_RECORD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            "memories.jsonl.gz contains a record that exceeds limit of "
                            f"{_format_limit(MAX_BACKUP_LOGICAL_RECORD_BYTES)}"
                        ),
                    )

                yield json.loads(raw.decode("utf-8"))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid memories.jsonl.gz")


def _validate_logical_memories_blob(
    memories_blob: Optional[bytes],
    sqlite_data: Optional[Dict[str, Any]] = None,
) -> None:
    if memories_blob is None:
        return
    if len(memories_blob) == 0:
        raise HTTPException(status_code=400, detail="Invalid memories.jsonl.gz")

    allowed_memory_ids = None
    if sqlite_data is not None:
        allowed_memory_ids = {str(memory.get("id")) for memory in sqlite_data.get("memories", [])}

    record_count = 0
    seen_memory_ids = set()
    for index, record in enumerate(_iter_limited_logical_records(memories_blob), start=1):
        record_count = index
        _validate_logical_record(record, index, allowed_memory_ids)
        memory_id = str(record.get("id"))
        if memory_id in seen_memory_ids:
            raise HTTPException(status_code=400, detail=f"Invalid memories.jsonl.gz: duplicate record {index}.id")
        seen_memory_ids.add(memory_id)

    if record_count == 0 and allowed_memory_ids:
        raise HTTPException(status_code=400, detail="Invalid memories.jsonl.gz: no records found")
    if allowed_memory_ids is not None and seen_memory_ids != allowed_memory_ids:
        raise HTTPException(status_code=400, detail="Invalid memories.jsonl.gz: records do not match memories.json")


def _export_sqlite(db: Session, req: ExportRequest) -> Dict[str, Any]: 
    user = db.query(User).filter(User.user_id == req.user_id).first()
    if not user: 
        raise HTTPException(status_code=404, detail="User not found")
    
    time_filters = []
    if req.from_date: 
        time_filters.append(Memory.created_at >= datetime.fromtimestamp(req.from_date, tz=UTC))
    if req.to_date: 
        time_filters.append(Memory.created_at <= datetime.fromtimestamp(req.to_date, tz=UTC))

    mem_q = (
        db.query(Memory)
        .options(joinedload(Memory.categories), joinedload(Memory.app))
        .filter(
            Memory.user_id == user.id, 
            *(time_filters or []), 
            * ( [Memory.app_id == req.app_id] if req.app_id else [] ),
        )
    )

    memories = mem_q.all()
    memory_ids = [m.id for m in memories]

    app_ids = sorted({m.app_id for m in memories if m.app_id})
    apps = db.query(App).filter(App.id.in_(app_ids)).all() if app_ids else []

    cats = sorted({c for m in memories for c in m.categories}, key = lambda c: str(c.id))

    mc_rows = db.execute(
        memory_categories.select().where(memory_categories.c.memory_id.in_(memory_ids))
    ).fetchall() if memory_ids else []

    history = db.query(MemoryStatusHistory).filter(MemoryStatusHistory.memory_id.in_(memory_ids)).all() if memory_ids else []

    acls = db.query(AccessControl).filter(
        AccessControl.subject_type == "app", 
        AccessControl.subject_id.in_(app_ids) if app_ids else False
    ).all() if app_ids else []

    return {
        "user": {
            "id": str(user.id), 
            "user_id": user.user_id, 
            "name": user.name, 
            "email": user.email, 
            "metadata": user.metadata_, 
            "created_at": _iso(user.created_at), 
            "updated_at": _iso(user.updated_at)
        }, 
        "apps": [
            {
                "id": str(a.id), 
                "owner_id": str(a.owner_id), 
                "name": a.name, 
                "description": a.description, 
                "metadata": a.metadata_, 
                "is_active": a.is_active, 
                "created_at": _iso(a.created_at), 
                "updated_at": _iso(a.updated_at),
            }
            for a in apps
        ], 
        "categories": [
            {
                "id": str(c.id), 
                "name": c.name, 
                "description": c.description, 
                "created_at": _iso(c.created_at), 
                "updated_at": _iso(c.updated_at), 
            }
            for c in cats
        ], 
        "memories": [
            {
                "id": str(m.id), 
                "user_id": str(m.user_id), 
                "app_id": str(m.app_id) if m.app_id else None, 
                "content": m.content, 
                "metadata": m.metadata_, 
                "state": m.state.value,
                "created_at": _iso(m.created_at), 
                "updated_at": _iso(m.updated_at), 
                "archived_at": _iso(m.archived_at), 
                "deleted_at": _iso(m.deleted_at), 
                "category_ids": [str(c.id) for c in m.categories], #TODO: figure out a way to add category names simply to this
            }
            for m in memories
        ], 
        "memory_categories": [
            {"memory_id": str(r.memory_id), "category_id": str(r.category_id)}
            for r in mc_rows
        ], 
        "status_history": [
            {
                "id": str(h.id), 
                "memory_id": str(h.memory_id), 
                "changed_by": str(h.changed_by), 
                "old_state": h.old_state.value, 
                "new_state": h.new_state.value, 
                "changed_at": _iso(h.changed_at), 
            }
            for h in history
        ], 
        "access_controls": [
            {
                "id": str(ac.id), 
                "subject_type": ac.subject_type, 
                "subject_id": str(ac.subject_id) if ac.subject_id else None, 
                "object_type": ac.object_type, 
                "object_id": str(ac.object_id) if ac.object_id else None, 
                "effect": ac.effect, 
                "created_at": _iso(ac.created_at), 
            }
            for ac in acls
        ], 
        "export_meta": {
            "app_id_filter": str(req.app_id) if req.app_id else None,
            "from_date": req.from_date,
            "to_date": req.to_date,
            "version": "1",
            "generated_at": datetime.now(UTC).isoformat(),
        },
    }

def _export_logical_memories_gz(
        db: Session, 
        *, 
        user_id: str, 
        app_id: Optional[UUID] = None, 
        from_date: Optional[int] = None, 
        to_date: Optional[int] = None
) -> bytes: 
    """
    Export a provider-agnostic backup of memories so they can be restored to any vector DB
    by re-embedding content. One JSON object per line, gzip-compressed.

    Schema (per line):
    {
      "id": "<uuid>",
      "content": "<text>",
      "metadata": {...},
      "created_at": "<iso8601 or null>",
      "updated_at": "<iso8601 or null>",
      "state": "active|paused|archived|deleted",
      "app": "<app name or null>",
      "categories": ["catA", "catB", ...]
    }
    """

    user = db.query(User).filter(User.user_id == user_id).first()
    if not user: 
        raise HTTPException(status_code=404, detail="User not found")
    
    time_filters = []
    if from_date: 
        time_filters.append(Memory.created_at >= datetime.fromtimestamp(from_date, tz=UTC))
    if to_date: 
        time_filters.append(Memory.created_at <= datetime.fromtimestamp(to_date, tz=UTC))
    
    q = (
        db.query(Memory)
        .options(joinedload(Memory.categories), joinedload(Memory.app))
        .filter(
            Memory.user_id == user.id,
            *(time_filters or []),
        )
    )
    if app_id:
        q = q.filter(Memory.app_id == app_id)

    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz: 
        for m in q.all(): 
            record = {
                "id": str(m.id),
                "content": m.content,
                "metadata": m.metadata_ or {},
                "created_at": _iso(m.created_at),
                "updated_at": _iso(m.updated_at),
                "state": m.state.value,
                "app": m.app.name if m.app else None,
                "categories": [c.name for c in m.categories],
            }
            gz.write((json.dumps(record) + "\n").encode("utf-8"))
    return buf.getvalue()

@router.post("/export")
async def export_backup(req: ExportRequest, db: Session = Depends(get_db)): 
    sqlite_payload = _export_sqlite(db=db, req=req)
    memories_blob = _export_logical_memories_gz(
        db=db, 
        user_id=req.user_id, 
        app_id=req.app_id, 
        from_date=req.from_date, 
        to_date=req.to_date,

    )

    #TODO: add vector store specific exports in future for speed 

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf: 
        zf.writestr("memories.json", json.dumps(sqlite_payload, indent=2))
        zf.writestr("memories.jsonl.gz", memories_blob)
        
    zip_buf.seek(0)
    return StreamingResponse(
        zip_buf, 
        media_type="application/zip", 
        headers={"Content-Disposition": f'attachment; filename="memories_export_{req.user_id}.zip"'},
    )

@router.post("/import")
async def import_backup(
    file: UploadFile = File(..., description="Zip with memories.json and memories.jsonl.gz"), 
    user_id: str = Form(..., description="Import memories into this user_id"),
    mode: str = Query("overwrite"), 
    db: Session = Depends(get_db)
): 
    if not file.filename.endswith(".zip"): 
        raise HTTPException(status_code=400, detail="Expected a zip file.")
    
    if mode not in {"skip", "overwrite"}:
        raise HTTPException(status_code=400, detail="Invalid mode. Must be 'skip' or 'overwrite'.")
    
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user: 
        raise HTTPException(status_code=404, detail="User not found")

    content = await _read_upload_limited(file)
    sqlite_data, memories_blob = _load_backup_archive(content)
    _validate_sqlite_backup_manifest(sqlite_data)
    _validate_logical_memories_blob(memories_blob, sqlite_data)

    default_app = db.query(App).filter(App.owner_id == user.id, App.name == "openmemory").first()
    if not default_app: 
        default_app = App(owner_id=user.id, name="openmemory", is_active=True, metadata_={})
        db.add(default_app)
        db.commit()
        db.refresh(default_app)

    cat_id_map: Dict[str, UUID] = {}
    for c in sqlite_data.get("categories", []): 
        cat = db.query(Category).filter(Category.name == c["name"]).first()
        if not cat: 
            cat = Category(name=c["name"], description=c.get("description"))
            db.add(cat)
            db.commit()
            db.refresh(cat)
        cat_id_map[c["id"]] = cat.id

    old_to_new_id: Dict[str, UUID] = {}
    for m in sqlite_data.get("memories", []): 
        incoming_id = UUID(m["id"])
        existing = db.query(Memory).filter(Memory.id == incoming_id).first()

        # Cross-user collision: always mint a new UUID and import as a new memory
        if existing and existing.user_id != user.id:
            target_id = uuid4()
        else:
            target_id = incoming_id

        old_to_new_id[m["id"]] = target_id

        # Same-user collision + skip mode: leave existing row untouched
        if existing and (existing.user_id == user.id) and mode == "skip": 
            continue 
        
        # Same-user collision + overwrite mode: treat import as ground truth
        if existing and (existing.user_id == user.id) and mode == "overwrite": 
            incoming_state = m.get("state", "active")
            existing.user_id = user.id 
            existing.app_id = default_app.id
            existing.content = m.get("content") or ""
            existing.metadata_ = m.get("metadata") or {}
            try: 
                existing.state = MemoryState(incoming_state)
            except Exception: 
                existing.state = MemoryState.active
            # Update state-related timestamps from import (ground truth)
            existing.archived_at = _parse_iso(m.get("archived_at"))
            existing.deleted_at = _parse_iso(m.get("deleted_at"))
            existing.created_at = _parse_iso(m.get("created_at")) or existing.created_at
            existing.updated_at = _parse_iso(m.get("updated_at")) or existing.updated_at
            db.add(existing)
            db.commit()
            continue

        new_mem = Memory(
            id=target_id,
            user_id=user.id,
            app_id=default_app.id,
            content=m.get("content") or "",
            metadata_=m.get("metadata") or {},
            state=MemoryState(m.get("state", "active")) if m.get("state") else MemoryState.active,
            created_at=_parse_iso(m.get("created_at")) or datetime.now(UTC),
            updated_at=_parse_iso(m.get("updated_at")) or datetime.now(UTC),
            archived_at=_parse_iso(m.get("archived_at")),
            deleted_at=_parse_iso(m.get("deleted_at")),
        )
        db.add(new_mem)
        db.commit()

    for link in sqlite_data.get("memory_categories", []): 
        mid = old_to_new_id.get(link["memory_id"])
        cid = cat_id_map.get(link["category_id"])
        if not (mid and cid): 
            continue
        exists = db.execute(
            memory_categories.select().where(
                (memory_categories.c.memory_id == mid) & (memory_categories.c.category_id == cid)
            )
        ).first()

        if not exists: 
            db.execute(memory_categories.insert().values(memory_id=mid, category_id=cid))
            db.commit()

    for h in sqlite_data.get("status_history", []): 
        hid = UUID(h["id"])
        mem_id = old_to_new_id.get(h["memory_id"], UUID(h["memory_id"]))
        exists = db.query(MemoryStatusHistory).filter(MemoryStatusHistory.id == hid).first()
        if exists and mode == "skip":
            continue
        rec = exists if exists else MemoryStatusHistory(id=hid)
        rec.memory_id = mem_id
        rec.changed_by = user.id
        try:
            rec.old_state = MemoryState(h.get("old_state", "active"))
            rec.new_state = MemoryState(h.get("new_state", "active"))
        except Exception:
            rec.old_state = MemoryState.active
            rec.new_state = MemoryState.active
        rec.changed_at = _parse_iso(h.get("changed_at")) or datetime.now(UTC)
        db.add(rec)
        db.commit()

    memory_client = get_memory_client()
    vector_store = getattr(memory_client, "vector_store", None) if memory_client else None

    if vector_store and memory_client and hasattr(memory_client, "embedding_model"):
        def iter_logical_records():
            if memories_blob is not None:
                yield from _iter_limited_logical_records(memories_blob)
            else:
                for m in sqlite_data.get("memories", []):
                    yield {
                        "id": m["id"],
                        "content": m.get("content"),
                        "metadata": m.get("metadata") or {},
                        "created_at": m.get("created_at"),
                        "updated_at": m.get("updated_at"),
                    }

        for rec in iter_logical_records():
            old_id = rec["id"]
            new_id = old_to_new_id.get(old_id, UUID(old_id))
            content = rec.get("content") or ""
            metadata = rec.get("metadata") or {}
            created_at = rec.get("created_at")
            updated_at = rec.get("updated_at")

            if mode == "skip":
                try:
                    get_fn = getattr(vector_store, "get", None)
                    if callable(get_fn) and vector_store.get(str(new_id)):
                        continue
                except Exception:
                    pass

            payload = dict(metadata)
            payload["data"] = content
            if created_at:
                payload["created_at"] = created_at
            if updated_at:
                payload["updated_at"] = updated_at
            payload["user_id"] = user_id
            payload.setdefault("source_app", "openmemory")

            try:
                vec = memory_client.embedding_model.embed(content, "add")
                vector_store.insert(vectors=[vec], payloads=[payload], ids=[str(new_id)])
            except Exception as e:
                print(f"Vector upsert failed for memory {new_id}: {e}")
                continue

        return {"message": f'Import completed into user "{user_id}"'}

    return {"message": f'Import completed into user "{user_id}"'}


    
            
        
 


    

    






    

    










 
