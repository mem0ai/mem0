import os
import tempfile

import pytest

from mem0.vector_stores.sqlite_vec import OutputData, SQLiteVec


@pytest.fixture(params=[True, False], ids=["inline", "separate"])
def sqlite_vec_instance(request):
    """Parametrized fixture covering both inline_payload modes."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test_collection.db")
        store = SQLiteVec(
            collection_name="test_collection",
            path=db_path,
            embedding_model_dims=4,
            inline_payload=request.param,
        )
        yield store
        try:
            store._conn.close()
        except Exception:
            pass


@pytest.fixture
def populated_store(sqlite_vec_instance):
    """Populated store for both inline_payload modes."""
    store = sqlite_vec_instance
    store.insert(
        vectors=[[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8], [0.9, 1.0, 1.1, 1.2]],
        payloads=[
            {"user_id": "u1", "text": "hello", "category": "A"},
            {"user_id": "u2", "text": "world", "category": "B"},
            {"user_id": "u1", "text": "foo", "category": "A"},
        ],
        ids=["id1", "id2", "id3"],
    )
    return store


class TestCreateCol:
    def test_create_col_default(self, sqlite_vec_instance):
        """Creating a collection should set the collection name."""
        store = sqlite_vec_instance
        assert store.col_info()["name"] == "test_collection"
        assert store.col_info()["count"] == 0

    def test_create_col_explicit(self, sqlite_vec_instance):
        """create_col with explicit name should update collection name."""
        store = sqlite_vec_instance
        store.create_col(name="new_collection")
        assert store.collection_name == "new_collection"


class TestInsert:
    def test_insert_basic(self, sqlite_vec_instance):
        """Insert vectors should store them and return correct count."""
        store = sqlite_vec_instance
        store.insert(
            vectors=[[0.1, 0.2, 0.3, 0.4]],
            payloads=[{"key": "value"}],
            ids=["id1"],
        )
        assert store.col_info()["count"] == 1

    def test_insert_multiple(self, sqlite_vec_instance):
        """Insert multiple vectors at once."""
        store = sqlite_vec_instance
        store.insert(
            vectors=[[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]],
            payloads=[{"n": 1}, {"n": 2}],
            ids=["id1", "id2"],
        )
        assert store.col_info()["count"] == 2

    def test_insert_auto_generates_ids(self, sqlite_vec_instance):
        """Insert without IDs should auto-generate UUIDs."""
        store = sqlite_vec_instance
        store.insert(
            vectors=[[0.1, 0.2, 0.3, 0.4]],
            payloads=[{"key": "value"}],
        )
        assert store.col_info()["count"] == 1
        # Verify the auto-generated ID is retrievable
        results = store.list()
        assert len(results[0]) == 1
        assert results[0][0].id is not None

    def test_insert_auto_generates_payloads(self, sqlite_vec_instance):
        """Insert without payloads should default to empty dicts."""
        store = sqlite_vec_instance
        store.insert(
            vectors=[[0.1, 0.2, 0.3, 0.4]],
            ids=["id1"],
        )
        result = store.get("id1")
        assert result.payload == {}

    def test_insert_mismatched_lengths_raises(self, sqlite_vec_instance):
        """Mismatched vector/ID/payload lengths should raise ValueError."""
        store = sqlite_vec_instance
        with pytest.raises(ValueError, match="must have the same length"):
            store.insert(
                vectors=[[0.1, 0.2], [0.3, 0.4]],
                ids=["id1"],
                payloads=[{}, {}],
            )


class TestSearch:
    def test_search_returns_results(self, populated_store):
        """Search should return results ordered by similarity."""
        results = populated_store.search(
            query="test",
            vectors=[[0.1, 0.2, 0.3, 0.4]],
            top_k=3,
        )
        assert len(results) == 3
        # id1 should be closest (exact match)
        assert results[0].id == "id1"
        assert results[0].score == pytest.approx(1.0, abs=0.01)

    def test_search_respects_top_k(self, populated_store):
        """Search should respect the top_k limit."""
        results = populated_store.search(
            query="test",
            vectors=[[0.1, 0.2, 0.3, 0.4]],
            top_k=1,
        )
        assert len(results) == 1

    def test_search_scores_are_between_0_and_1(self, populated_store):
        """Similarity scores should be in [0, 1] range."""
        results = populated_store.search(
            query="test",
            vectors=[[0.1, 0.2, 0.3, 0.4]],
            top_k=3,
        )
        for r in results:
            assert 0.0 <= r.score <= 1.0

    def test_search_returns_output_data(self, populated_store):
        """Search results should be OutputData instances with correct fields."""
        results = populated_store.search(
            query="test",
            vectors=[[0.1, 0.2, 0.3, 0.4]],
            top_k=1,
        )
        assert isinstance(results[0], OutputData)
        assert results[0].id is not None
        assert results[0].score is not None
        assert isinstance(results[0].payload, dict)


class TestSearchWithFilters:
    def test_search_filter_exact_match(self, populated_store):
        """Filter should narrow results to matching payload values."""
        results = populated_store.search(
            query="test",
            vectors=[[0.1, 0.2, 0.3, 0.4]],
            top_k=3,
            filters={"user_id": "u1"},
        )
        assert len(results) == 2
        for r in results:
            assert r.payload["user_id"] == "u1"

    def test_search_filter_single_result(self, populated_store):
        """Filter should return only matching results."""
        results = populated_store.search(
            query="test",
            vectors=[[0.1, 0.2, 0.3, 0.4]],
            top_k=3,
            filters={"user_id": "u2"},
        )
        assert len(results) == 1
        assert results[0].id == "id2"

    def test_search_filter_no_match(self, populated_store):
        """Filter with no matches should return empty list."""
        results = populated_store.search(
            query="test",
            vectors=[[0.1, 0.2, 0.3, 0.4]],
            top_k=3,
            filters={"user_id": "nonexistent"},
        )
        assert len(results) == 0

    def test_search_filter_list_value(self, populated_store):
        """Filter with list value should match IN condition."""
        results = populated_store.search(
            query="test",
            vectors=[[0.1, 0.2, 0.3, 0.4]],
            top_k=3,
            filters={"category": ["A", "C"]},
        )
        assert len(results) == 2
        for r in results:
            assert r.payload["category"] == "A"

    def test_search_filter_none_value(self, sqlite_vec_instance):
        """Filter with None value should match empty string (vec0 TEXT columns cannot be NULL)."""
        store = sqlite_vec_instance
        store.insert(
            vectors=[[0.1, 0.2, 0.3, 0.4]],
            payloads=[{"user_id": ""}],
            ids=["id_empty"],
        )
        results = store.search(
            query="test",
            vectors=[[0.1, 0.2, 0.3, 0.4]],
            top_k=1,
            filters={"user_id": ""},
        )
        assert len(results) == 1
        assert results[0].id == "id_empty"


class TestDelete:
    def test_delete_existing(self, populated_store):
        """Delete should remove an existing vector."""
        populated_store.delete("id1")
        assert populated_store.col_info()["count"] == 2
        assert populated_store.get("id1") is None

    def test_delete_nonexistent(self, populated_store):
        """Delete on non-existent ID should not raise or change count."""
        populated_store.delete("nonexistent")
        assert populated_store.col_info()["count"] == 3

    def test_delete_all_and_reinsert(self, populated_store):
        """After deleting all, insert should still work."""
        populated_store.delete("id1")
        populated_store.delete("id2")
        populated_store.delete("id3")
        assert populated_store.col_info()["count"] == 0

        populated_store.insert(
            vectors=[[0.1, 0.2, 0.3, 0.4]],
            payloads=[{"key": "new"}],
            ids=["new_id"],
        )
        assert populated_store.col_info()["count"] == 1
        assert populated_store.get("new_id") is not None


class TestUpdate:
    def test_update_payload_and_vector(self, populated_store):
        """Update should modify both payload and vector."""
        populated_store.update(
            "id1",
            vector=[0.9, 0.8, 0.7, 0.6],
            payload={"user_id": "u1", "text": "updated"},
        )
        result = populated_store.get("id1")
        assert result.payload == {"user_id": "u1", "text": "updated"}

    def test_update_vector_only(self, populated_store):
        """Update should modify only the vector."""
        new_vector = [0.9, 0.8, 0.7, 0.6]
        populated_store.update("id1", vector=new_vector)
        # After update, the vector should be closer to [0.9, 0.8, 0.7, 0.6]
        results = populated_store.search(
            query="test",
            vectors=[[0.9, 0.8, 0.7, 0.6]],
            top_k=1,
        )
        assert results[0].id == "id1"
        assert results[0].score > 0.99

    def test_update_nonexistent_raises(self, populated_store):
        """Update on non-existent ID should raise ValueError."""
        with pytest.raises(ValueError, match="not found"):
            populated_store.update("nonexistent", payload={"key": "value"})


class TestGet:
    def test_get_existing(self, populated_store):
        """Get should return the correct vector by ID."""
        result = populated_store.get("id1")
        assert result is not None
        assert result.id == "id1"
        assert result.payload == {"user_id": "u1", "text": "hello", "category": "A"}
        assert result.score is None

    def test_get_nonexistent(self, populated_store):
        """Get on non-existent ID should return None."""
        result = populated_store.get("nonexistent")
        assert result is None


class TestList:
    def test_list_all(self, populated_store):
        """List should return all vectors."""
        results = populated_store.list()
        assert len(results[0]) == 3

    def test_list_with_limit(self, populated_store):
        """List should respect top_k limit."""
        results = populated_store.list(top_k=2)
        assert len(results[0]) == 2

    def test_list_with_filters(self, populated_store):
        """List should filter results by metadata."""
        results = populated_store.list(filters={"user_id": "u1"})
        assert len(results[0]) == 2
        for r in results[0]:
            assert r.payload["user_id"] == "u1"

    def test_list_with_filters_no_match(self, populated_store):
        """List with non-matching filter should return empty."""
        results = populated_store.list(filters={"user_id": "nonexistent"})
        assert len(results[0]) == 0

    def test_list_empty_store(self, sqlite_vec_instance):
        """List on empty store should return empty."""
        results = sqlite_vec_instance.list()
        assert len(results[0]) == 0


class TestColInfo:
    def test_col_info_empty(self, sqlite_vec_instance):
        """col_info on empty store should report zero count."""
        info = sqlite_vec_instance.col_info()
        assert info["name"] == "test_collection"
        assert info["count"] == 0
        assert info["dimension"] == 4
        assert info["distance"] == "cosine"

    def test_col_info_populated(self, populated_store):
        """col_info should reflect the actual count."""
        info = populated_store.col_info()
        assert info["count"] == 3
        assert info["dimension"] == 4


class TestDeleteCol:
    def test_delete_col_removes_data(self, populated_store):
        """delete_col should remove the database file."""
        db_path = populated_store._db_path
        populated_store.delete_col()
        assert not os.path.exists(db_path)


class TestReset:
    def test_reset_clears_all_data(self, populated_store):
        """Reset should clear all data and allow re-insertion."""
        populated_store.reset()
        assert populated_store.col_info()["count"] == 0

        # Should be able to insert after reset
        populated_store.insert(
            vectors=[[0.1, 0.2, 0.3, 0.4]],
            payloads=[{"key": "after_reset"}],
            ids=["new_id"],
        )
        assert populated_store.col_info()["count"] == 1
        assert populated_store.get("new_id") is not None


class TestSearchBatch:
    def test_search_batch(self, populated_store):
        """search_batch should return results for multiple queries."""
        results = populated_store.search_batch(
            queries=["q1", "q2"],
            vectors_list=[[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]],
            top_k=1,
        )
        assert len(results) == 2
        assert len(results[0]) == 1
        assert len(results[1]) == 1


class TestListCols:
    def test_list_cols(self, sqlite_vec_instance):
        """list_cols should return the collection name."""
        cols = sqlite_vec_instance.list_cols()
        assert "test_collection" in cols


class TestOutputData:
    def test_output_data_fields(self):
        """OutputData should have id, score, and payload fields."""
        data = OutputData(id="test_id", score=0.95, payload={"key": "value"})
        assert data.id == "test_id"
        assert data.score == 0.95
        assert data.payload == {"key": "value"}

    def test_output_data_optional_fields(self):
        """OutputData fields should allow None values."""
        data = OutputData(id=None, score=None, payload=None)
        assert data.id is None
        assert data.score is None
        assert data.payload is None