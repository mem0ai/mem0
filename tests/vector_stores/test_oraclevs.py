import os
import uuid
from typing import List, Dict, Any

import pytest
import oracledb

from mem0.configs.vector_stores.oracledb import OracleAIVectorSearchConfig
from mem0.vector_stores.oracledb import OracleAIVectorSearch, OutputData


# Global connection settings (override via env to run in different envs)
ORACLE_USER = os.environ.get("ORACLE_USER") or ""
ORACLE_PASSWORD = os.environ.get("ORACLE_PASSWORD") or ""
ORACLE_DSN = os.environ.get("ORACLE_DSN") or ""

DIM = 128


def _unique_collection_name() -> str:
    # Keep under Oracle's 30-char identifier limit
    return f"TEST_MEM0_{uuid.uuid4().hex[:8]}"


def _unwrap_results(results: Any) -> List[OutputData]:
    # Current implementation of list() returns [outputs] (nested); unwrap for assertions.
    if isinstance(results, list) and len(results) == 1 and isinstance(results[0], list):
        return results[0]
    return results


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
            {"neighbors": 40, "efconstruction": 64}
            if case["index_type"] == "HNSW"
            else {"neighbor_partitions": 10}
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
    db = _build_oracle_db(request.param, do_create_index=False)

    try:
        yield db
    finally:
        try:
            db.delete_col()
        except Exception:
            # Ignore failures (e.g., already dropped)
            pass


@pytest.mark.parametrize("case", REPRESENTATIVE_CASES, ids=lambda case: case["name"])
def test_initialize_create_col(case: Dict[str, Any]):
    oracle_db = _build_oracle_db(case, do_create_index=False)

    try:
        # Verify config normalization and DDL generation for each representative case
        collection_name = oracle_db.collection_name.strip('"')
        expected_index_name = (
            f'"{collection_name}_IDX"'
            if case["custom_index_name"]
            else f'"{collection_name}_VEC_IDX"'
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
            "neighbor_partitions": 10,
            "samples_per_partition": 4,
            "min_vectors_per_partition": 2,
        },
    )

    try:
        ddl = oracle_db._create_index_ddl()
        assert (
            "PARAMETERS (type IVF, neighbor partitions 10, samples_per_partition 4, "
            "min_vectors_per_partition 2)"
        ) in ddl
    finally:
        oracle_db.delete_col()


def test_index_parameters_reject_unsupported_fragments():
    conn_params = {"user": ORACLE_USER, "password": ORACLE_PASSWORD, "dsn": ORACLE_DSN}

    with pytest.raises(ValueError, match="unsupported keys"):
        OracleAIVectorSearch(
            collection_name=_unique_collection_name(),
            embedding_model_dims=DIM,
            connection_params=conn_params,
            do_create_index=False,
            index_type="HNSW",
            index_parameters={"parallel": "8 NOLOGGING"},
        )

    with pytest.raises(ValueError, match="must be an integer"):
        OracleAIVectorSearch(
            collection_name=_unique_collection_name(),
            embedding_model_dims=DIM,
            connection_params=conn_params,
            do_create_index=False,
            index_type="IVF",
            index_parameters={"neighbor_partitions": "10) PARALLEL 8"},
        )


def test_index_parameters_reject_non_string_keys():
    with pytest.raises(ValueError, match="keys must be strings"):
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


def test_index_parameters_reject_post_validation_mutation():
    config = OracleAIVectorSearchConfig(
        collection_name=_unique_collection_name(),
        embedding_model_dims=DIM,
        client=object(),
        index_type="HNSW",
        index_parameters={"neighbors": 40},
    )
    oracle_db = object.__new__(OracleAIVectorSearch)
    oracle_db.config = config
    oracle_db.collection_name = config.collection_name

    config.index_parameters["neighbors"] = "40) PARALLEL 8"

    with pytest.raises(ValueError, match="must be an integer"):
        oracle_db._create_index_ddl()


def test_insert_and_get(oracle_db: OracleAIVectorSearch):
    vectors = [[0.1] * DIM, [0.2] * DIM]
    payloads = [{"name": "vector1"}, {"name": "vector2"}]

    oracle_db.insert(vectors, payloads=payloads)

    listed = _unwrap_results(oracle_db.list(limit=10))
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

    results = oracle_db.search("unused", vectors=pos_vec, limit=3)
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
    results = oracle_db.search("unused", vectors=vec, limit=5, filters=filters)

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

    results = oracle_db.search("unused", vectors=vec, limit=5, filters={"user_id": "alice"})
    assert len(results) >= 1
    for r in results:
        assert r.payload.get("user_id") == "alice"


def test_search_with_no_filters(oracle_db: OracleAIVectorSearch):
    vec = [0.33] * DIM
    oracle_db.insert([vec], payloads=[{"k": "v"}])

    results = oracle_db.search("unused", vectors=vec, limit=1, filters=None)
    assert len(results) == 1


def test_delete(oracle_db: OracleAIVectorSearch):
    vec = [0.9] * DIM
    oracle_db.insert([vec], payloads=[{"name": "to_delete"}])

    listed = _unwrap_results(oracle_db.list(limit=10))
    assert len(listed) >= 1
    target_id = listed[0].id

    oracle_db.delete(vector_id=target_id)
    got = oracle_db.get(vector_id=target_id)
    assert got is None


def test_update(oracle_db: OracleAIVectorSearch):
    vec = [0.01] * DIM
    oracle_db.insert([vec], payloads=[{"name": "old"}])

    listed = _unwrap_results(oracle_db.list(limit=10))
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

    results = _unwrap_results(oracle_db.list(limit=2))
    assert len(results) <= 2
    # Both inserted might be returned if table had no prior rows
    if len(results) == 2:
        payloads = [r.payload for r in results]
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
    results = _unwrap_results(oracle_db.list(filters=filters, limit=10))
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

    results = _unwrap_results(oracle_db.list(filters={"user_id": "alice"}, limit=10))
    assert len(results) >= 1
    for r in results:
        assert r.payload.get("user_id") == "alice"


def test_list_with_no_filters(oracle_db: OracleAIVectorSearch):
    v = [0.66] * DIM
    oracle_db.insert([v], payloads=[{"k": "v"}])

    results = _unwrap_results(oracle_db.list(filters=None, limit=10))
    assert len(results) >= 1


def test_list_returns_flat_output(oracle_db: OracleAIVectorSearch):
    oracle_db.insert([[0.12] * DIM], payloads=[{"name": "flat"}])

    results = oracle_db.list(limit=10)

    assert isinstance(results, list)
    assert results
    assert not isinstance(results[0], list)
    assert results[0].payload["name"] == "flat"


def test_update_accepts_empty_payload(oracle_db: OracleAIVectorSearch):
    oracle_db.insert([[0.21] * DIM], payloads=[{"name": "before"}], ids=["row-1"])

    oracle_db.update("row-1", payload={})

    result = oracle_db.get("row-1")
    assert result is not None
    assert result.payload == {}


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
