import builtins
import importlib.util
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("lancedb")

from mem0.vector_stores.configs import VectorStoreConfig
from mem0.vector_stores.lancedb import LanceDB
from mem0.utils.factory import VectorStoreFactory


def test_lancedb_import_error_mentions_vector_stores_extra(monkeypatch):
    real_import = builtins.__import__

    def fail_lancedb_import(name, *args, **kwargs):
        if name == "lancedb":
            raise ImportError("No module named 'lancedb'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_lancedb_import)
    module_path = Path(__file__).parents[2] / "mem0" / "vector_stores" / "lancedb.py"
    spec = importlib.util.spec_from_file_location("missing_lancedb_test_module", module_path)
    module = importlib.util.module_from_spec(spec)

    with pytest.raises(ImportError, match="mem0ai\\[vector-stores\\]"):
        spec.loader.exec_module(module)


@pytest.fixture
def populated_filter_store(tmp_path):
    store = LanceDB(
        collection_name="filter_memories",
        path=str(tmp_path),
        embedding_model_dims=2,
        distance="cosine",
    )
    store.insert(
        vectors=[[1.0, 0.0], [0.9, 0.1], [0.8, 0.2]],
        ids=["m1", "m2", "m3"],
        payloads=[
            {"user_id": "alice", "score": 7, "name": "Alice Garden", "category": "work"},
            {"user_id": "bob", "score": 3, "name": "Bob Farm", "category": "personal"},
            {"user_id": "carol", "score": 10, "name": "ALICE archive"},
        ],
    )
    return store


def test_lancedb_config_accepts_local_settings():
    config = VectorStoreConfig(
        provider="lancedb",
        config={
            "path": "/tmp/lancedb",
            "collection_name": "memories",
            "embedding_model_dims": 3,
            "distance": "cosine",
        },
    )

    assert config.provider == "lancedb"
    assert config.config.path == "/tmp/lancedb"
    assert config.config.collection_name == "memories"
    assert config.config.embedding_model_dims == 3
    assert config.config.distance == "cosine"


def test_lancedb_factory_creates_a_persistent_store(tmp_path):
    config = VectorStoreConfig(
        provider="lancedb",
        config={
            "path": str(tmp_path),
            "collection_name": "factory_memories",
            "embedding_model_dims": 2,
            "distance": "cosine",
        },
    )

    store = VectorStoreFactory.create("lancedb", config.config)

    assert isinstance(store, LanceDB)
    assert store.col_info() == {
        "name": "factory_memories",
        "count": 0,
        "dimension": 2,
        "distance": "cosine",
    }


@pytest.mark.parametrize("embedding_model_dims", [0, -1])
def test_lancedb_config_rejects_non_positive_embedding_dimensions(embedding_model_dims):
    with pytest.raises(ValueError, match="greater than 0"):
        VectorStoreConfig(
            provider="lancedb",
            config={"embedding_model_dims": embedding_model_dims},
        )


@pytest.mark.parametrize("embedding_model_dims", [0, -1])
def test_lancedb_rejects_non_positive_embedding_dimensions_when_constructed_directly(tmp_path, embedding_model_dims):
    with pytest.raises(ValueError, match="embedding_model_dims must be a positive integer"):
        LanceDB(
            collection_name="invalid_dimension_memories",
            path=str(tmp_path),
            embedding_model_dims=embedding_model_dims,
        )


def test_lancedb_crud_search_and_filters():
    with tempfile.TemporaryDirectory() as temp_dir:
        store = LanceDB(
            collection_name="memories",
            path=temp_dir,
            embedding_model_dims=3,
            distance="cosine",
        )

        store.insert(
            vectors=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.9, 0.1, 0.0]],
            ids=["m1", "m2", "m3"],
            payloads=[
                {"user_id": "alice", "memory": "likes drip irrigation"},
                {"user_id": "bob", "memory": "likes flood irrigation"},
                {"user_id": "alice", "memory": "prefers morning reminders"},
            ],
        )

        info = store.col_info()
        assert info["name"] == "memories"
        assert info["count"] == 3
        assert info["dimension"] == 3
        assert info["distance"] == "cosine"

        results = store.search(query="", vectors=[1.0, 0.0, 0.0], top_k=2)
        assert [result.id for result in results] == ["m1", "m3"]
        assert results[0].score == pytest.approx(1.0)

        filtered = store.search(
            query="",
            vectors=[0.0, 1.0, 0.0],
            top_k=3,
            filters={"user_id": "alice"},
        )
        assert filtered
        assert all(result.payload["user_id"] == "alice" for result in filtered)

        assert store.get("m1").payload["memory"] == "likes drip irrigation"

        store.update("m1", payload={"user_id": "alice", "memory": "updated memory"})
        assert store.get("m1").payload["memory"] == "updated memory"

        store.update("m2", vector=[1.0, 0.0, 0.0], payload={"user_id": "bob", "memory": "updated vector"})
        moved = store.search(query="", vectors=[1.0, 0.0, 0.0], top_k=2)
        assert "m2" in [result.id for result in moved]

        listed = store.list(top_k=10)[0]
        assert sorted(result.id for result in listed) == ["m1", "m2", "m3"]

        store.delete("m3")
        listed_after_delete = store.list(top_k=10)[0]
        assert sorted(result.id for result in listed_after_delete) == ["m1", "m2"]

        store.reset()
        assert store.col_info()["count"] == 0


def test_lancedb_reopens_an_existing_collection(tmp_path):
    first = LanceDB(
        collection_name="persisted_memories",
        path=str(tmp_path),
        embedding_model_dims=2,
        distance="cosine",
    )
    first.insert(vectors=[[1.0, 0.0]], ids=["m1"], payloads=[{"value": "persisted"}])

    reopened = LanceDB(
        collection_name="persisted_memories",
        path=str(tmp_path),
        embedding_model_dims=2,
        distance="cosine",
    )

    assert reopened.get("m1").payload == {"value": "persisted"}


def test_lancedb_list_cols_returns_all_collection_names(tmp_path):
    expected_names = [f"memories_{index:02d}" for index in range(12)]
    store = None
    for name in expected_names:
        store = LanceDB(
            collection_name=name,
            path=str(tmp_path),
            embedding_model_dims=2,
            distance="cosine",
        )

    assert store.list_cols() == expected_names


def test_lancedb_delete_col_removes_the_collection(tmp_path):
    store = LanceDB(
        collection_name="deleted_memories",
        path=str(tmp_path),
        embedding_model_dims=2,
        distance="cosine",
    )

    store.delete_col()

    assert store.table is None
    assert "deleted_memories" not in store.list_cols()


def test_lancedb_create_col_switches_the_active_collection(tmp_path):
    store = LanceDB(
        collection_name="first_memories",
        path=str(tmp_path),
        embedding_model_dims=2,
        distance="cosine",
    )
    store.insert(vectors=[[1.0, 0.0]], ids=["first"], payloads=[{"collection": "first"}])

    store.create_col("second_memories")
    store.insert(vectors=[[0.0, 1.0]], ids=["second"], payloads=[{"collection": "second"}])

    assert store.col_info()["name"] == "second_memories"
    assert store.col_info()["count"] == 1
    assert store.get("second").payload == {"collection": "second"}
    assert store.client.open_table("first_memories").count_rows() == 1


def test_lancedb_rejects_existing_collection_dimension_mismatch(tmp_path):
    LanceDB(
        collection_name="dimensioned_memories",
        path=str(tmp_path),
        embedding_model_dims=2,
        distance="cosine",
    )

    with pytest.raises(ValueError, match="uses embedding dimension 2.*requested 3"):
        LanceDB(
            collection_name="dimensioned_memories",
            path=str(tmp_path),
            embedding_model_dims=3,
            distance="cosine",
        )


def test_lancedb_failed_collection_switch_preserves_the_active_collection(tmp_path):
    store = LanceDB(
        collection_name="stable_memories",
        path=str(tmp_path),
        embedding_model_dims=2,
        distance="cosine",
    )
    store.insert(vectors=[[1.0, 0.0]], ids=["m1"], payloads=[{"stable": True}])

    with pytest.raises(ValueError, match="uses embedding dimension 2.*requested 3"):
        store.create_col("stable_memories", vector_size=3, distance="l2")

    assert store.col_info() == {
        "name": "stable_memories",
        "count": 1,
        "dimension": 2,
        "distance": "cosine",
    }
    assert store.get("m1").payload == {"stable": True}


def test_lancedb_dot_distance_similarity_direction():
    with tempfile.TemporaryDirectory() as temp_dir:
        store = LanceDB(
            collection_name="memories",
            path=temp_dir,
            embedding_model_dims=3,
            distance="dot",
        )

        store.insert(
            vectors=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            ids=["perfect", "orthogonal"],
        )

        results = store.search(query="", vectors=[1.0, 0.0, 0.0], top_k=2)
        assert results[0].id == "perfect"
        assert results[0].score > results[1].score
        assert results[0].score == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("filters", "expected_ids"),
    [
        ({"$or": [{"user_id": "alice"}, {"score": {"lt": 4}}]}, {"m1", "m2"}),
        ({"$not": [{"user_id": "bob"}]}, {"m1", "m3"}),
        ({"user_id": "alice", "score": {"gte": 7}}, {"m1"}),
        ({"category": "*"}, {"m1", "m2"}),
        ({"score": {"eq": 7}}, {"m1"}),
        ({"score": {"ne": 7}}, {"m2", "m3"}),
        ({"score": {"gt": 6}}, {"m1", "m3"}),
        ({"score": {"gte": 7}}, {"m1", "m3"}),
        ({"score": {"lt": 7}}, {"m2"}),
        ({"score": {"lte": 7}}, {"m1", "m2"}),
        ({"user_id": {"in": ["alice", "carol"]}}, {"m1", "m3"}),
        ({"user_id": {"nin": ["alice", "carol"]}}, {"m2"}),
        ({"name": {"contains": "Alice"}}, {"m1"}),
        ({"name": {"icontains": "alice"}}, {"m1", "m3"}),
        ({"user_id": ["alice", "carol"]}, {"m1", "m3"}),
    ],
)
def test_lancedb_search_supports_processed_metadata_filters(populated_filter_store, filters, expected_ids):
    results = populated_filter_store.search(
        query="",
        vectors=[1.0, 0.0],
        top_k=10,
        filters=filters,
    )

    assert {result.id for result in results} == expected_ids


def test_lancedb_list_supports_processed_metadata_filters(populated_filter_store):
    results = populated_filter_store.list(
        filters={"$or": [{"user_id": "alice"}, {"score": {"gt": 9}}]},
        top_k=10,
    )[0]

    assert {result.id for result in results} == {"m1", "m3"}


@pytest.mark.parametrize(
    "filters",
    [
        {"user_id": "alice", "AND": [{"score": {"gte": 7}}, {"category": "work"}]},
        {"user_id": "alice", "OR": [{"category": "work"}, {"score": {"gt": 9}}]},
        {"user_id": "alice", "NOT": [{"category": "personal"}]},
    ],
)
def test_lancedb_list_supports_unprocessed_logical_filter_aliases(populated_filter_store, filters):
    results = populated_filter_store.list(filters=filters, top_k=10)[0]

    assert {result.id for result in results} == {"m1"}


def test_lancedb_not_matches_payloads_missing_the_negated_field(tmp_path):
    store = LanceDB(
        collection_name="missing_field_memories",
        path=str(tmp_path),
        embedding_model_dims=2,
        distance="cosine",
    )
    store.insert(
        vectors=[[1.0, 0.0], [0.0, 1.0]],
        ids=["missing", "work"],
        payloads=[{}, {"category": "work"}],
    )

    results = store.list(filters={"$not": [{"category": "work"}]}, top_k=10)[0]

    assert {result.id for result in results} == {"missing"}


def test_lancedb_search_returns_no_results_when_top_k_is_zero(populated_filter_store):
    results = populated_filter_store.search(query="", vectors=[1.0, 0.0], top_k=0)

    assert results == []


def test_lancedb_list_returns_no_results_when_top_k_is_zero(populated_filter_store):
    results = populated_filter_store.list(top_k=0)

    assert results == [[]]


@pytest.mark.parametrize("top_k", [-1, 1.5, None, True])
@pytest.mark.parametrize("operation", ["search", "list"])
def test_lancedb_rejects_invalid_top_k_before_querying_an_empty_table(tmp_path, operation, top_k):
    store = LanceDB(
        collection_name="invalid_top_k_memories",
        path=str(tmp_path),
        embedding_model_dims=2,
        distance="cosine",
    )

    with pytest.raises(ValueError, match="top_k must be a non-negative integer"):
        if operation == "search":
            store.search(query="", vectors=[1.0, 0.0], top_k=top_k)
        else:
            store.list(top_k=top_k)


@pytest.mark.parametrize("operation", ["search", "list"])
def test_lancedb_rejects_non_dictionary_filters_even_when_empty(tmp_path, operation):
    store = LanceDB(
        collection_name="invalid_filter_type_memories",
        path=str(tmp_path),
        embedding_model_dims=2,
        distance="cosine",
    )

    with pytest.raises(ValueError, match="Filters must be a dictionary"):
        if operation == "search":
            store.search(query="", vectors=[1.0, 0.0], filters=[])
        else:
            store.list(filters=[])


@pytest.mark.parametrize("filters", [None, {"user_id": "alice"}])
def test_lancedb_rejects_invalid_query_vector_before_searching_an_empty_table(tmp_path, filters):
    store = LanceDB(
        collection_name="invalid_query_vector_memories",
        path=str(tmp_path),
        embedding_model_dims=2,
        distance="cosine",
    )

    with pytest.raises(ValueError, match="Vector has dimension 3.*expects 2"):
        store.search(query="", vectors=[1.0, 0.0, 0.0], filters=filters)


def test_lancedb_search_expands_recall_until_top_k_filtered_results_are_found(tmp_path):
    store = LanceDB(
        collection_name="recall_memories",
        path=str(tmp_path),
        embedding_model_dims=2,
        distance="cosine",
    )
    excluded_count = 55
    matching_ids = ["match-1", "match-2", "match-3"]
    store.insert(
        vectors=[[1.0, 0.0] for _ in range(excluded_count)] + [[0.0, 1.0] for _ in matching_ids],
        ids=[f"excluded-{index}" for index in range(excluded_count)] + matching_ids,
        payloads=[{"user_id": "bob"} for _ in range(excluded_count)] + [{"user_id": "alice"} for _ in matching_ids],
    )

    results = store.search(
        query="",
        vectors=[1.0, 0.0],
        top_k=len(matching_ids),
        filters={"user_id": "alice"},
    )

    assert {result.id for result in results} == set(matching_ids)


def test_lancedb_search_rejects_unknown_filter_operator(populated_filter_store):
    with pytest.raises(ValueError, match="Unsupported filter operator"):
        populated_filter_store.search(
            query="",
            vectors=[1.0, 0.0],
            top_k=3,
            filters={"score": {"between": [3, 7]}},
        )


@pytest.mark.parametrize("operation", ["search", "list"])
def test_lancedb_rejects_unknown_filter_operator_when_table_is_empty(tmp_path, operation):
    store = LanceDB(
        collection_name="empty_filter_memories",
        path=str(tmp_path),
        embedding_model_dims=2,
        distance="cosine",
    )
    filters = {"score": {"between": [3, 7]}}

    with pytest.raises(ValueError, match="Unsupported filter operator"):
        if operation == "search":
            store.search(query="", vectors=[1.0, 0.0], top_k=3, filters=filters)
        else:
            store.list(filters=filters, top_k=3)


@pytest.mark.parametrize(
    ("filters", "error"),
    [
        ({"score": {}}, "must not be empty"),
        ({"user_id": {"in": "alice,bob"}}, "requires a non-empty list"),
        ({"user_id": {"nin": []}}, "requires a non-empty list"),
        ({"name": {"contains": 1}}, "requires a string value"),
        ({"score": {"gt": [6]}}, "requires a scalar value"),
        ({"score": {"gte": None}}, "does not support null"),
    ],
)
def test_lancedb_rejects_invalid_filter_operands(populated_filter_store, filters, error):
    with pytest.raises(ValueError, match=error):
        populated_filter_store.list(filters=filters, top_k=10)


def test_lancedb_update_missing_id_is_a_noop(tmp_path):
    store = LanceDB(
        collection_name="update_memories",
        path=str(tmp_path),
        embedding_model_dims=2,
        distance="cosine",
    )

    store.update("missing", payload={"user_id": "alice"})

    assert store.col_info()["count"] == 0


@pytest.mark.parametrize(
    ("vector", "payload", "error"),
    [
        ([1.0, 0.0, 0.0], {"safe": False}, ValueError),
        (["not-a-number", 0.0], {"safe": False}, ValueError),
        ([0.0, 1.0], {"bad": {1, 2}}, TypeError),
    ],
)
def test_lancedb_failed_vector_update_preserves_the_existing_record(tmp_path, vector, payload, error):
    store = LanceDB(
        collection_name="safe_update_memories",
        path=str(tmp_path),
        embedding_model_dims=2,
        distance="cosine",
    )
    store.insert(vectors=[[1.0, 0.0]], ids=["m1"], payloads=[{"safe": True}])

    with pytest.raises(error):
        store.update("m1", vector=vector, payload=payload)

    assert store.get("m1").payload == {"safe": True}


def test_lancedb_vector_only_update_preserves_the_existing_payload(tmp_path):
    store = LanceDB(
        collection_name="vector_only_update_memories",
        path=str(tmp_path),
        embedding_model_dims=2,
        distance="cosine",
    )
    store.insert(vectors=[[1.0, 0.0]], ids=["m1"], payloads=[{"safe": True}])

    store.update("m1", vector=[0.0, 1.0])

    assert store.get("m1").payload == {"safe": True}
    assert store.search(query="", vectors=[0.0, 1.0], top_k=1)[0].id == "m1"


@pytest.mark.parametrize("payload", [[], ["invalid"], "invalid", 1])
def test_lancedb_insert_rejects_non_dictionary_payloads(tmp_path, payload):
    store = LanceDB(
        collection_name="invalid_insert_payload_memories",
        path=str(tmp_path),
        embedding_model_dims=2,
        distance="cosine",
    )

    with pytest.raises(TypeError, match="Payload must be a dictionary or None"):
        store.insert(vectors=[[1.0, 0.0]], ids=["m1"], payloads=[payload])

    assert store.col_info()["count"] == 0


@pytest.mark.parametrize("payload", [[], ["invalid"], "invalid", 1])
def test_lancedb_update_rejects_non_dictionary_payloads_without_modifying_the_record(tmp_path, payload):
    store = LanceDB(
        collection_name="invalid_update_payload_memories",
        path=str(tmp_path),
        embedding_model_dims=2,
        distance="cosine",
    )
    store.insert(vectors=[[1.0, 0.0]], ids=["m1"], payloads=[{"safe": True}])

    with pytest.raises(TypeError, match="Payload must be a dictionary or None"):
        store.update("m1", payload=payload)

    assert store.get("m1").payload == {"safe": True}


def test_lancedb_reads_legacy_non_dictionary_payload_as_empty_metadata(tmp_path, caplog):
    store = LanceDB(
        collection_name="legacy_payload_memories",
        path=str(tmp_path),
        embedding_model_dims=2,
        distance="cosine",
    )
    store.table.add([{"id": "m1", "vector": [1.0, 0.0], "payload": '["legacy"]'}])

    result = store.get("m1")

    assert result.payload == {}
    assert "must decode to a dictionary" in caplog.text
