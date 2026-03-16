"""
End-to-end integration test for mem0 Memory with PolarDB vector store.

Exercises the full mem0 workflow: Memory.from_config() → add → search →
get_all → get → update → delete → history → delete_all → reset.

Required environment variables:
    POLARDB_HOST       PolarDB MySQL hostname
    POLARDB_USER       Database user
    POLARDB_PASSWORD   Database password
    POLARDB_DATABASE   Database name
    OPENAI_API_KEY     OpenAI API key (for LLM + embedder)

Optional:
    POLARDB_PORT            Database port (default: 3306)
    OPENAI_BASE_URL         Custom OpenAI-compatible API base URL
    OPENAI_LLM_MODEL        LLM model name (default: gpt-4o)
    OPENAI_EMBEDDING_MODEL  Embedding model name (default: text-embedding-3-small)
    OPENAI_EMBEDDING_DIMS   Embedding dimensions (default: 1536)

Run:
    POLARDB_HOST=xxx POLARDB_USER=xxx POLARDB_PASSWORD=xxx \
    POLARDB_DATABASE=xxx OPENAI_API_KEY=sk-xxx \
    OPENAI_BASE_URL=https://your-endpoint/v1 \
    OPENAI_LLM_MODEL=gpt-4o \
    OPENAI_EMBEDDING_MODEL=text-embedding-3-small \
        python -m pytest tests/test_polardb_memory_e2e.py -v -s
"""

import os
import time
import uuid

import pytest

# ── skip conditions ──────────────────────────────────────────────────────────
_REQUIRED_ENV = ["POLARDB_HOST", "POLARDB_USER", "POLARDB_PASSWORD", "POLARDB_DATABASE", "OPENAI_API_KEY"]
_MISSING = [v for v in _REQUIRED_ENV if not os.environ.get(v)]

pytestmark = pytest.mark.skipif(
    len(_MISSING) > 0,
    reason=f"E2E test requires env vars: {', '.join(_MISSING)}",
)

# ── helpers ──────────────────────────────────────────────────────────────────
_COLLECTION = f"mem0_e2e_{uuid.uuid4().hex[:8]}"
_USER_ID = f"test_user_{uuid.uuid4().hex[:6]}"
# PolarDB IMCI columnar engine may have a brief sync delay after writes
_IMCI_SYNC_WAIT = 2

_BASE_URL = os.environ.get("OPENAI_BASE_URL")
_LLM_MODEL = os.environ.get("OPENAI_LLM_MODEL", "gpt-4o")
_EMBEDDING_MODEL = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
_EMBEDDING_DIMS = int(os.environ.get("OPENAI_EMBEDDING_DIMS", "1536"))


def _make_config() -> dict:
    llm_config = {"model": _LLM_MODEL}
    embedder_config = {"model": _EMBEDDING_MODEL}

    if _BASE_URL:
        llm_config["openai_base_url"] = _BASE_URL
        embedder_config["openai_base_url"] = _BASE_URL

    return {
        "llm": {
            "provider": "openai",
            "config": llm_config,
        },
        "embedder": {
            "provider": "openai",
            "config": embedder_config,
        },
        "vector_store": {
            "provider": "polardb",
            "config": {
                "host": os.environ.get("POLARDB_HOST"),
                "port": int(os.environ.get("POLARDB_PORT", "3306")),
                "user": os.environ.get("POLARDB_USER"),
                "password": os.environ.get("POLARDB_PASSWORD"),
                "database": os.environ.get("POLARDB_DATABASE"),
                "collection_name": _COLLECTION,
                "embedding_model_dims": _EMBEDDING_DIMS,
                "index_type": "FAISS_HNSW_FLAT",
            },
        },
    }


# ── fixtures ─────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def mem():
    """Create a Memory instance backed by PolarDB, tear down after all tests."""
    from mem0 import Memory

    m = Memory.from_config(_make_config())
    yield m
    # cleanup: drop the collection table
    try:
        m.vector_store.delete_col()
    except Exception:
        pass


# ── tests (ordered by name so they run sequentially) ─────────────────────────

class TestPolarDBMemoryE2E:
    """Full lifecycle tests for mem0 Memory + PolarDB."""

    # ── 1. add with infer=False (raw storage, no LLM) ───────────────────────

    def test_01_add_raw_messages(self, mem):
        """add() with infer=False stores messages directly without LLM."""
        result = mem.add(
            "I love science fiction movies, especially Interstellar.",
            user_id=_USER_ID,
            infer=False,
        )
        assert "results" in result
        assert len(result["results"]) >= 1
        first = result["results"][0]
        assert first["event"] == "ADD"
        assert first["id"]
        # save for later tests
        self.__class__._raw_memory_id = first["id"]
        time.sleep(_IMCI_SYNC_WAIT)

    # ── 2. get single memory ─────────────────────────────────────────────────

    def test_02_get_memory(self, mem):
        """get() retrieves a memory by ID."""
        memory = mem.get(self._raw_memory_id)
        assert memory is not None
        assert memory["id"] == self._raw_memory_id
        assert "science fiction" in memory["memory"].lower() or "interstellar" in memory["memory"].lower()

    # ── 3. get_all ───────────────────────────────────────────────────────────

    def test_03_get_all(self, mem):
        """get_all() returns at least the memory we just added."""
        result = mem.get_all(user_id=_USER_ID)
        assert "results" in result
        assert len(result["results"]) >= 1
        ids = [m["id"] for m in result["results"]]
        assert self._raw_memory_id in ids

    # ── 4. search ────────────────────────────────────────────────────────────

    def test_04_search(self, mem):
        """search() finds relevant memories by semantic similarity."""
        result = mem.search("What movies does the user like?", user_id=_USER_ID)
        assert "results" in result
        assert len(result["results"]) >= 1
        # the top result should mention sci-fi or interstellar
        top = result["results"][0]
        assert "science fiction" in top["memory"].lower() or "interstellar" in top["memory"].lower()

    # ── 5. add more raw messages for richer search ───────────────────────────

    def test_05_add_more_raw(self, mem):
        """Add a second memory to test multi-result search & filtering."""
        result = mem.add(
            "My favorite programming language is Python.",
            user_id=_USER_ID,
            metadata={"category": "tech"},
            infer=False,
        )
        assert len(result["results"]) >= 1
        self.__class__._tech_memory_id = result["results"][0]["id"]
        time.sleep(_IMCI_SYNC_WAIT)

    def test_06_search_returns_multiple(self, mem):
        """search() returns multiple results when relevant."""
        result = mem.search("Tell me about the user", user_id=_USER_ID, limit=10)
        assert len(result["results"]) >= 2

    # ── 6. update ────────────────────────────────────────────────────────────

    def test_07_update_memory(self, mem):
        """update() changes the content of an existing memory."""
        mem.update(self._tech_memory_id, "My favorite programming language is Rust.")

        updated = mem.get(self._tech_memory_id)
        assert updated is not None
        assert "rust" in updated["memory"].lower()
        time.sleep(_IMCI_SYNC_WAIT)

    # ── 7. history ───────────────────────────────────────────────────────────

    def test_08_history(self, mem):
        """history() shows change log for a memory."""
        h = mem.history(self._tech_memory_id)
        assert isinstance(h, list)
        # should have at least ADD + UPDATE
        events = [entry.get("event") for entry in h]
        assert "ADD" in events
        assert "UPDATE" in events

    # ── 8. delete single ─────────────────────────────────────────────────────

    def test_09_delete_memory(self, mem):
        """delete() removes a specific memory."""
        result = mem.delete(self._tech_memory_id)
        assert "message" in result

        # verify it's gone
        deleted = mem.get(self._tech_memory_id)
        assert deleted is None
        time.sleep(_IMCI_SYNC_WAIT)

    def test_10_get_all_after_delete(self, mem):
        """After delete, get_all should have one fewer result."""
        result = mem.get_all(user_id=_USER_ID)
        ids = [m["id"] for m in result["results"]]
        assert self._tech_memory_id not in ids
        # the raw memory should still be there
        assert self._raw_memory_id in ids

    # ── 9. add with infer=True (LLM-powered fact extraction) ────────────────

    def test_11_add_with_inference(self, mem):
        """add() with infer=True uses LLM to extract facts from conversation."""
        messages = [
            {"role": "user", "content": "I just moved to Shanghai and I'm looking for good restaurants."},
            {"role": "assistant", "content": "Welcome to Shanghai! There are many great restaurants. Do you have any cuisine preferences?"},
            {"role": "user", "content": "I love Japanese food, especially sushi and ramen."},
        ]
        result = mem.add(messages, user_id=_USER_ID, metadata={"category": "food"})
        assert "results" in result
        # LLM should extract at least one fact
        if len(result["results"]) > 0:
            self.__class__._inferred_memory_ids = [r["id"] for r in result["results"]]
        else:
            self.__class__._inferred_memory_ids = []
        time.sleep(_IMCI_SYNC_WAIT)

    def test_12_search_inferred_memories(self, mem):
        """Search should find LLM-extracted facts."""
        result = mem.search("Where does the user live?", user_id=_USER_ID, limit=5)
        assert "results" in result
        # Should find something about Shanghai
        texts = " ".join(r["memory"].lower() for r in result["results"])
        assert "shanghai" in texts

    def test_13_search_food_preference(self, mem):
        """Search should surface food preference memories."""
        result = mem.search("What food does the user like?", user_id=_USER_ID, limit=5)
        assert "results" in result
        texts = " ".join(r["memory"].lower() for r in result["results"])
        assert "japanese" in texts or "sushi" in texts or "ramen" in texts

    # ── 10. add conversation with role context ───────────────────────────────

    def test_14_add_multi_turn_conversation(self, mem):
        """add() handles multi-turn conversations for fact extraction."""
        messages = [
            {"role": "user", "content": "I'm planning to watch a movie tonight. Any recommendations?"},
            {"role": "assistant", "content": "How about thriller movies? They can be quite engaging."},
            {"role": "user", "content": "I'm not a big fan of thriller movies but I love sci-fi movies."},
            {"role": "assistant", "content": "Got it! I'll suggest sci-fi movies in the future."},
        ]
        result = mem.add(messages, user_id=_USER_ID, metadata={"category": "movies"})
        assert "results" in result
        time.sleep(_IMCI_SYNC_WAIT)

    def test_15_search_movie_preferences(self, mem):
        """Verify movie preferences are stored and searchable."""
        result = mem.search("movie preferences", user_id=_USER_ID, limit=5)
        assert "results" in result
        texts = " ".join(r["memory"].lower() for r in result["results"])
        assert "sci-fi" in texts or "science fiction" in texts or "movie" in texts

    # ── 11. delete_all for user ──────────────────────────────────────────────

    def test_16_delete_all(self, mem):
        """delete_all() removes all memories for a user."""
        result = mem.delete_all(user_id=_USER_ID)
        assert "message" in result

        time.sleep(_IMCI_SYNC_WAIT)

        all_mems = mem.get_all(user_id=_USER_ID)
        assert len(all_mems["results"]) == 0

    # ── 12. reset (full table wipe) ──────────────────────────────────────────

    def test_17_add_after_delete_all(self, mem):
        """Verify we can still add memories after delete_all."""
        result = mem.add(
            "Testing post-delete-all insertion",
            user_id=_USER_ID,
            infer=False,
        )
        assert len(result["results"]) >= 1
        self.__class__._post_delete_id = result["results"][0]["id"]
        time.sleep(_IMCI_SYNC_WAIT)

    def test_18_reset(self, mem):
        """reset() clears all data from the collection."""
        mem.reset()

        # after reset, the same collection should be empty
        # (add a new memory to prove the table was recreated)
        result = mem.add(
            "Fresh start after reset",
            user_id=_USER_ID,
            infer=False,
        )
        assert len(result["results"]) >= 1

        time.sleep(_IMCI_SYNC_WAIT)
        all_mems = mem.get_all(user_id=_USER_ID)
        # should have only the one we just added
        assert len(all_mems["results"]) == 1
        assert "fresh start" in all_mems["results"][0]["memory"].lower()
