import json
import ssl
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from mem0.configs.vector_stores.scylladb import ScyllaDBConfig
from mem0.vector_stores.scylladb import OutputData, ScyllaDB, _matches_filters

# ---------------------------------------------------------------------------
# Fake session
# ---------------------------------------------------------------------------


class FakePrepared:
    def __init__(self, cql):
        self.cql = cql

    def bind(self, values):
        return FakeBound(self.cql, tuple(values))


class FakeBound:
    def __init__(self, cql, values):
        self.cql = cql
        self.values = values
        self.fetch_size = None


class FakeResult(list):
    def one(self):
        return self[0] if self else None


class FakeSession:
    """Records every executed statement; ``responder(cql, params)`` returns the rows."""

    def __init__(self):
        self.calls = []
        self.responder = lambda cql, params: []

    def prepare(self, cql):
        return FakePrepared(cql)

    def execute(self, statement, params=None):
        if isinstance(statement, FakeBound):
            cql, params = statement.cql, statement.values
            self.last_bound = statement
        elif isinstance(statement, FakePrepared):
            cql = statement.cql
        else:
            cql = statement
        self.calls.append((cql, params))
        result = self.responder(cql, params)
        if isinstance(result, Exception):
            raise result
        return FakeResult(result)

    def executed(self, fragment):
        return [(cql, params) for cql, params in self.calls if fragment in cql]


def _ann_row(id_, score, payload):
    return Mock(id=id_, score=score, payload=json.dumps(payload))


def _row(id_, payload):
    return Mock(id=id_, payload=json.dumps(payload))


def _make_store(session, **kwargs):
    cluster = Mock()
    cluster.connect = Mock(return_value=session)
    params = dict(
        contact_points=["127.0.0.1"],
        keyspace="test_keyspace",
        collection_name="test_collection",
        embedding_model_dims=3,
    )
    params.update(kwargs)
    with patch("mem0.vector_stores.scylladb.Cluster", return_value=cluster) as cluster_cls:
        store = ScyllaDB(**params)
    store._cluster_cls = cluster_cls
    return store


@pytest.fixture
def session():
    return FakeSession()


@pytest.fixture
def store(session):
    instance = _make_store(session)
    session.calls.clear()
    return instance


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


def test_init_stores_config(session):
    instance = _make_store(session, username="testuser", password="testpass", embedding_model_dims=128)

    assert instance.contact_points == ["127.0.0.1"]
    assert instance.port == 9042
    assert instance.username == "testuser"
    assert instance.keyspace == "test_keyspace"
    assert instance.collection_name == "test_collection"
    assert instance.embedding_model_dims == 128
    assert instance.replication_factor == 3


def test_init_creates_keyspace_with_replication_factor(session):
    _make_store(session, replication_factor=1)

    (cql, _), *_ = session.executed("CREATE KEYSPACE")
    assert "'class': 'NetworkTopologyStrategy'" in cql
    assert "'replication_factor': 1" in cql


def test_init_creates_scoped_schema(session):
    _make_store(session)

    table_ddl = session.executed("CREATE TABLE")[0][0]
    for column in ("id text PRIMARY KEY", "vector VECTOR<FLOAT, 3>", "user_id text", "agent_id text", "run_id text"):
        assert column in table_ddl

    ann_indexes = [cql for cql, _ in session.executed("CREATE CUSTOM INDEX")]
    assert len(ann_indexes) == 3
    assert any("((user_id), vector, agent_id, run_id)" in cql for cql in ann_indexes)
    assert any("((agent_id), vector, user_id, run_id)" in cql for cql in ann_indexes)
    assert any("((run_id), vector, user_id, agent_id)" in cql for cql in ann_indexes)

    secondary = [cql for cql, _ in session.executed("CREATE INDEX IF NOT EXISTS")]
    assert {cql.rsplit("(", 1)[1].rstrip(")") for cql in secondary} == {"user_id", "agent_id", "run_id"}


def test_mixed_case_identifiers_are_normalized(session):
    instance = _make_store(session, keyspace="MyMem0", collection_name="MyMemories")

    assert instance.keyspace == "mymem0"
    assert instance.collection_name == "mymemories"
    assert all("MyMem0" not in cql and "MyMemories" not in cql for cql, _ in session.calls)


def test_invalid_keyspace_name_rejected(session):
    with pytest.raises(ValueError, match="Invalid keyspace"):
        _make_store(session, keyspace="bad keyspace!")


def test_init_with_datacenter(session):
    with patch("mem0.vector_stores.scylladb.DCAwareRoundRobinPolicy") as mock_policy:
        instance = _make_store(session, datacenter="AWS_US_EAST_1")

    assert instance.datacenter == "AWS_US_EAST_1"
    mock_policy.assert_called_once_with(local_dc="AWS_US_EAST_1")
    assert instance._cluster_cls.call_args.kwargs["load_balancing_policy"] is mock_policy.return_value


def test_init_with_ssl_passes_verifying_context(session):
    with patch("mem0.vector_stores.scylladb.ssl.SSLContext") as mock_context_cls:
        instance = _make_store(session, use_ssl=True, ssl_cert_path="/tmp/ca.pem")

    context = mock_context_cls.return_value
    mock_context_cls.assert_called_once_with(ssl.PROTOCOL_TLS_CLIENT)
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    context.load_verify_locations.assert_called_once_with(cafile="/tmp/ca.pem")
    context.load_default_certs.assert_not_called()
    assert instance._cluster_cls.call_args.kwargs["ssl_context"] is context


def test_init_with_ssl_uses_default_ca_bundle(session):
    with patch("mem0.vector_stores.scylladb.ssl.SSLContext") as mock_context_cls:
        _make_store(session, use_ssl=True)

    mock_context_cls.return_value.load_default_certs.assert_called_once()
    mock_context_cls.return_value.load_verify_locations.assert_not_called()


def test_init_without_ssl_has_no_ssl_context(session):
    instance = _make_store(session)
    assert "ssl_context" not in instance._cluster_cls.call_args.kwargs


# ---------------------------------------------------------------------------
# create_col / reset
# ---------------------------------------------------------------------------


def test_create_col_with_custom_name_and_size(store, session):
    store.create_col(name="New_Collection", vector_size=256)

    assert "test_keyspace.new_collection" in session.executed("CREATE TABLE")[0][0]
    assert "VECTOR<FLOAT, 256>" in session.executed("CREATE TABLE")[0][0]
    assert len(session.executed("CREATE CUSTOM INDEX")) == 3


def test_reset_drops_and_recreates_table_and_indexes(store, session):
    store.reset()

    statements = [cql for cql, _ in session.calls]
    drop_idx = next(i for i, cql in enumerate(statements) if cql.startswith("DROP TABLE"))
    create_idx = next(i for i, cql in enumerate(statements) if cql.startswith("CREATE TABLE"))
    assert drop_idx < create_idx
    assert len(session.executed("CREATE CUSTOM INDEX")) == 3
    assert not session.executed("TRUNCATE")


# ---------------------------------------------------------------------------
# insert
# ---------------------------------------------------------------------------


def test_insert_writes_entity_columns(store, session):
    store.insert(
        vectors=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
        payloads=[{"data": "hello", "user_id": "alice"}, {"data": "world", "agent_id": "bot", "run_id": "r1"}],
        ids=["id1", "id2"],
    )

    inserts = session.executed("INSERT INTO")
    assert len(inserts) == 2
    assert inserts[0][1] == (
        "id1",
        [0.1, 0.2, 0.3],
        "alice",
        None,
        None,
        json.dumps({"data": "hello", "user_id": "alice"}),
    )
    assert inserts[1][1][2:5] == (None, "bot", "r1")


def test_insert_auto_generates_ids_and_payloads(store, session):
    store.insert(vectors=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])

    inserts = session.executed("INSERT INTO")
    assert len(inserts) == 2
    assert inserts[0][1][0] != inserts[1][1][0]
    assert inserts[0][1][5] == "{}"


@pytest.mark.parametrize(
    "vectors, payloads, ids",
    [
        ([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]], None, ["only-one"]),
        ([[0.1, 0.2, 0.3]], [{}, {}], ["id1"]),
        ([[0.1, 0.2, 0.3]], [{}], ["id1", "id2"]),
    ],
)
def test_insert_rejects_mismatched_lengths(store, session, vectors, payloads, ids):
    with pytest.raises(ValueError, match="same length"):
        store.insert(vectors=vectors, payloads=payloads, ids=ids)

    assert not session.executed("INSERT INTO")


def test_insert_unserializable_payload_writes_nothing(store, session):
    with pytest.raises(TypeError):
        store.insert(vectors=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]], payloads=[{}, {"bad": object()}], ids=["a", "b"])

    assert not session.executed("INSERT INTO")


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


def test_search_returns_similarity_scores_unchanged(store, session):
    session.responder = lambda cql, params: [
        _ann_row("id1", 1.0, {"user_id": "u"}),
        _ann_row("id2", 0.8, {"user_id": "u"}),
    ]

    results = store.search(query="q", vectors=[0.1, 0.2, 0.3], top_k=5, filters={"user_id": "u"})

    assert all(isinstance(r, OutputData) for r in results)
    assert [r.score for r in results] == [1.0, 0.8]


def test_search_scopes_ann_query_to_entity(store, session):
    session.responder = lambda cql, params: []

    store.search(query="q", vectors=[0.1, 0.2, 0.3], top_k=5, filters={"user_id": "alice"})

    cql, params = session.executed("ORDER BY vector ANN OF")[0]
    assert "WHERE user_id = ?" in cql
    assert "ALLOW FILTERING" not in cql
    assert params == ([0.1, 0.2, 0.3], "alice", [0.1, 0.2, 0.3], 5)


def test_search_with_multiple_entities_filters_within_scope(store, session):
    store.search(query="q", vectors=[0.1, 0.2, 0.3], top_k=5, filters={"user_id": "alice", "agent_id": "bot"})

    cql, params = session.executed("ORDER BY vector ANN OF")[0]
    assert "WHERE user_id = ? AND agent_id = ?" in cql
    assert cql.endswith("ALLOW FILTERING")
    assert params[1:3] == ("alice", "bot")


@pytest.mark.parametrize("filters", [None, {}, {"category": "books"}, {"user_id": "*"}])
def test_search_without_entity_scope_raises(store, session, filters):
    with pytest.raises(ValueError, match="user_id, agent_id or run_id"):
        store.search(query="q", vectors=[0.1, 0.2, 0.3], top_k=5, filters=filters)

    assert not session.calls


def test_search_respects_top_k(store, session):
    session.responder = lambda cql, params: [_ann_row(f"id{i}", 0.9, {"user_id": "u"}) for i in range(10)]

    results = store.search(query="q", vectors=[0.1, 0.2, 0.3], top_k=3, filters={"user_id": "u"})

    assert len(results) == 3


def test_search_clamps_limit_to_scylladb_maximum(store, session):
    store.search(query="q", vectors=[0.1, 0.2, 0.3], top_k=5000, filters={"user_id": "u"})

    assert session.executed("ORDER BY vector ANN OF")[0][1][-1] == 1000


def test_search_operator_filter_matches(store, session):
    session.responder = lambda cql, params: [
        _ann_row("id1", 0.95, {"user_id": "u", "category": "books"}),
        _ann_row("id2", 0.80, {"user_id": "u", "category": "music"}),
    ]

    results = store.search(
        query="q", vectors=[0.1, 0.2, 0.3], top_k=5, filters={"user_id": "u", "category": {"eq": "books"}}
    )

    assert [r.id for r in results] == ["id1"]


def test_search_refetches_with_larger_limit_when_payload_filters_prune(store, session):
    def responder(cql, params):
        limit = params[-1]
        rows = [_ann_row(f"miss{i}", 0.9, {"user_id": "u", "category": "music"}) for i in range(limit)]
        if limit > 2:
            rows[-1] = _ann_row("hit", 0.5, {"user_id": "u", "category": "books"})
        return rows

    session.responder = responder

    results = store.search(query="q", vectors=[0.1, 0.2, 0.3], top_k=1, filters={"user_id": "u", "category": "books"})

    assert [r.id for r in results] == ["hit"]
    assert [params[-1] for _, params in session.executed("ORDER BY vector ANN OF")] == [1, 4]


def test_search_stops_when_scope_is_exhausted(store, session):
    session.responder = lambda cql, params: [_ann_row("id1", 0.9, {"user_id": "u", "category": "music"})]

    results = store.search(query="q", vectors=[0.1, 0.2, 0.3], top_k=5, filters={"user_id": "u", "category": "books"})

    assert results == []
    assert len(session.executed("ORDER BY vector ANN OF")) == 1


def test_search_rejects_unsupported_operator(store, session):
    session.responder = lambda cql, params: [_ann_row("id1", 0.9, {"user_id": "u", "category": "books"})]

    with pytest.raises(ValueError, match="Unsupported filter operator"):
        store.search(
            query="q", vectors=[0.1, 0.2, 0.3], top_k=5, filters={"user_id": "u", "category": {"regex": "b.*"}}
        )


def test_search_propagates_database_errors(store, session):
    session.responder = lambda cql, params: RuntimeError("timeout")

    with pytest.raises(RuntimeError, match="timeout"):
        store.search(query="q", vectors=[0.1, 0.2, 0.3], top_k=5, filters={"user_id": "u"})


# ---------------------------------------------------------------------------
# Filter evaluation
# ---------------------------------------------------------------------------


PAYLOAD = {"user_id": "u", "category": "books", "rating": 4, "title": "Project Hail Mary"}


@pytest.mark.parametrize(
    "filters, expected",
    [
        ({"category": "books"}, True),
        ({"category": "music"}, False),
        ({"category": {"eq": "books"}}, True),
        ({"category": {"ne": "books"}}, False),
        ({"category": {"in": ["music", "books"]}}, True),
        ({"category": {"nin": ["music", "books"]}}, False),
        ({"rating": {"gt": 3}}, True),
        ({"rating": {"gte": 4, "lt": 5}}, True),
        ({"rating": {"lte": 3}}, False),
        ({"title": {"contains": "Hail"}}, True),
        ({"title": {"contains": "hail"}}, False),
        ({"title": {"icontains": "hail"}}, True),
        ({"category": "*"}, True),
        ({"missing": "*"}, False),
        ({"missing": {"eq": "x"}}, False),
        ({"category": ["music", "books"]}, True),
        ({"$or": [{"category": "music"}, {"rating": {"gte": 4}}]}, True),
        ({"$or": [{"category": "music"}, {"rating": {"gte": 5}}]}, False),
        ({"$not": [{"category": "music"}]}, True),
        ({"$not": [{"category": "books"}]}, False),
        ({"AND": [{"category": "books"}, {"rating": 4}]}, True),
    ],
)
def test_matches_filters(filters, expected):
    assert _matches_filters(PAYLOAD, filters) is expected


def test_matches_filters_in_requires_list():
    with pytest.raises(ValueError, match="requires a list"):
        _matches_filters(PAYLOAD, {"category": {"in": "books"}})


# ---------------------------------------------------------------------------
# delete / update / get
# ---------------------------------------------------------------------------


def test_delete(store, session):
    store.delete(vector_id="test_id")

    assert session.executed("DELETE FROM")[0][1] == ("test_id",)


def test_update_vector_and_payload_in_one_statement(store, session):
    store.update(vector_id="test_id", vector=[0.7, 0.8, 0.9], payload={"data": "updated", "user_id": "alice"})

    updates = session.executed("UPDATE")
    assert len(updates) == 1
    cql, params = updates[0]
    assert "SET vector = ?, user_id = ?, agent_id = ?, run_id = ?, payload = ? WHERE id = ?" in cql
    assert params == (
        [0.7, 0.8, 0.9],
        "alice",
        None,
        None,
        json.dumps({"data": "updated", "user_id": "alice"}),
        "test_id",
    )


def test_update_only_payload(store, session):
    store.update(vector_id="test_id", payload={"data": "new"})

    cql, _ = session.executed("UPDATE")[0]
    assert "vector" not in cql
    assert "payload = ?" in cql


def test_update_only_vector(store, session):
    store.update(vector_id="test_id", vector=[0.1, 0.2, 0.3])

    cql, params = session.executed("UPDATE")[0]
    assert "SET vector = ? WHERE id = ?" in cql
    assert params == ([0.1, 0.2, 0.3], "test_id")


def test_update_unserializable_payload_writes_nothing(store, session):
    with pytest.raises(TypeError):
        store.update(vector_id="test_id", vector=[0.1, 0.2, 0.3], payload={"bad": object()})

    assert not session.executed("UPDATE")


def test_get_existing_record(store, session):
    session.responder = lambda cql, params: [_row("test_id", {"data": "hello"})]

    result = store.get(vector_id="test_id")

    assert isinstance(result, OutputData)
    assert result.id == "test_id"
    assert result.payload == {"data": "hello"}
    assert result.score is None


def test_get_missing_record_returns_none(store, session):
    assert store.get(vector_id="nonexistent") is None


def test_get_propagates_database_errors(store, session):
    session.responder = lambda cql, params: RuntimeError("timeout")

    with pytest.raises(RuntimeError, match="timeout"):
        store.get(vector_id="test_id")


# ---------------------------------------------------------------------------
# list_cols / delete_col / col_info
# ---------------------------------------------------------------------------


def test_list_cols(store, session):
    session.responder = lambda cql, params: [Mock(table_name="table_a"), Mock(table_name="table_b")]

    assert store.list_cols() == ["table_a", "table_b"]
    assert session.calls[0][1] == ("test_keyspace",)


def test_list_cols_propagates_database_errors(store, session):
    session.responder = lambda cql, params: RuntimeError("timeout")

    with pytest.raises(RuntimeError):
        store.list_cols()


def test_delete_col(store, session):
    store.delete_col()

    assert session.executed("DROP TABLE IF EXISTS test_keyspace.test_collection")


def test_col_info(store, session):
    session.responder = lambda cql, params: [Mock(count=42)]

    info = store.col_info()

    assert info == {"name": "test_collection", "keyspace": "test_keyspace", "count": 42, "vector_dims": 3}


def test_col_info_propagates_database_errors(store, session):
    session.responder = lambda cql, params: RuntimeError("timeout")

    with pytest.raises(RuntimeError):
        store.col_info()


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def test_list_all_is_paged(store, session):
    session.responder = lambda cql, params: [_row("id1", {"text": "a"}), _row("id2", {"text": "b"})]

    results = store.list(top_k=10)

    assert [r.id for r in results[0]] == ["id1", "id2"]
    assert session.calls[0][0] == "SELECT id, payload FROM test_keyspace.test_collection"
    assert session.last_bound.fetch_size == 1000


def test_list_scopes_query_to_entity(store, session):
    store.list(filters={"user_id": "alice"}, top_k=10)

    cql, params = session.calls[0]
    assert cql.endswith("WHERE user_id = ?")
    assert params == ("alice",)


def test_list_with_multiple_entities(store, session):
    store.list(filters={"user_id": "alice", "run_id": "r1"}, top_k=10)

    cql, params = session.calls[0]
    assert "WHERE user_id = ? AND run_id = ? ALLOW FILTERING" in cql
    assert params == ("alice", "r1")


def test_list_applies_limit_after_filtering(store, session):
    # 1,000 non-matching rows come back before the matching ones.
    rows = [_row(f"other{i}", {"user_id": "u", "category": "music"}) for i in range(1000)]
    rows += [_row(f"hit{i}", {"user_id": "u", "category": "books"}) for i in range(3)]
    session.responder = lambda cql, params: rows

    results = store.list(filters={"user_id": "u", "category": {"eq": "books"}}, top_k=2)

    assert [r.id for r in results[0]] == ["hit0", "hit1"]


def test_list_propagates_database_errors(store, session):
    session.responder = lambda cql, params: RuntimeError("timeout")

    with pytest.raises(RuntimeError, match="timeout"):
        store.list(filters={"user_id": "u"})


# ---------------------------------------------------------------------------
# _wait_for_index_ready
# ---------------------------------------------------------------------------


def test_wait_for_index_ready_probes_every_local_index(store, session):
    store._wait_for_index_ready("test_collection", 3)

    probes = [cql for cql, _ in session.calls]
    assert len(probes) == 3
    assert [p.split("WHERE ")[1].split(" =")[0] for p in probes] == ["user_id", "agent_id", "run_id"]


@pytest.mark.parametrize(
    "transient_error",
    [
        "... is not available yet ...",
        'Error from server: code=2200 [Invalid query] message="Vector Store error: '
        'HTTP status 404 Not Found, message: missing index: test_keyspace.test_collection_user_id_ann"',
    ],
)
def test_wait_for_index_ready_retries_transient_errors(store, session, transient_error):
    errors = [Exception(transient_error)]
    session.responder = lambda cql, params: errors.pop() if errors else []

    with patch("mem0.vector_stores.scylladb.time.sleep"):
        store._wait_for_index_ready("test_collection", 3)

    assert len(session.calls) == 4


def test_wait_for_index_ready_raises_on_unrelated_error(store, session):
    session.responder = lambda cql, params: Exception("syntax error")

    with pytest.raises(Exception, match="syntax error"):
        store._wait_for_index_ready("test_collection", 3)


# ---------------------------------------------------------------------------
# OutputData / config
# ---------------------------------------------------------------------------


def test_output_data_model():
    data = OutputData(id="abc", score=0.95, payload={"key": "value"})
    assert data.id == "abc"
    assert data.score == 0.95
    assert data.payload == {"key": "value"}


def test_output_data_allows_none():
    data = OutputData(id=None, score=None, payload=None)
    assert data.id is None
    assert data.score is None


def test_config_defaults():
    config = ScyllaDBConfig(contact_points=["127.0.0.1"])
    assert config.replication_factor == 3
    assert config.use_ssl is False


def test_config_rejects_invalid_replication_factor():
    with pytest.raises(ValidationError):
        ScyllaDBConfig(contact_points=["127.0.0.1"], replication_factor=0)


def test_config_rejects_extra_fields():
    with pytest.raises(ValidationError, match="Extra fields not allowed"):
        ScyllaDBConfig(contact_points=["127.0.0.1"], replication="3")
