import os
import uuid
from contextlib import nullcontext
from types import SimpleNamespace
from typing import Any, Dict
from unittest.mock import MagicMock

import oracledb
import pytest

from mem0.configs.vector_stores.oracledb import (
    OracleAIVectorSearchConfig,
    _quote_identifier,
)
from mem0.vector_stores.oracledb import OracleAIVectorSearch, _convert_distance_to_score

# Global Oracle connection settings (override via env to run in different environments)
ORACLE_USER = os.environ.get("ORACLE_USER") or ""
ORACLE_PASSWORD = os.environ.get("ORACLE_PASSWORD") or ""
ORACLE_DSN = os.environ.get("ORACLE_DSN") or ""

requires_oracle_credentials = pytest.mark.skipif(
    not (ORACLE_USER and ORACLE_DSN),
    reason="Oracle credentials not configured",
)

DIM = 128


def _unique_collection_name() -> str:
    # Keep under Oracle's 30-char identifier limit
    return f"TEST_MEM0_{uuid.uuid4().hex[:8]}"


# Representative coverage of the old matrix. Every option value from the previous
# grid appears in at least one case, without creating a 1924-test DDL-heavy suite.
REPRESENTATIVE_CASES = [
    {
        "name": "params-cosine-hnsw-default-noacc-noparams",
        "use_connection_pool": False,
        "distance_metric": "COSINE",
        "index_type": "HNSW",
        "custom_index_name": False,
        "index_accuracy": None,
        "index_parameters": False,
    },
    {
        "name": "params-euclidean-ivf-custom-acc90-params",
        "use_connection_pool": False,
        "distance_metric": "EUCLIDEAN",
        "index_type": "IVF",
        "custom_index_name": True,
        "index_accuracy": 90,
        "index_parameters": True,
    },
    {
        "name": "pool-cosine-ivf-default-acc90-noparams",
        "use_connection_pool": True,
        "distance_metric": "COSINE",
        "index_type": "IVF",
        "custom_index_name": False,
        "index_accuracy": 90,
        "index_parameters": False,
    },
    {
        "name": "pool-euclidean-hnsw-custom-noacc-params",
        "use_connection_pool": True,
        "distance_metric": "EUCLIDEAN",
        "index_type": "HNSW",
        "custom_index_name": True,
        "index_accuracy": None,
        "index_parameters": True,
    },
]


def _build_oracle_db(case: Dict[str, Any], *, do_create_index: bool) -> OracleAIVectorSearch:
    collection_name = _unique_collection_name()
    conn_params = {"user": ORACLE_USER, "password": ORACLE_PASSWORD, "dsn": ORACLE_DSN}
    config_kwargs: Dict[str, Any] = {
        "collection_name": collection_name,
        "embedding_model_dims": DIM,
        "distance_metric": case["distance_metric"],
        "index_type": case["index_type"],
        "do_create_index": do_create_index,
        "use_connection_pool": case["use_connection_pool"],
    }

    if case.get("custom_index_name"):
        config_kwargs["index_name"] = f"{collection_name}_IDX"
    if case.get("index_accuracy") is not None:
        config_kwargs["index_accuracy"] = case["index_accuracy"]
    if case.get("index_parameters"):
        config_kwargs["index_parameters"] = (
            {"neighbors": 40, "efconstruction": 64} if case["index_type"] == "HNSW" else {"neighbor partitions": 10}
        )

    if case.get("use_connection_pool"):
        config_kwargs["client"] = oracledb.create_pool(min=1, max=4, **conn_params)
    else:
        config_kwargs["connection_params"] = conn_params

    return OracleAIVectorSearch(**config_kwargs)


@pytest.fixture(
    params=[REPRESENTATIVE_CASES[0]],
    ids=lambda p: p["name"],
)
def oracle_db(request):
    """
    Stable Oracle fixture for CRUD/search/list behavior.
    Uses a single representative config and skips vector-index creation to avoid
    repeated DDL lock contention on the shared Oracle instance.
    """
    if not (ORACLE_USER and ORACLE_DSN):
        pytest.skip("Oracle credentials not configured")

    db = _build_oracle_db(request.param, do_create_index=False)

    try:
        yield db
    finally:
        try:
            db.delete_col()
        except Exception:
            # Ignore failures (e.g., already dropped)
            pass


@requires_oracle_credentials
@pytest.mark.parametrize("case", REPRESENTATIVE_CASES, ids=lambda case: case["name"])
def test_initialize_create_col(case: Dict[str, Any]):
    oracle_db = _build_oracle_db(case, do_create_index=False)

    try:
        # Verify config normalization and DDL generation for each representative case
        collection_name = oracle_db.collection_name.strip('"')
        expected_index_name = (
            f'"{collection_name}_IDX"' if case["custom_index_name"] else f'"{collection_name}_VEC_IDX"'
        )
        assert oracle_db.config.embedding_model_dims == DIM
        assert oracle_db.config.distance_metric in ("COSINE", "EUCLIDEAN")
        assert oracle_db.config.index_type in ("HNSW", "IVF")
        assert oracle_db.config.index_name == expected_index_name
        assert oracle_db.config.index_accuracy == case["index_accuracy"]
        assert bool(case["index_parameters"]) == bool(oracle_db.config.index_parameters)
        ddl = oracle_db._create_index_ddl()
        assert oracle_db.config.index_name in ddl
        assert oracle_db.collection_name in ddl
        if case["index_type"] == "HNSW":
            assert "INMEMORY NEIGHBOR GRAPH" in ddl
        else:
            assert "NEIGHBOR PARTITIONS" in ddl
        if case["index_accuracy"] is not None:
            assert f"WITH TARGET ACCURACY {case['index_accuracy']}" in ddl
        if case["index_parameters"]:
            assert "PARAMETERS (" in ddl
            assert f"type {case['index_type']}" in ddl
        else:
            assert "PARAMETERS (" not in ddl

        tables = oracle_db.list_cols()
        target = oracle_db.collection_name.strip('"').upper()
        assert target in [t.upper() for t in tables]
    finally:
        try:
            oracle_db.delete_col()
        except Exception:
            pass


@requires_oracle_credentials
def test_create_col_with_index_smoke():
    case = REPRESENTATIVE_CASES[1]
    oracle_db = _build_oracle_db(case, do_create_index=True)

    try:
        tables = oracle_db.list_cols()
        target = oracle_db.collection_name.strip('"').upper()
        assert target in [t.upper() for t in tables]
    finally:
        try:
            oracle_db.delete_col()
        except Exception:
            pass


@requires_oracle_credentials
def test_index_parameters_are_structured_and_allowlisted():
    conn_params = {"user": ORACLE_USER, "password": ORACLE_PASSWORD, "dsn": ORACLE_DSN}
    collection_name = _unique_collection_name()
    oracle_db = OracleAIVectorSearch(
        collection_name=collection_name,
        embedding_model_dims=DIM,
        connection_params=conn_params,
        do_create_index=False,
        index_type="HNSW",
        index_parameters={"neighbors": 40, "efconstruction": 64},
    )

    try:
        ddl = oracle_db._create_index_ddl()
        assert "PARAMETERS (type HNSW, neighbors 40, efconstruction 64)" in ddl
    finally:
        oracle_db.delete_col()


@requires_oracle_credentials
def test_ivf_index_parameters_are_structured_and_allowlisted():
    conn_params = {"user": ORACLE_USER, "password": ORACLE_PASSWORD, "dsn": ORACLE_DSN}
    collection_name = _unique_collection_name()
    oracle_db = OracleAIVectorSearch(
        collection_name=collection_name,
        embedding_model_dims=DIM,
        connection_params=conn_params,
        do_create_index=False,
        index_type="IVF",
        index_parameters={
            "neighbor partitions": 10,
            "samples_per_partition": 4,
            "min_vectors_per_partition": 2,
        },
    )

    try:
        ddl = oracle_db._create_index_ddl()
        assert (
            "PARAMETERS (type IVF, neighbor partitions 10, samples_per_partition 4, min_vectors_per_partition 2)"
        ) in ddl
    finally:
        oracle_db.delete_col()


def test_index_parameters_reject_unsupported_fragments():
    conn_params = {"user": ORACLE_USER, "password": ORACLE_PASSWORD, "dsn": ORACLE_DSN}

    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        OracleAIVectorSearch(
            collection_name=_unique_collection_name(),
            embedding_model_dims=DIM,
            connection_params=conn_params,
            do_create_index=False,
            index_type="HNSW",
            index_parameters={"parallel": "8 NOLOGGING"},
        )

    with pytest.raises(ValueError, match="Input should be a valid integer"):
        OracleAIVectorSearch(
            collection_name=_unique_collection_name(),
            embedding_model_dims=DIM,
            connection_params=conn_params,
            do_create_index=False,
            index_type="IVF",
            index_parameters={"neighbor partitions": "10) PARALLEL 8"},
        )


def test_index_parameters_reject_non_string_keys():
    with pytest.raises(ValueError, match="Keys should be strings"):
        OracleAIVectorSearchConfig(
            collection_name=_unique_collection_name(),
            embedding_model_dims=DIM,
            client=object(),
            index_type="HNSW",
            index_parameters={1: 10},
        )


def test_index_parameters_canonicalize_int_subclasses():
    class FormattedInt(int):
        def __format__(self, format_spec):
            return "40) PARALLEL 8"

    config = OracleAIVectorSearchConfig(
        collection_name=_unique_collection_name(),
        embedding_model_dims=DIM,
        client=object(),
        index_type="HNSW",
        index_parameters={"neighbors": FormattedInt(40)},
    )
    oracle_db = object.__new__(OracleAIVectorSearch)
    oracle_db.config = config
    oracle_db.collection_name = config.collection_name

    ddl = oracle_db._create_index_ddl()
    assert type(config.index_parameters["neighbors"]) is int
    assert "PARALLEL 8" not in ddl
    assert "PARAMETERS (type HNSW, neighbors 40)" in ddl


def test_ivf_index_parameters_use_oracle_ddl_names():
    config = OracleAIVectorSearchConfig(
        collection_name=_unique_collection_name(),
        embedding_model_dims=DIM,
        client=object(),
        index_type="ivf",
        index_parameters={
            "neighbor partitions": 10,
            "samples_per_partition": 4,
            "min_vectors_per_partition": 2,
        },
    )
    oracle_db = object.__new__(OracleAIVectorSearch)
    oracle_db.config = config
    oracle_db.collection_name = config.collection_name

    assert config.index_type == "IVF"
    assert config.index_parameters == {
        "neighbor partitions": 10,
        "samples_per_partition": 4,
        "min_vectors_per_partition": 2,
    }
    assert (
        oracle_db._index_parameters()
        == "type IVF, neighbor partitions 10, samples_per_partition 4, min_vectors_per_partition 2"
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("distance_metric", None),
        ("index_type", None),
        ("use_connection_pool", None),
        ("collection_name", None),
    ],
)
def test_config_rejects_none_for_non_optional_fields(field, value):
    with pytest.raises(ValueError):
        OracleAIVectorSearchConfig(client=object(), **{field: value})


@pytest.mark.parametrize(
    ("metric", "distance", "expected_score"),
    [
        ("COSINE", 0.25, 0.75),
        ("cosine", -0.01, 1.0),
        ("COSINE", 1.25, 0.0),
        ("EUCLIDEAN", 3.0, 0.25),
        ("EUCLIDEAN", -0.01, 1.0),
        ("EUCLIDEAN_SQUARED", 9.0, 0.25),
        ("HAMMING", 3.0, 0.25),
        ("MANHATTAN", 3.0, 0.25),
        ("DOT", -0.75, 0.75),
        ("DOT", 0.25, -0.25),
    ],
)
def test_convert_distance_to_score(metric, distance, expected_score):
    assert _convert_distance_to_score(distance, metric) == pytest.approx(expected_score)


def test_convert_distance_to_score_rejects_unknown_metric():
    with pytest.raises(ValueError, match="Unsupported distance metric: UNKNOWN"):
        _convert_distance_to_score(0.5, "UNKNOWN")


def test_search_and_list_follow_base_contract():
    search_cursor = MagicMock()
    search_cursor.fetchall.return_value = [
        ("close", '{"label": "close"}', 0.1),
        ("far", '{"label": "far"}', 0.8),
    ]
    list_cursor = MagicMock()
    list_cursor.fetchall.return_value = [
        ("listed", '{"name": "listed"}'),
    ]

    store = object.__new__(OracleAIVectorSearch)
    store.collection_name = '"MEM0"'
    store.config = SimpleNamespace(distance_metric="COSINE")
    store._get_cursor = MagicMock(
        side_effect=[
            nullcontext(search_cursor),
            nullcontext(list_cursor),
        ]
    )

    search_results = store.search(
        query="unused",
        vectors=[1.0, 0.0],
        top_k=2,
        filters={"score": {"gte": 5}},
    )
    list_results = store.list(top_k=2)

    assert [result.score for result in search_results] == pytest.approx([0.9, 0.2])
    assert search_results[0].score > search_results[1].score
    search_sql = search_cursor.execute.call_args.args[0]
    assert "@ >= $f_0" in search_sql
    assert search_cursor.execute.call_args.kwargs["f_0"] == 5
    assert isinstance(list_results[0], list)
    assert list_results[0][0].payload["name"] == "listed"


def test_build_filters_wildcard_requires_field_existence():
    store = object.__new__(OracleAIVectorSearch)

    clause, params = store._build_filters({"run_id": "*"})

    assert clause == """WHERE JSON_EXISTS(payload, '$."run_id"')"""
    assert params == {}


def test_build_filters_rejects_empty_metadata_key():
    store = object.__new__(OracleAIVectorSearch)

    with pytest.raises(ValueError, match="Invalid metadata key"):
        store._build_filters({"": "alice"})


@pytest.mark.parametrize(
    ("collection_name", "expected"),
    [
        ("MEM0", (None, "MEM0")),
        ("SCHEMA.MEM0", ("SCHEMA", "MEM0")),
        ('"my.table"', (None, "my.table")),
    ],
)
def test_split_collection_name(collection_name, expected):
    store = object.__new__(OracleAIVectorSearch)
    store.collection_name = _quote_identifier(collection_name)

    assert store._split_collection_name() == expected


def test_col_info_looks_up_the_unqualified_table_name():
    cursor = MagicMock()
    cursor.fetchone.return_value = ("MEM0", 7, "1.5 MB")

    store = object.__new__(OracleAIVectorSearch)
    store.collection_name = _quote_identifier("SCHEMA.MEM0")
    store._get_cursor = MagicMock(return_value=nullcontext(cursor))

    info = store.col_info()

    assert info == {"name": "MEM0", "count": 7, "size": "1.5 MB"}
    assert cursor.execute.call_args.kwargs == {"table_name": "MEM0", "owner": "SCHEMA"}


def test_col_info_raises_when_collection_is_missing():
    cursor = MagicMock()
    cursor.fetchone.return_value = None

    store = object.__new__(OracleAIVectorSearch)
    store.collection_name = _quote_identifier("MEM0")
    store._get_cursor = MagicMock(return_value=nullcontext(cursor))

    with pytest.raises(ValueError, match="not found"):
        store.col_info()


def test_build_filters_combines_wildcard_and_scalar_equality():
    store = object.__new__(OracleAIVectorSearch)

    clause, params = store._build_filters({"user_id": "alice", "run_id": "*"})

    assert """JSON_EXISTS(payload, '$."user_id"?(@ == $f_0)' PASSING :f_0 AS "f_0")""" in clause
    assert """JSON_EXISTS(payload, '$."run_id"')""" in clause
    assert " AND " in clause
    assert params == {"f_0": "alice"}


@pytest.mark.parametrize(
    ("operator", "predicate"),
    [
        ("eq", "@ == $f_0"),
        ("ne", "@ != $f_0"),
        ("gt", "@ > $f_0"),
        ("gte", "@ >= $f_0"),
        ("lt", "@ < $f_0"),
        ("lte", "@ <= $f_0"),
    ],
)
def test_build_filters_comparison_operators(operator, predicate):
    store = object.__new__(OracleAIVectorSearch)

    clause, params = store._build_filters({"score": {operator: 5}})

    assert predicate in clause
    assert params == {"f_0": 5}


def test_build_filters_combines_comparisons_for_same_field():
    store = object.__new__(OracleAIVectorSearch)

    clause, params = store._build_filters({"score": {"gte": 5, "lt": 10}})

    assert '$."score"?(@ >= $f_0 && @ < $f_1)' in clause
    assert params == {"f_0": 5, "f_1": 10}


@pytest.mark.parametrize(
    ("operator", "expected"),
    [
        ("in", "JSON_EXISTS"),
        ("nin", "NOT (JSON_EXISTS"),
    ],
)
def test_build_filters_membership_operators_expand_binds(operator, expected):
    store = object.__new__(OracleAIVectorSearch)

    clause, params = store._build_filters({"category": {operator: ["work", "personal"]}})

    assert expected in clause
    assert "@ in ($f_0, $f_1)" in clause
    assert params == {"f_0": "work", "f_1": "personal"}


def test_build_filters_string_operators():
    store = object.__new__(OracleAIVectorSearch)

    contains_clause, contains_params = store._build_filters({"title": {"contains": "Meeting"}})
    icontains_clause, icontains_params = store._build_filters({"title": {"icontains": "Meet.ing"}})

    assert "@ has substring $f_0" in contains_clause
    assert contains_params == {"f_0": "Meeting"}
    assert "@.lower() has substring $f_0" in icontains_clause
    assert icontains_params == {"f_0": "meet.ing"}


def test_build_filters_operator_eq_treats_asterisk_as_literal():
    store = object.__new__(OracleAIVectorSearch)

    clause, params = store._build_filters({"status": {"eq": "*"}})

    assert "@ == $f_0" in clause
    assert params == {"f_0": "*"}


@pytest.mark.parametrize(
    ("filters", "predicate", "params"),
    [
        ({"nullable": None}, "@ == null", {}),
        ({"nullable": {"eq": None}}, "@ == null", {}),
        ({"nullable": {"ne": None}}, "@ != null", {}),
        ({"nullable": {"in": [None, "set"]}}, "@ in (null, $f_0)", {"f_0": "set"}),
    ],
)
def test_build_filters_supports_json_null(filters, predicate, params):
    store = object.__new__(OracleAIVectorSearch)

    clause, actual_params = store._build_filters(filters)

    assert predicate in clause
    assert actual_params == params


def test_build_filters_nested_logical_operators_share_bind_namespace():
    store = object.__new__(OracleAIVectorSearch)
    filters = {
        "user_id": "alice",
        "$or": [
            {"score": {"gte": 5}},
            {
                "$and": [
                    {"status": {"eq": "active"}},
                    {"category": "work"},
                ]
            },
        ],
        "$not": [{"archived": {"eq": "yes"}}],
    }

    clause, params = store._build_filters(filters)

    assert " OR " in clause
    assert " AND " in clause
    assert "NOT (" in clause
    assert params == {
        "f_0": "alice",
        "f_1": 5,
        "f_2": "active",
        "f_3": "work",
        "f_4": "yes",
    }


def test_build_filters_accepts_unprocessed_logical_operator_names():
    store = object.__new__(OracleAIVectorSearch)

    clause, params = store._build_filters(
        {
            "AND": [
                {"score": {"gte": 5}},
                {"OR": [{"category": "work"}, {"category": "personal"}]},
            ]
        }
    )

    assert " AND " in clause
    assert " OR " in clause
    assert params == {"f_0": 5, "f_1": "work", "f_2": "personal"}


@pytest.mark.parametrize(
    ("filters", "message"),
    [
        ({"score": {"between": [1, 2]}}, "Unsupported Oracle filter operator"),
        ({"score": {}}, "must not be empty"),
        ({"score": {"in": []}}, "requires a non-empty list"),
        ({"title": {"contains": 5}}, "requires a string value"),
        ({"score": {"gte": [5]}}, "requires a scalar value"),
        ({"score": {"gte": None}}, "does not support null"),
        ({"$xor": [{"score": 5}]}, "Unsupported Oracle logical filter operator"),
        ({"$or": []}, "requires a non-empty list"),
        ({"bad-key": "value"}, "Invalid metadata key"),
    ],
)
def test_build_filters_rejects_invalid_filter_shapes(filters, message):
    store = object.__new__(OracleAIVectorSearch)

    with pytest.raises(ValueError, match=message):
        store._build_filters(filters)


def test_insert_and_get(oracle_db: OracleAIVectorSearch):
    vectors = [[0.1] * DIM, [0.2] * DIM]
    payloads = [{"name": "vector1"}, {"name": "vector2"}]

    oracle_db.insert(vectors, payloads=payloads)

    listed = oracle_db.list(top_k=10)[0]
    assert len(listed) >= 2
    seen_names = {item.payload.get("name") for item in listed}
    assert {"vector1", "vector2"}.issubset(seen_names)

    # Fetch one by id (Oracle RAW(16) id is generated by DB)
    some_id = listed[0].id
    got = oracle_db.get(vector_id=some_id)
    assert got is not None
    assert got.id == some_id
    assert isinstance(got.payload, dict)


def test_search(oracle_db: OracleAIVectorSearch):
    # Create predictable geometry; works for COSINE or EUCLIDEAN
    pos_vec = [1.0] * DIM
    neg_vec = [-1.0] * DIM
    mid_vec = [1.0 if i % 2 == 0 else 0.0 for i in range(DIM)]
    payloads = [
        {"name": "pos", "user_id": "u1"},
        {"name": "neg", "user_id": "u2"},
        {"name": "mid", "user_id": "u3"},
    ]
    oracle_db.insert([pos_vec, neg_vec, mid_vec], payloads=payloads)

    results = oracle_db.search("unused", vectors=pos_vec, top_k=3)
    assert isinstance(results, list)
    assert len(results) >= 1

    names = {r.payload.get("name") for r in results}
    assert "pos" in names  # closest to query


def test_search_with_filters(oracle_db: OracleAIVectorSearch):
    vec = [0.5] * DIM
    payloads = [
        {"name": "a", "user_id": "alice", "agent_id": "agent1", "run_id": "run1"},
        {"name": "b", "user_id": "bob", "agent_id": "agent2", "run_id": "run2"},
    ]
    oracle_db.insert([vec, vec], payloads=payloads)

    filters = {"user_id": "alice", "agent_id": "agent1", "run_id": "run1"}
    results = oracle_db.search("unused", vectors=vec, top_k=5, filters=filters)

    assert len(results) >= 1
    for r in results:
        assert r.payload.get("user_id") == "alice"
        assert r.payload.get("agent_id") == "agent1"
        assert r.payload.get("run_id") == "run1"


def test_search_with_single_filter(oracle_db: OracleAIVectorSearch):
    vec = [0.7] * DIM
    payloads = [
        {"name": "x", "user_id": "alice"},
        {"name": "y", "user_id": "bob"},
    ]
    oracle_db.insert([vec, vec], payloads=payloads)

    results = oracle_db.search("unused", vectors=vec, top_k=5, filters={"user_id": "alice"})
    assert len(results) >= 1
    for r in results:
        assert r.payload.get("user_id") == "alice"


def test_search_with_no_filters(oracle_db: OracleAIVectorSearch):
    vec = [0.33] * DIM
    oracle_db.insert([vec], payloads=[{"k": "v"}])

    results = oracle_db.search("unused", vectors=vec, top_k=1, filters=None)
    assert len(results) == 1


def test_extended_filtering(oracle_db: OracleAIVectorSearch):
    vector = [0.42] * DIM
    oracle_db.insert(
        [vector] * 4,
        payloads=[
            {
                "name": "Alpha Meeting",
                "score": 10,
                "category": "work",
                "status": "active",
                "run_id": "r1",
                "enabled": True,
                "nullable": None,
                "ratio": 1.25,
                "created_at": "2025-01-15",
                "profile": {"department": "Engineering", "skills": ["Python", "SQL"]},
            },
            {
                "name": "beta meeting",
                "score": 5,
                "category": "personal",
                "status": "inactive",
                "enabled": False,
                "nullable": "set",
                "ratio": 2.5,
                "created_at": "2024-12-31",
                "profile": {"department": "Engineering", "skills": ["Java"]},
            },
            {
                "name": "Gamma",
                "score": 20,
                "category": "work",
                "status": "active",
                "run_id": "r3",
                "enabled": True,
                "ratio": 3.75,
                "created_at": "2025-06-01",
                "profile": {"department": "Sales", "skills": ["Python"]},
            },
            {
                "name": "Literal",
                "score": 12,
                "category": "other",
                "status": "*",
                "enabled": False,
                "nullable": "value",
                "ratio": 4.0,
                "created_at": "2026-01-01",
                "profile": {"department": "Support", "skills": []},
            },
        ],
        ids=["alpha", "beta", "gamma", "literal"],
    )

    def matching_names(filters):
        results = oracle_db.list(filters=filters, top_k=10)[0]
        return {result.payload["name"] for result in results}

    assert matching_names({"score": {"gte": 6, "lt": 20}}) == {"Alpha Meeting", "Literal"}
    assert matching_names({"category": {"eq": "work"}}) == {"Alpha Meeting", "Gamma"}
    assert matching_names({"category": {"ne": "work"}}) == {"beta meeting", "Literal"}
    assert matching_names({"score": {"lte": 10}}) == {"Alpha Meeting", "beta meeting"}
    assert matching_names({"category": {"in": ["work", "personal"]}}) == {
        "Alpha Meeting",
        "beta meeting",
        "Gamma",
    }
    assert matching_names({"category": {"nin": ["work", "personal"]}}) == {"Literal"}
    assert matching_names({"name": {"contains": "Meeting"}}) == {"Alpha Meeting"}
    assert matching_names({"name": {"icontains": "meeting"}}) == {"Alpha Meeting", "beta meeting"}
    assert matching_names({"run_id": "*"}) == {"Alpha Meeting", "Gamma"}
    assert matching_names({"status": {"eq": "*"}}) == {"Literal"}
    assert matching_names({"profile.department": {"eq": "Engineering"}}) == {
        "Alpha Meeting",
        "beta meeting",
    }
    assert matching_names({"profile.skills[*]": {"eq": "Python"}}) == {"Alpha Meeting", "Gamma"}
    assert matching_names({"enabled": {"eq": True}}) == {"Alpha Meeting", "Gamma"}
    assert matching_names({"nullable": {"eq": None}}) == {"Alpha Meeting"}
    assert matching_names({"nullable": {"ne": None}}) == {"beta meeting", "Literal"}
    assert matching_names({"nullable": {"in": [None, "set"]}}) == {"Alpha Meeting", "beta meeting"}
    assert matching_names({"created_at": {"gte": "2025-01-01", "lt": "2026-01-01"}}) == {
        "Alpha Meeting",
        "Gamma",
    }
    assert matching_names({"ratio": {"gt": 1.25, "lte": 3.75}}) == {"beta meeting", "Gamma"}
    assert matching_names({"score": {"gte": 10, "in": [10, 12]}}) == {"Alpha Meeting", "Literal"}
    assert matching_names(
        {
            "$or": [
                {"score": {"lt": 6}},
                {"score": {"gt": 15}},
            ]
        }
    ) == {"beta meeting", "Gamma"}
    assert matching_names({"$not": [{"category": {"eq": "personal"}}]}) == {
        "Alpha Meeting",
        "Gamma",
        "Literal",
    }
    assert matching_names(
        {
            "AND": [
                {"score": {"gte": 10}},
                {
                    "OR": [
                        {"category": "work"},
                        {"status": {"eq": "*"}},
                    ]
                },
            ]
        }
    ) == {"Alpha Meeting", "Gamma", "Literal"}
    assert matching_names(
        {
            "AND": [
                {"enabled": {"eq": True}},
                {
                    "OR": [
                        {"profile.department": {"eq": "Engineering"}},
                        {
                            "AND": [
                                {"score": {"gt": 15}},
                                {"NOT": [{"category": {"eq": "personal"}}]},
                            ]
                        },
                    ]
                },
            ]
        }
    ) == {"Alpha Meeting", "Gamma"}


def test_delete(oracle_db: OracleAIVectorSearch):
    vec = [0.9] * DIM
    oracle_db.insert([vec], payloads=[{"name": "to_delete"}])

    listed = oracle_db.list(top_k=10)[0]
    assert len(listed) >= 1
    target_id = listed[0].id

    oracle_db.delete(vector_id=target_id)
    got = oracle_db.get(vector_id=target_id)
    assert got is None


def test_reset_recreates_empty_usable_collection(oracle_db: OracleAIVectorSearch):
    vector = [0.15] * DIM
    oracle_db.insert([vector], ids=["before-reset"], payloads=[{"name": "before"}])
    assert oracle_db.get("before-reset") is not None

    oracle_db.reset()

    assert oracle_db.get("before-reset") is None
    assert oracle_db.list(top_k=10) == [[]]

    oracle_db.insert([vector], ids=["after-reset"], payloads=[{"name": "after"}])
    result = oracle_db.get("after-reset")
    assert result is not None
    assert result.payload["name"] == "after"


def test_update(oracle_db: OracleAIVectorSearch):
    vec = [0.01] * DIM
    oracle_db.insert([vec], payloads=[{"name": "old"}])

    listed = oracle_db.list(top_k=10)[0]
    assert len(listed) >= 1
    target_id = listed[0].id

    updated_vec = [0.02] * DIM
    updated_payload = {"name": "new"}
    oracle_db.update(vector_id=target_id, vector=updated_vec, payload=updated_payload)

    got = oracle_db.get(vector_id=target_id)
    assert got is not None
    assert got.payload.get("name") == "new"


def test_list_cols(oracle_db: OracleAIVectorSearch):
    tables = oracle_db.list_cols()
    target = oracle_db.collection_name.strip('"').upper()
    assert target in [t.upper() for t in tables]


def test_delete_col_isolated(oracle_db: OracleAIVectorSearch):
    # Use a separate, isolated collection to test drop; reuse current fixture's metric/index options
    collection_name = _unique_collection_name()
    cfg: Dict[str, Any] = {
        "collection_name": collection_name,
        "embedding_model_dims": DIM,
        "distance_metric": oracle_db.config.distance_metric,
        "index_type": oracle_db.config.index_type,
        "do_create_index": False,
        "connection_params": {"user": ORACLE_USER, "password": ORACLE_PASSWORD, "dsn": ORACLE_DSN},
    }

    # If the fixture used a pool object, pass it as well.
    if getattr(oracle_db.config, "client", None):
        cfg["client"] = oracle_db.config.client

    tmp_db = OracleAIVectorSearch(**cfg)

    tgt = tmp_db.collection_name.strip('"').upper()
    tables_before = [t.upper() for t in tmp_db.list_cols()]
    assert tgt in tables_before

    tmp_db.delete_col()

    tables_after = [t.upper() for t in tmp_db.list_cols()]
    assert tgt not in tables_after


def test_col_info(oracle_db: OracleAIVectorSearch):
    info = oracle_db.col_info()
    # Structure sanity checks; exact values depend on DB state
    assert isinstance(info, dict)
    assert "name" in info and "count" in info and "size" in info


def test_list(oracle_db: OracleAIVectorSearch):
    v1, v2 = [0.11] * DIM, [0.22] * DIM
    oracle_db.insert([v1, v2], payloads=[{"key": "value1"}, {"key": "value2"}])

    results = oracle_db.list(top_k=2)
    assert isinstance(results[0], list)
    listed = results[0]
    assert len(listed) <= 2
    # Both inserted might be returned if table had no prior rows
    if len(listed) == 2:
        payloads = [r.payload for r in listed]
        keys = {p.get("key") for p in payloads}
        assert keys.issubset({"value1", "value2"})


def test_list_with_filters(oracle_db: OracleAIVectorSearch):
    v = [0.44] * DIM
    oracle_db.insert(
        [v, v],
        payloads=[
            {"user_id": "alice", "agent_id": "agent1", "run_id": "run1"},
            {"user_id": "bob", "agent_id": "agent2", "run_id": "run2"},
        ],
    )

    filters = {"user_id": "alice", "agent_id": "agent1", "run_id": "run1"}
    results = oracle_db.list(filters=filters, top_k=10)[0]
    assert len(results) >= 1
    for r in results:
        assert r.payload.get("user_id") == "alice"
        assert r.payload.get("agent_id") == "agent1"
        assert r.payload.get("run_id") == "run1"


def test_list_with_single_filter(oracle_db: OracleAIVectorSearch):
    v = [0.55] * DIM
    oracle_db.insert(
        [v, v],
        payloads=[
            {"user_id": "alice"},
            {"user_id": "bob"},
        ],
    )

    results = oracle_db.list(filters={"user_id": "alice"}, top_k=10)[0]
    assert len(results) >= 1
    for r in results:
        assert r.payload.get("user_id") == "alice"


def test_list_with_no_filters(oracle_db: OracleAIVectorSearch):
    v = [0.66] * DIM
    oracle_db.insert([v], payloads=[{"k": "v"}])

    results = oracle_db.list(filters=None, top_k=10)[0]
    assert len(results) >= 1


def test_list_returns_nested_output(oracle_db: OracleAIVectorSearch):
    oracle_db.insert([[0.12] * DIM], payloads=[{"name": "nested"}])

    results = oracle_db.list(top_k=10)

    assert isinstance(results, list)
    assert results
    assert isinstance(results[0], list)
    assert results[0][0].payload["name"] == "nested"


def test_update_accepts_empty_payload(oracle_db: OracleAIVectorSearch):
    oracle_db.insert([[0.21] * DIM], payloads=[{"name": "before"}], ids=["row-1"])

    oracle_db.update("row-1", payload={})

    result = oracle_db.get("row-1")
    assert result is not None
    assert result.payload == {}


@requires_oracle_credentials
def test_does_not_close_caller_supplied_pool():
    pool = oracledb.create_pool(
        min=1,
        max=2,
        user=ORACLE_USER,
        password=ORACLE_PASSWORD,
        dsn=ORACLE_DSN,
    )
    db = OracleAIVectorSearch(
        collection_name=_unique_collection_name(),
        embedding_model_dims=4,
        do_create_index=False,
        client=pool,
    )

    try:
        db.__del__()
        with pool.acquire() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1 FROM dual")
                assert cursor.fetchone()[0] == 1
    finally:
        try:
            db.delete_col()
        finally:
            pool.close()


@requires_oracle_credentials
def test_documentation():
    from mem0 import Memory

    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY is required for the end-to-end documentation test")

    config = {
        "vector_store": {
            "provider": "oracledb",
            "config": {
                "connection_params": {"user": ORACLE_USER, "password": ORACLE_PASSWORD, "dsn": ORACLE_DSN},
                "do_create_index": False,
            },
        },
    }

    m = Memory.from_config(config)
    messages = [
        {"role": "user", "content": "I'm planning to watch a movie tonight. Any recommendations?"},
        {"role": "assistant", "content": "How about thriller movies? They can be quite engaging."},
        {"role": "user", "content": "I'm not a big fan of thriller movies but I love sci-fi movies."},
        {
            "role": "assistant",
            "content": "Got it! I'll avoid thriller recommendations and suggest sci-fi movies in the future.",
        },
    ]
    m.add(messages, user_id="alice", metadata={"category": "movies"})
    results = m.search("What movie to watch?", user_id="alice", limit=2)["results"]
    assert len(results) == 2
    assert all(res["user_id"] == "alice" for res in results)
    m.reset()
