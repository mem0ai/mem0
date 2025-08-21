from datetime import UTC, datetime
import io 
import json 
import gzip 
import zipfile
from typing import Optional, List, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_

from app.database import get_db
from app.models import (
    User, App, Memory, MemoryState, Category, memory_categories, 
    MemoryStatusHistory, AccessControl
)
from app.utils.memory import get_memory_client

from uuid import uuid4

router = APIRouter(prefix="/api/v1/backup", tags=["backup"])

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
        except: 
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

    content = await file.read()
    try:
        with zipfile.ZipFile(io.BytesIO(content), "r") as zf:
            names = zf.namelist()

            def find_member(filename: str) -> Optional[str]:
                for name in names:
                    # Skip directory entries
                    if name.endswith('/'):
                        continue
                    if name.rsplit('/', 1)[-1] == filename:
                        return name
                return None

            sqlite_member = find_member("memories.json")
            if not sqlite_member:
                raise HTTPException(status_code=400, detail="memories.json missing in zip")

            memories_member = find_member("memories.jsonl.gz")

            sqlite_data = json.loads(zf.read(sqlite_member))
            memories_blob = zf.read(memories_member) if memories_member else None
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid zip file")

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
            if memories_blob:
                gz_buf = io.BytesIO(memories_blob)
                with gzip.GzipFile(fileobj=gz_buf, mode="rb") as gz:
                    for raw in gz:
                        yield json.loads(raw.decode("utf-8"))
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


    
            
        
 


    

    






    

    










 




