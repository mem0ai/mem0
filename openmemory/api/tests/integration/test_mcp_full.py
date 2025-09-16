import importlib
import json
import os
import uuid as _uuid

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test-key")


class Hit:
    def __init__(self, id, score, payload):
        self.id = id
        self.score = score
        self.payload = payload


class FakeEmbedder:
    def embed(self, text, _purpose):
        # Return a fixed-length dummy vector
        return [0.1] * 10


class FakeVectorStore:
    def __init__(self, storage):
        self._storage = storage  # dict[id] = payload

    def search(self, query, vectors, limit, filters):
        # Return all stored items for the user id filter in FIFO order
        uid = filters.get("user_id")
        hits = []
        for mid, payload in list(self._storage.items())[:limit]:
            if payload.get("user_id") == uid:
                hits.append(Hit(id=str(mid), score=0.5, payload=payload))
        return hits


class FakeMemoryClient:
    def __init__(self):
        self._items = {}  # uuid -> payload
        self.embedding_model = FakeEmbedder()
        self.vector_store = FakeVectorStore(self._items)

    def add(self, text, user_id, metadata):
        mid = _uuid.uuid4()
        payload = {
            "data": text,
            "hash": "h",
            "created_at": "now",
            "updated_at": "now",
            "user_id": user_id,
            "metadata": metadata,
        }
        self._items[mid] = payload
        return {
            "results": [
                {
                    "event": "ADD",
                    "id": str(mid),
                    "memory": text,
                }
            ]
        }

    def get_all(self, user_id):
        results = []
        for mid, payload in self._items.items():
            if payload.get("user_id") == user_id:
                results.append({
                    "id": str(mid),
                    "hash": payload.get("hash"),
                    "created_at": payload.get("created_at"),
                    "updated_at": payload.get("updated_at"),
                    "memory": payload.get("data"),
                })
        return {"results": results}

    def delete(self, memory_id):
        # Accept UUID or str
        mid = memory_id
        if isinstance(mid, str):
            mid = _uuid.UUID(mid)
        self._items.pop(mid, None)


@pytest.fixture(autouse=True)
def setup_db_and_context(monkeypatch):
    # Force SQLite for tests before importing database-bound modules
    os.environ["DATABASE_URL"] = "sqlite:///./test_openmemory.db"

    # Reload DB and models to pick up new engine
    import app.database as dbmod
    import app.mcp_server as mcp_mod
    import app.models as models
    import app.routers.memories as memrouter
    import app.utils.db as dbutils
    import app.utils.permissions as perms

    importlib.reload(dbmod)
    importlib.reload(models)
    importlib.reload(dbutils)
    importlib.reload(perms)
    importlib.reload(memrouter)
    importlib.reload(mcp_mod)

    # Expose reloaded artifacts to global namespace for tests
    global Base, engine, SessionLocal
    global Memory, MemoryAccessLog, MemoryState, MemoryStatusHistory
    global add_memories, search_memory, list_memories, delete_all_memories
    global user_id_var, client_name_var
    global check_memory_access_permissions, get_accessible_memory_ids

    Base = dbmod.Base
    engine = dbmod.engine
    SessionLocal = dbmod.SessionLocal

    Memory = models.Memory
    MemoryAccessLog = models.MemoryAccessLog
    MemoryState = models.MemoryState
    MemoryStatusHistory = models.MemoryStatusHistory
    check_memory_access_permissions = perms.check_memory_access_permissions
    get_accessible_memory_ids = memrouter.get_accessible_memory_ids

    add_memories = mcp_mod.add_memories
    search_memory = mcp_mod.search_memory
    list_memories = mcp_mod.list_memories
    delete_all_memories = mcp_mod.delete_all_memories
    user_id_var = mcp_mod.user_id_var
    client_name_var = mcp_mod.client_name_var

    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    # Set context vars
    user_token = user_id_var.set("it-user")
    client_token = client_name_var.set("it-client")

    # Patch out categorization to avoid external OpenAI calls
    monkeypatch.setattr(models, "categorize_memory", lambda m, db: None)

    # Provide a working fake memory client
    fake_client = FakeMemoryClient()
    monkeypatch.setattr(mcp_mod, "get_memory_client_safe", lambda: fake_client)

    try:
        yield
    finally:
        # Reset context vars
        user_id_var.reset(user_token)
        client_name_var.reset(client_token)


@pytest.mark.asyncio
async def test_full_add_list_search_delete_flow():
    text = "remember: mcp full flow works"

    # Add
    add_resp_s = await add_memories(text)
    add_resp = json.loads(add_resp_s)
    assert "results" in add_resp and add_resp["results"][0]["event"] == "ADD"
    mid_str = add_resp["results"][0]["id"]
    mid = _uuid.UUID(mid_str)

    # Validate DB insert and state
    db = SessionLocal()
    try:
        m = db.query(Memory).filter(Memory.id == mid).first()
        assert m is not None
        assert m.content == text
        assert m.state == MemoryState.active
        # History should have an entry to active
        hist = db.query(MemoryStatusHistory).filter(MemoryStatusHistory.memory_id == mid).all()
        assert any(h.new_state == MemoryState.active for h in hist)
    finally:
        db.close()

    # List
    list_resp_s = await list_memories()
    listed = json.loads(list_resp_s)
    # Ensure the added memory ID appears in list output
    assert any(item.get("id") == mid_str for item in listed)

    # Search
    search_resp_s = await search_memory("full flow")
    search_resp = json.loads(search_resp_s)
    assert any(r.get("id") == mid_str and r.get("memory") == text for r in search_resp.get("results", []))

    # Access log created for search
    db = SessionLocal()
    try:
        logs = db.query(MemoryAccessLog).filter(MemoryAccessLog.memory_id == mid).all()
        assert any(log.access_type == "search" for log in logs)
    finally:
        db.close()

    # Delete all memories
    del_resp = await delete_all_memories()
    assert "Successfully deleted" in del_resp

    # Validate state updated and history recorded
    db = SessionLocal()
    try:
        m = db.query(Memory).filter(Memory.id == mid).first()
        assert m is not None
        assert m.state == MemoryState.deleted
        hist = db.query(MemoryStatusHistory).filter(MemoryStatusHistory.memory_id == mid).all()
        assert any(h.new_state == MemoryState.deleted for h in hist)
    finally:
        db.close()
