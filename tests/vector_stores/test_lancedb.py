"""Integration tests against a local LanceDB database."""
import json
from importlib import import_module

import pytest

lancedb = pytest.importorskip("lancedb")
pa = pytest.importorskip("pyarrow")

LanceDB = import_module("mem0.vector_stores.lancedb").LanceDB


def test_native_prefilter_and_payload_lifecycle(tmp_path):
    store = LanceDB(path=str(tmp_path), embedding_model_dims=2)
    owner = "me' OR true --"
    vectors = [[1.0, 0.0]] * 55 + [[0.8, 0.6]]
    payloads = [{"user_id": "other", "n": i} for i in range(55)] + [
        {"user_id": owner, "n": 3, "nullable": None, "label": "Green field", "tags": ["rice", "water"]}
    ]
    store.insert(vectors, payloads=payloads, ids=[str(i) for i in range(56)])
    filters = {
        "user_id": owner,
        "AND": [
            {"n": {"gte": 3}}, {"label": {"icontains": "FIELD"}}, {"tags": {"contains": "rice"}},
            {"nullable": {"eq": None}}, {"missing": {"ne": 9}},
        ],
    }
    assert store.search("", [1.0, 0.0], top_k=1, filters=filters) == []
    filters["AND"].pop()
    assert [row.id for row in store.search("", [1.0, 0.0], top_k=1, filters=filters)] == ["55"]
    assert [row.id for row in store.list(filters={"user_id": owner, "NOT": [{"n": {"lt": 3}}]})[0]] == ["55"]
    store.update("55", payload={"user_id": owner, "n": 4})
    assert not store.list(filters={"user_id": owner, "n": 3})[0]
    assert store.list(filters={"user_id": owner, "n": 4})[0][0].id == "55"
    reopened = LanceDB(path=str(tmp_path), embedding_model_dims=2)
    assert reopened.get("55").payload["n"] == 4
    reopened.delete("55")
    assert reopened.get("55") is None


@pytest.mark.parametrize(
    "filters, expected",
    [
        ({"n": {"gt": 3, "lte": 5}}, {"b", "c"}),
        ({"n": {"in": [3, 5]}}, {"a", "c"}),
        ({"n": {"nin": [3, 5]}}, {"b"}),
        ({"null": {"ne": None}}, {"c"}),
        ({"null": None}, {"a"}),
        ({"null": "*"}, {"a", "c"}),
        ({"text": {"contains": "it's"}}, {"a"}),
        ({"text": {"icontains": "RICE"}}, {"a"}),
        ({"tags": {"contains": "rice"}}, {"a"}),
        ({"map": {"contains": "rice"}}, {"a"}),
        ({"OR": [{"user_id": "a"}, {"user_id": "b"}], "NOT": [{"n": {"eq": 4}}]}, {"a"}),
        ({"$and": [{"n": {"gte": 3}}, {"$or": [{"user_id": "a"}, {"user_id": "b"}]}]}, {"a", "b"}),
        ({"$not": [{"null": None}]}, {"b", "c"}),
        ({"$and": []}, {"a", "b", "c"}),
        ({"$or": []}, set()),
        ({"$not": []}, {"a", "b", "c"}),
        ({"user_id') OR true --": "*"}, set()),
    ],
)
def test_native_filter_types_and_null_semantics(tmp_path, filters, expected):
    store = LanceDB(path=str(tmp_path), embedding_model_dims=2)
    store.insert(
        [[1.0, 0.0], [0.9, 0.1], [0.8, 0.2]],
        ids=["a", "b", "c"],
        payloads=[
            {"user_id": "a", "n": 3, "null": None, "text": "it's Rice", "tags": ["rice"], "map": {"rice": 1}},
            {"user_id": "b", "n": 4, "text": "none"},
            {"user_id": "c", "n": 5, "null": "value"},
        ],
    )
    assert {row.id for row in store.list(filters=filters)[0]} == expected


def test_large_numbers_and_json_normalization(tmp_path):
    store = LanceDB(path=str(tmp_path), embedding_model_dims=2)
    store.insert(
        [[1.0, 0.0], [0.9, 0.1]], ids=["plus", "minus"],
        payloads=[{"n": 2**63 + 1, "nested": {1: "x"}, "tags": ("rice",)}, {"n": -(2**63)}],
    )
    assert [row.id for row in store.list(filters={"n": {"gt": 2**53 - 1}})[0]] == ["plus"]
    assert [row.id for row in store.list(filters={"n": {"lt": -(2**53 - 1)}})[0]] == ["minus"]
    filters = {"nested": {"contains": "1"}, "tags": {"contains": "rice"}}
    assert [row.id for row in store.list(filters=filters)[0]] == ["plus"]


def test_failed_collection_open_keeps_current_state(tmp_path):
    store = LanceDB(path=str(tmp_path), embedding_model_dims=2)
    store.insert([[1.0, 0.0]], ids=["stable"], payloads=[{"user_id": "a"}])
    store.client.create_table(
        "other", schema=store._schema(3), storage_options={"new_table_data_storage_version": "2.2"}
    )
    with pytest.raises(ValueError, match="dimension"):
        store.create_col("other")
    with pytest.raises(ValueError, match="dimension"):
        LanceDB(path=str(tmp_path), embedding_model_dims=3)
    assert store.collection_name == "mem0"
    assert store.get("stable").payload["user_id"] == "a"


def test_invalid_native_schema_rejected_without_replacing_current(tmp_path):
    store = LanceDB(path=str(tmp_path), embedding_model_dims=2)
    original = store.table
    bad = pa.schema([
        ("id", pa.int64()), ("vector", pa.list_(pa.float32(), 2)), ("payload", pa.string()),
        ("filter_data", pa.map_(pa.string(), pa.string())),
    ])
    store.client.create_table("bad", schema=bad, storage_options={"new_table_data_storage_version": "2.2"})
    with pytest.raises(ValueError, match="schema"):
        store.create_col("bad")
    assert store.table is original


def test_json_special_keys_and_mixed_types(tmp_path):
    store = LanceDB(path=str(tmp_path), embedding_model_dims=2)
    key = "a\"b'] OR true --"
    store.insert(
        [[1.0, 0.0], [0.0, 1.0]], ids=["one", "two"],
        payloads=[{key: "x'y", "mixed": ["x"], "other": None}, {key: "other", "mixed": {"x": True}}],
    )
    assert [r.id for r in store.list(filters={key: "x'y"})[0]] == ["one"]
    assert {r.id for r in store.list(filters={"mixed": {"contains": "x"}})[0]} == {"one", "two"}
    assert [r.id for r in store.list(filters={"other": None})[0]] == ["one"]


def test_decoded_string_operations_on_mixed_json(tmp_path):
    store = LanceDB(path=str(tmp_path), embedding_model_dims=2)
    key = "field\"long'name"
    store.insert(
        [[1.0, 0.0]] * 5, ids=["string", "array", "object", "null", "number"],
        payloads=[{key: "a\nb"}, {key: ["n"]}, {key: {"n": 1}}, {key: None}, {key: 4}],
    )
    assert {r.id for r in store.list(filters={key: {"contains": "n"}})[0]} == {"array", "object"}
    assert [r.id for r in store.list(filters={key: {"contains": "\n"}})[0]] == ["string"]
    assert [r.id for r in store.list(filters={key: {"gt": "a"}})[0]] == ["string"]
    assert store.list(filters={key: {"icontains": "N"}}) == [[]]


@pytest.mark.parametrize("value,index", [("", 1), ("1", 2), ("a\"b", 3), ("a\\b", 4), ("a\nb", 5)])
def test_contains_empty_and_escaped_members_are_typed(tmp_path, value, index):
    store = LanceDB(path=str(tmp_path), embedding_model_dims=2)
    values = ["", "1", "a\"b", "a\\b", "a\nb"]
    payloads = [{"x": [1]}] + [{"x": [v]} for v in values] + [{"x": {"": None}}, {"x": "abc"}]
    store.insert([[1.0, 0.0]] * len(payloads), ids=[str(i) for i in range(len(payloads))], payloads=payloads)
    expected = {str(index)} | ({"6", "7"} if value == "" else set())
    assert {r.id for r in store.list(filters={"x": {"contains": value}})[0]} == expected


def test_legacy_table_is_preserved(tmp_path):
    db = lancedb.connect(str(tmp_path))
    schema = pa.schema([("id", pa.string()), ("vector", pa.list_(pa.float32(), 2)), ("payload", pa.string())])
    old = db.create_table("mem0", schema=schema)
    rows = [{"id": "old", "vector": [1.0, 0.0], "payload": json.dumps({"text": "old"})}]
    old.add(pa.Table.from_pylist(rows, schema=schema))
    with pytest.raises(ValueError, match="incompatible payload schema"):
        LanceDB(path=str(tmp_path), embedding_model_dims=2)
    assert db.open_table("mem0").search().to_list()[0]["payload"] == rows[0]["payload"]


def test_update_reopen_and_collection_operations(tmp_path):
    store = LanceDB(path=str(tmp_path), embedding_model_dims=2)
    original = {"text": "a\nb", "nested": {"": None}, "array": [1, True, None, "水"]}
    store.insert([[1.0, 0.0]], ids=["id' --"], payloads=[original])
    store.update("missing", payload={"new": True})
    store.update("id' --", vector=[0.0, 1.0])
    assert LanceDB(path=str(tmp_path), embedding_model_dims=2).get("id' --").payload == original
    replacement = {"text": "新", "nested": {"x": [None, False]}}
    store.update("id' --", payload=replacement)
    assert LanceDB(path=str(tmp_path), embedding_model_dims=2).get("id' --").payload == replacement
    store.create_col("other", vector_size=2)
    assert set(store.list_cols()) == {"mem0", "other"}
    store.reset()
    assert store.col_info()["count"] == 0
    store.delete_col()
    assert store.list_cols() == ["mem0"]


@pytest.mark.parametrize("filters", [
    {"": 1}, {"x": {"eq": 2**53}}, {"x": {"gt": True}}, {"x": {"in": []}},
    {"x": {"contains": 1}}, {"x": {"icontains": 1}}, {"x": {"unsupported": "x"}},
])
def test_invalid_filters_rejected_on_empty_table(tmp_path, filters):
    store = LanceDB(path=str(tmp_path), embedding_model_dims=2)
    with pytest.raises(ValueError):
        store.list(filters=filters)
    with pytest.raises(ValueError):
        store.search("", [1.0, 0.0], filters=filters)


@pytest.mark.parametrize("filters,expected", [
    ({"x": True}, {"bool"}), ({"x": 1}, {"number"}), ({"x": None}, {"null"}),
    ({"x": {"ne": 1}}, {"bool", "null"}), ({"x": {"nin": [1, None]}}, {"bool"}),
])
def test_filters_are_typed(tmp_path, filters, expected):
    store = LanceDB(path=str(tmp_path), embedding_model_dims=2)
    store.insert(
        [[1.0, 0.0]] * 4, ids=["bool", "number", "null", "missing"],
        payloads=[{"x": True}, {"x": 1}, {"x": None}, {}],
    )
    assert {row.id for row in store.list(filters=filters)[0]} == expected


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -(2**63) - 1, 2**64])
def test_invalid_writes_preserve_data(tmp_path, bad):
    store = LanceDB(path=str(tmp_path), embedding_model_dims=2)
    store.insert([[1.0, 0.0]], ids=["existing"], payloads=[{"x": 1}])
    with pytest.raises(ValueError):
        store.update("existing", vector=[0.0, 1.0], payload={"nested": [bad]})
    with pytest.raises(ValueError):
        store.update("existing", vector=[1.0], payload={"changed": True})
    with pytest.raises(ValueError):
        store.insert([[1.0, 0.0], [0.0, 1.0]], ids=["first", "bad"], payloads=[{}, {"nested": [bad]}])
    assert store.col_info()["count"] == 1
    assert store.get("existing").payload == {"x": 1}
    assert store.search("", [1.0, 0.0])[0].score == pytest.approx(1.0)


@pytest.mark.parametrize("top_k", [-1, True, 1.5, None])
def test_invalid_top_k(tmp_path, top_k):
    store = LanceDB(path=str(tmp_path), embedding_model_dims=2)
    with pytest.raises(ValueError):
        store.list(top_k=top_k)
    with pytest.raises(ValueError):
        store.search("", [1.0, 0.0], top_k=top_k)


def test_zero_top_k(tmp_path):
    store = LanceDB(path=str(tmp_path), embedding_model_dims=2)
    store.insert([[1.0, 0.0]], ids=["one"], payloads=[{}])
    assert store.list(top_k=0) == [[]]
    assert store.search("", [1.0, 0.0], top_k=0) == []


@pytest.mark.parametrize("metric", ["cosine", "l2", "dot"])
def test_search_scores_are_higher_for_closer_vectors(tmp_path, metric):
    store = LanceDB(path=str(tmp_path), embedding_model_dims=2, distance=metric)
    store.insert([[1.0, 0.0], [0.0, 1.0]], ids=["close", "far"], payloads=[{}, {}])
    results = store.search("", [1.0, 0.0], top_k=2)
    assert [row.id for row in results] == ["close", "far"]
    assert results[0].score == pytest.approx(1.0)
    assert results[0].score > results[1].score
    if metric in ("dot", "cosine"):
        assert results[1].score == pytest.approx(0.0)
    else:
        # LanceDB returns squared L2 distance for this metric.
        assert results[1].score == pytest.approx(1 / 3)


def test_factory_creates_provider_from_config(tmp_path):
    from mem0.utils.factory import VectorStoreFactory
    from mem0.vector_stores.configs import VectorStoreConfig

    config = VectorStoreConfig(provider="lancedb", config={"path": str(tmp_path), "embedding_model_dims": 2})
    store = VectorStoreFactory.create(config.provider, config.config)
    store.insert([[1.0, 0.0]], ids=["one"], payloads=[{"user_id": "a"}])
    assert store.list(filters={"user_id": "a"})[0][0].id == "one"


def test_memory_get_all_with_native_filters_and_reopen(tmp_path):
    from mem0 import Memory

    local_model_config = {"api_key": "unused-for-local-listing", "openai_base_url": "http://127.0.0.1:1"}
    config = {
        "vector_store": {
            "provider": "lancedb",
            "config": {"path": str(tmp_path / "vectors"), "embedding_model_dims": 2},
        },
        "embedder": {"provider": "openai", "config": dict(local_model_config)},
        "llm": {"provider": "openai", "config": dict(local_model_config)},
        "history_db_path": str(tmp_path / "history.db"),
    }
    memory = Memory.from_config(config)
    memory.vector_store.insert(
        [[1.0, 0.0]] * 3,
        ids=["wrong-user", "too-small", "match"],
        payloads=[
            {"user_id": "u2", "n": 5, "data": "wrong user"},
            {"user_id": "u1", "n": 1, "data": "too small"},
            {"user_id": "u1", "n": 5, "data": "selected"},
        ],
    )
    filters = {"user_id": "u1", "n": {"gte": 3}}
    results = memory.get_all(filters=filters, top_k=1, show_expired=True)["results"]
    assert [(item["id"], item["user_id"], item["memory"]) for item in results] == [("match", "u1", "selected")]
    assert results[0]["metadata"]["n"] == 5

    reopened = Memory.from_config(config)
    results = reopened.get_all(filters=filters, top_k=1, show_expired=True)["results"]
    assert [(item["id"], item["user_id"], item["memory"]) for item in results] == [("match", "u1", "selected")]


@pytest.mark.parametrize(
    "vector_type,vector", [(pa.int32(), [1, 2]), (pa.float64(), [1.5, 2.5]), (pa.string(), None)]
)
def test_incompatible_vector_type_is_rejected_without_modification(tmp_path, vector_type, vector):
    db = lancedb.connect(str(tmp_path))
    schema = pa.schema([("id", pa.string()), ("vector", pa.list_(vector_type, 2)), ("payload", pa.json_())])
    table = db.create_table("mem0", schema=schema, storage_options={"new_table_data_storage_version": "2.2"})
    # LanceDB 0.40 cannot write string vectors; an empty table still exercises schema rejection.
    if vector is not None:
        table.add(pa.Table.from_pylist([{"id": "old", "vector": vector, "payload": '{"x":1}'}], schema=schema))
    before = table.to_arrow().to_pylist()
    with pytest.raises(ValueError, match="incompatible vector schema"):
        LanceDB(path=str(tmp_path), embedding_model_dims=2)
    assert db.open_table("mem0").to_arrow().to_pylist() == before


def test_escaped_unicode_keys_and_string_operations(tmp_path):
    store = LanceDB(path=str(tmp_path), embedding_model_dims=2)
    key = "键\\line\n\"'"
    value = "前\\line\n\"'后"
    store.insert([[1.0, 0.0]], ids=["one"], payloads=[{key: value}])
    assert [row.id for row in store.list(filters={key: value})[0]] == ["one"]
    assert [row.id for row in store.list(filters={key: {"contains": "\\line\n\"'"}})[0]] == ["one"]
    assert [row.id for row in store.list(filters={key: {"gte": value}})[0]] == ["one"]


def test_json_integer_limits_survive_reopen_and_update(tmp_path):
    store = LanceDB(path=str(tmp_path), embedding_model_dims=2)
    payload = {"low": -(2**63), "high": 2**64 - 1, "label": "before"}
    store.insert([[1.0, 0.0]], ids=["limits"], payloads=[payload])
    reopened = LanceDB(path=str(tmp_path), embedding_model_dims=2)
    assert reopened.get("limits").payload == payload
    reopened.update("limits", vector=[0.0, 1.0])
    assert reopened.list(filters={"low": {"lt": 0}, "high": {"gt": 0}})[0][0].payload == payload
    payload["label"] = "after"
    reopened.update("limits", payload=payload)
    final = LanceDB(path=str(tmp_path), embedding_model_dims=2)
    assert final.get("limits").payload == payload
    assert final.list(filters={"label": "after", "high": {"gt": 0}})[0][0].payload == payload


@pytest.mark.parametrize("filters", [[], 1, "", {1: "x"}, {"$unknown": []}, {"$and": {}}, {"OR": [1]}])
def test_invalid_filter_structure_rejected(tmp_path, filters):
    store = LanceDB(path=str(tmp_path), embedding_model_dims=2)
    with pytest.raises(ValueError):
        store.list(filters=filters)
    with pytest.raises(ValueError):
        store.search("", [1.0, 0.0], filters=filters)
