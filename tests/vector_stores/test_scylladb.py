import json
from unittest.mock import Mock, patch

import pytest

from mem0.vector_stores.scylladb import (
    ScyllaDB,
    OutputData,
    _matches_filters,
)


@pytest.fixture
def mock_session():
    """Create a mock CQL session."""
    session = Mock()
    session.execute = Mock(return_value=Mock())
    session.prepare = Mock(side_effect=lambda cql: f"prepared:{cql}")
    session.set_keyspace = Mock()
    return session


@pytest.fixture
def mock_cluster(mock_session):
    """Create a mock cluster returning the mock session."""
    cluster = Mock()
    cluster.connect = Mock(return_value=mock_session)
    cluster.shutdown = Mock()
    return cluster


@pytest.fixture
def scylladb_instance(mock_cluster, mock_session):
    """Create a ScyllaDB instance with a mocked cluster."""
    with patch("mem0.vector_stores.scylladb.Cluster") as mock_cluster_class:
        mock_cluster_class.return_value = mock_cluster
        instance = ScyllaDB(
            contact_points=["127.0.0.1"],
            port=9042,
            username="testuser",
            password="testpass",
            keyspace="test_keyspace",
            collection_name="test_collection",
            embedding_model_dims=128,
        )
        instance.session = mock_session
        return instance


def _make_row(row_id, score=None, payload=None):
    row = Mock()
    row.id = row_id
    row.score = score
    row.payload = json.dumps(payload) if payload is not None else None
    return row


def _executed_cql(mock_session):
    """All CQL strings passed to session.execute (unprepared calls)."""
    return [call.args[0] for call in mock_session.execute.call_args_list]


def _prepared_cql(mock_session):
    return [call.args[0] for call in mock_session.prepare.call_args_list]


class TestInit:
    def test_init_creates_keyspace_table_and_index(self, mock_cluster, mock_session):
        with patch("mem0.vector_stores.scylladb.Cluster") as mock_cluster_class:
            mock_cluster_class.return_value = mock_cluster
            ScyllaDB(
                contact_points=["127.0.0.1"],
                keyspace="ks",
                collection_name="coll",
                embedding_model_dims=128,
            )

        cql = _executed_cql(mock_session)
        assert any("CREATE KEYSPACE IF NOT EXISTS ks" in stmt for stmt in cql)
        assert any("CREATE TABLE IF NOT EXISTS ks.coll" in stmt and "VECTOR<FLOAT, 128>" in stmt for stmt in cql)
        index_stmts = [stmt for stmt in cql if "CREATE CUSTOM INDEX" in stmt]
        assert len(index_stmts) == 1
        # Scope columns ride the vector index as filtering columns.
        assert "(vector, user_id, agent_id, run_id)" in index_stmts[0]
        assert "'similarity_function': 'COSINE'" in index_stmts[0]
        mock_session.set_keyspace.assert_called_with("ks")

    def test_init_normalizes_identifiers_to_lowercase(self, mock_cluster, mock_session):
        """Unquoted CQL folds identifiers to lowercase; the driver quotes USE.

        Normalizing at init keeps both consistent (regression: 'MyMem0' used
        to create keyspace 'mymem0' but then failed set_keyspace('MyMem0')).
        """
        with patch("mem0.vector_stores.scylladb.Cluster") as mock_cluster_class:
            mock_cluster_class.return_value = mock_cluster
            instance = ScyllaDB(
                contact_points=["127.0.0.1"],
                keyspace="MyMem0",
                collection_name="MyColl",
                embedding_model_dims=128,
            )

        assert instance.keyspace == "mymem0"
        assert instance.collection_name == "mycoll"
        cql = _executed_cql(mock_session)
        assert any("CREATE KEYSPACE IF NOT EXISTS mymem0" in stmt for stmt in cql)
        mock_session.set_keyspace.assert_called_with("mymem0")

    def test_init_rejects_invalid_identifier(self, mock_cluster):
        with patch("mem0.vector_stores.scylladb.Cluster") as mock_cluster_class:
            mock_cluster_class.return_value = mock_cluster
            with pytest.raises(ValueError, match="Invalid keyspace"):
                ScyllaDB(contact_points=["127.0.0.1"], keyspace="bad;drop")

    def test_init_rejects_unsupported_distance(self, mock_cluster):
        with patch("mem0.vector_stores.scylladb.Cluster") as mock_cluster_class:
            mock_cluster_class.return_value = mock_cluster
            with pytest.raises(ValueError, match="Unsupported distance metric"):
                ScyllaDB(contact_points=["127.0.0.1"], distance="manhattan")

    def test_init_waits_for_index_readiness(self, mock_cluster, mock_session):
        """The vector index builds asynchronously; transient 'not available
        yet' errors on the probe query must be retried until ready."""
        mock_session.execute = Mock(
            side_effect=[
                None,  # CREATE KEYSPACE
                None,  # CREATE TABLE
                None,  # CREATE CUSTOM INDEX
                Exception("vector index on coll is not available yet"),  # probe 1
                None,  # probe 2: ready
            ]
        )
        with (
            patch("mem0.vector_stores.scylladb.Cluster") as mock_cluster_class,
            patch("mem0.vector_stores.scylladb.time.sleep") as mock_sleep,
        ):
            mock_cluster_class.return_value = mock_cluster
            ScyllaDB(contact_points=["127.0.0.1"], collection_name="coll", embedding_model_dims=8)

        mock_sleep.assert_called_once_with(1)

    def test_init_raises_on_non_transient_probe_error(self, mock_cluster, mock_session):
        mock_session.execute = Mock(side_effect=[None, None, None, Exception("unconfigured table")])
        with patch("mem0.vector_stores.scylladb.Cluster") as mock_cluster_class:
            mock_cluster_class.return_value = mock_cluster
            with pytest.raises(Exception, match="unconfigured table"):
                ScyllaDB(contact_points=["127.0.0.1"], embedding_model_dims=8)

    def test_init_uses_ssl_and_datacenter(self, mock_cluster, mock_session):
        with patch("mem0.vector_stores.scylladb.Cluster") as mock_cluster_class:
            mock_cluster_class.return_value = mock_cluster
            ScyllaDB(
                contact_points=["node-0.example.scylla.cloud"],
                datacenter="AWS_US_EAST_1",
                use_ssl=True,
                embedding_model_dims=8,
            )
        kwargs = mock_cluster_class.call_args.kwargs
        assert "ssl_context" in kwargs
        assert kwargs["ssl_context"].check_hostname is True
        assert kwargs["load_balancing_policy"].local_dc == "AWS_US_EAST_1"


class TestInsert:
    def test_insert_extracts_scope_columns(self, scylladb_instance, mock_session):
        mock_session.reset_mock()
        scylladb_instance.insert(
            vectors=[[0.1, 0.2]],
            payloads=[{"data": "hello", "user_id": "alice", "run_id": "r1"}],
            ids=["id1"],
        )

        insert_cql = [c for c in _prepared_cql(mock_session) if "INSERT INTO" in c]
        assert len(insert_cql) == 1
        assert "(id, vector, payload, user_id, agent_id, run_id)" in insert_cql[0]
        params = mock_session.execute.call_args.args[1]
        assert params[0] == "id1"
        assert params[1] == [0.1, 0.2]
        assert json.loads(params[2])["user_id"] == "alice"
        assert params[3:] == ("alice", None, "r1")

    def test_insert_generates_ids_when_missing(self, scylladb_instance, mock_session):
        mock_session.reset_mock()
        scylladb_instance.insert(vectors=[[0.1]], payloads=[{}])
        params = mock_session.execute.call_args.args[1]
        assert isinstance(params[0], str) and len(params[0]) == 36

    def test_insert_rejects_mismatched_lengths(self, scylladb_instance, mock_session):
        """zip() would silently truncate; a length mismatch must fail loudly
        before anything is written."""
        mock_session.reset_mock()
        with pytest.raises(ValueError, match="matching lengths"):
            scylladb_instance.insert(vectors=[[0.1], [0.2]], payloads=[{}, {}], ids=["only-one"])
        mock_session.execute.assert_not_called()


class TestSearch:
    def test_search_returns_similarity_unchanged(self, scylladb_instance, mock_session):
        """VectorStoreBase requires higher = more similar. The ANN similarity
        score must be returned as-is, never inverted (regression)."""
        mock_session.reset_mock()
        mock_session.execute.return_value = [
            _make_row("exact", 1.0, {"data": "a"}),
            _make_row("weak", 0.4, {"data": "b"}),
        ]
        results = scylladb_instance.search("q", [0.1, 0.2], top_k=2)

        assert [r.id for r in results] == ["exact", "weak"]
        assert results[0].score == 1.0
        assert results[1].score == 0.4
        assert all(isinstance(r, OutputData) for r in results)

    def test_search_pushes_scope_filters_into_cql(self, scylladb_instance, mock_session):
        mock_session.reset_mock()
        mock_session.execute.return_value = []
        scylladb_instance.search("q", [0.1], top_k=5, filters={"user_id": "alice"})

        cql = mock_session.prepare.call_args.args[0]
        assert "WHERE user_id = ?" in cql
        assert "ORDER BY vector ANN OF ? LIMIT ?" in cql
        assert cql.endswith("ALLOW FILTERING")
        params = mock_session.execute.call_args.args[1]
        # score vector, scope value, ANN vector, limit
        assert params == ([0.1], "alice", [0.1], 5)

    def test_search_pushes_eq_operator_scope(self, scylladb_instance, mock_session):
        """Memory passes operator dicts; {"eq": ...} on a scope field must be
        pushed down like a bare value (regression)."""
        mock_session.reset_mock()
        mock_session.execute.return_value = []
        scylladb_instance.search("q", [0.1], top_k=3, filters={"user_id": {"eq": "bob"}, "agent_id": "agt"})
        cql = mock_session.prepare.call_args.args[0]
        assert "WHERE user_id = ? AND agent_id = ?" in cql
        assert mock_session.execute.call_args.args[1][1:3] == ("bob", "agt")

    def test_search_without_filters_uses_plain_ann(self, scylladb_instance, mock_session):
        mock_session.reset_mock()
        mock_session.execute.return_value = []
        scylladb_instance.search("q", [0.1], top_k=5)
        cql = mock_session.prepare.call_args.args[0]
        assert "WHERE" not in cql
        assert "ALLOW FILTERING" not in cql

    def test_search_widens_window_until_matches_found(self, scylladb_instance, mock_session):
        """Residual (non-scope) filters must not be defeated by a fixed global
        candidate limit: the ANN window grows until top_k matches are found
        (regression for scoped/conditional retrieval)."""
        mock_session.reset_mock()
        other = _make_row("other", 0.9, {"category": "noise"})
        hit1 = _make_row("hit1", 0.8, {"category": "books"})
        hit2 = _make_row("hit2", 0.7, {"category": "books"})
        # First window (limit=2): only noise. Second window (limit=8): matches.
        mock_session.execute.side_effect = [[other, other], [other, other, hit1, hit2]]

        results = scylladb_instance.search("q", [0.1], top_k=2, filters={"category": "books"})

        assert [r.id for r in results] == ["hit1", "hit2"]
        limits = [call.args[1][-1] for call in mock_session.execute.call_args_list]
        assert limits == [2, 8]

    def test_search_stops_when_window_exhausted(self, scylladb_instance, mock_session):
        mock_session.reset_mock()
        mock_session.execute.return_value = [_make_row("x", 0.5, {"category": "noise"})]
        results = scylladb_instance.search("q", [0.1], top_k=5, filters={"category": "books"})
        assert results == []
        # one page smaller than the limit means there is nothing more to scan
        assert mock_session.execute.call_count == 1

    def test_search_residual_operator_dict(self, scylladb_instance, mock_session):
        mock_session.reset_mock()
        mock_session.execute.return_value = [
            _make_row("a", 0.9, {"category": "books", "year": 2020}),
            _make_row("b", 0.8, {"category": "books", "year": 2026}),
        ]
        results = scylladb_instance.search(
            "q", [0.1], top_k=5, filters={"category": {"eq": "books"}, "year": {"gte": 2025}}
        )
        assert [r.id for r in results] == ["b"]

    def test_search_rejects_unknown_operator(self, scylladb_instance, mock_session):
        mock_session.reset_mock()
        mock_session.execute.return_value = [_make_row("a", 0.9, {"category": "books"})]
        with pytest.raises(ValueError, match="Unsupported filter operator"):
            scylladb_instance.search("q", [0.1], filters={"category": {"bogus": "x"}})

    def test_search_reraises_db_errors(self, scylladb_instance, mock_session):
        mock_session.reset_mock()
        mock_session.execute.side_effect = Exception("timeout")
        with pytest.raises(Exception, match="timeout"):
            scylladb_instance.search("q", [0.1])


class TestUpdate:
    def test_update_writes_all_columns_in_one_statement(self, scylladb_instance, mock_session):
        """Vector and payload must be updated atomically: one CQL statement,
        payload serialized before anything is written (regression)."""
        mock_session.reset_mock()
        scylladb_instance.update("id1", vector=[0.3], payload={"data": "new", "user_id": "alice"})

        mock_session.prepare.assert_called_once()
        cql = mock_session.prepare.call_args.args[0]
        assert cql.startswith("UPDATE test_keyspace.test_collection SET")
        assert "vector = ?" in cql and "payload = ?" in cql
        assert "user_id = ?" in cql and "agent_id = ?" in cql and "run_id = ?" in cql
        mock_session.execute.assert_called_once()
        params = mock_session.execute.call_args.args[1]
        assert params == ([0.3], json.dumps({"data": "new", "user_id": "alice"}), "alice", None, None, "id1")

    def test_update_payload_only_keeps_scope_in_sync(self, scylladb_instance, mock_session):
        mock_session.reset_mock()
        scylladb_instance.update("id1", payload={"user_id": "carol"})
        cql = mock_session.prepare.call_args.args[0]
        assert "vector = ?" not in cql
        assert "payload = ?" in cql and "user_id = ?" in cql
        params = mock_session.execute.call_args.args[1]
        assert params[1:] == ("carol", None, None, "id1")

    def test_update_serializes_payload_before_writing(self, scylladb_instance, mock_session):
        """An unserializable payload must fail before any CQL is executed."""
        mock_session.reset_mock()
        with pytest.raises(TypeError):
            scylladb_instance.update("id1", vector=[0.1], payload={"bad": object()})
        mock_session.execute.assert_not_called()

    def test_update_noop_when_nothing_given(self, scylladb_instance, mock_session):
        mock_session.reset_mock()
        scylladb_instance.update("id1")
        mock_session.execute.assert_not_called()


class TestGet:
    def test_get_returns_record(self, scylladb_instance, mock_session):
        mock_session.reset_mock()
        mock_session.execute.return_value.one.return_value = _make_row("id1", payload={"data": "x"})
        result = scylladb_instance.get("id1")
        assert result.id == "id1"
        assert result.payload == {"data": "x"}

    def test_get_returns_none_when_missing(self, scylladb_instance, mock_session):
        mock_session.reset_mock()
        mock_session.execute.return_value.one.return_value = None
        assert scylladb_instance.get("missing") is None

    def test_get_reraises_db_errors(self, scylladb_instance, mock_session):
        """A timeout must not masquerade as 'record does not exist'
        (regression: update/delete would otherwise report invalid IDs)."""
        mock_session.reset_mock()
        mock_session.execute.side_effect = Exception("connection lost")
        with pytest.raises(Exception, match="connection lost"):
            scylladb_instance.get("id1")


class TestList:
    def test_list_scans_past_non_matching_rows(self, scylladb_instance, mock_session):
        """Regression: a fixed LIMIT applied before filtering made
        Memory.delete_all() silently miss a user's memories when other users'
        rows came first. The scan must continue until matches are found."""
        mock_session.reset_mock()
        rows = [_make_row(f"other-{i}", payload={"user_id": "alice"}) for i in range(1000)]
        rows.append(_make_row("target", payload={"user_id": "bob"}))
        mock_session.execute.return_value = rows

        results = scylladb_instance.list(filters={"user_id": "bob"}, top_k=5)

        assert len(results) == 1
        assert [r.id for r in results[0]] == ["target"]
        # scope filter is also pushed into CQL
        cql = mock_session.prepare.call_args.args[0]
        assert "WHERE user_id = ?" in cql and "ALLOW FILTERING" in cql

    def test_list_stops_at_top_k(self, scylladb_instance, mock_session):
        mock_session.reset_mock()
        mock_session.execute.return_value = [_make_row(f"id-{i}", payload={"v": i}) for i in range(10)]
        results = scylladb_instance.list(top_k=3)
        assert [r.id for r in results[0]] == ["id-0", "id-1", "id-2"]

    def test_list_applies_operator_filters(self, scylladb_instance, mock_session):
        mock_session.reset_mock()
        mock_session.execute.return_value = [
            _make_row("a", payload={"year": 2020}),
            _make_row("b", payload={"year": 2026}),
        ]
        results = scylladb_instance.list(filters={"year": {"gte": 2025}})
        assert [r.id for r in results[0]] == ["b"]

    def test_list_reraises_db_errors(self, scylladb_instance, mock_session):
        """An outage must propagate: delete_all() may never report success on
        a failed read (regression)."""
        mock_session.reset_mock()
        mock_session.execute.side_effect = Exception("node down")
        with pytest.raises(Exception, match="node down"):
            scylladb_instance.list(filters={"user_id": "alice"})


class TestDeleteAndReset:
    def test_delete(self, scylladb_instance, mock_session):
        mock_session.reset_mock()
        scylladb_instance.delete("id1")
        cql = mock_session.prepare.call_args.args[0]
        assert "DELETE FROM test_keyspace.test_collection WHERE id = ?" in cql
        assert mock_session.execute.call_args.args[1] == ("id1",)

    def test_reset_drops_and_recreates_instead_of_truncate(self, scylladb_instance, mock_session):
        """TRUNCATE does not propagate to the CDC log, so the vector index
        would keep stale vectors; reset must DROP + recreate."""
        mock_session.reset_mock()
        scylladb_instance.reset()
        cql = _executed_cql(mock_session)
        assert not any("TRUNCATE" in stmt for stmt in cql)
        assert cql[0].startswith("DROP TABLE IF EXISTS test_keyspace.test_collection")
        assert any("CREATE TABLE IF NOT EXISTS" in stmt for stmt in cql)
        assert any("CREATE CUSTOM INDEX" in stmt for stmt in cql)


class TestCollectionAdmin:
    def test_list_cols(self, scylladb_instance, mock_session):
        mock_session.reset_mock()
        row = Mock()
        row.table_name = "memories"
        mock_session.execute.return_value = [row]
        assert scylladb_instance.list_cols() == ["memories"]

    def test_col_info(self, scylladb_instance, mock_session):
        mock_session.reset_mock()
        row = Mock()
        row.count = 42
        mock_session.execute.return_value.one.return_value = row
        info = scylladb_instance.col_info()
        assert info["count"] == 42
        assert info["vector_dims"] == 128

    def test_delete_col(self, scylladb_instance, mock_session):
        mock_session.reset_mock()
        scylladb_instance.delete_col()
        cql = _executed_cql(mock_session)
        assert any("DROP TABLE IF EXISTS test_keyspace.test_collection" in stmt for stmt in cql)


class TestFilterPredicate:
    """Client-side predicate following mem0's operator convention."""

    def test_bare_value_means_equality(self):
        assert _matches_filters({"a": 1}, {"a": 1})
        assert not _matches_filters({"a": 1}, {"a": 2})

    def test_comparison_operators(self):
        payload = {"n": 5}
        assert _matches_filters(payload, {"n": {"gt": 4, "lt": 6}})
        assert _matches_filters(payload, {"n": {"gte": 5, "lte": 5}})
        assert not _matches_filters(payload, {"n": {"ne": 5}})
        assert _matches_filters(payload, {"n": {"eq": 5}})

    def test_list_operators(self):
        assert _matches_filters({"c": "x"}, {"c": {"in": ["x", "y"]}})
        assert _matches_filters({"c": "x"}, {"c": {"nin": ["y", "z"]}})
        assert not _matches_filters({"c": "x"}, {"c": {"in": ["y"]}})

    def test_contains_operators(self):
        assert _matches_filters({"s": "science fiction"}, {"s": {"contains": "fiction"}})
        assert _matches_filters({"s": "Science"}, {"s": {"icontains": "science"}})
        assert _matches_filters({"tags": ["a", "b"]}, {"tags": {"contains": "b"}})
        assert not _matches_filters({"s": "fantasy"}, {"s": {"contains": "fiction"}})

    def test_logical_operators(self):
        payload = {"a": 1, "b": 2}
        assert _matches_filters(payload, {"AND": [{"a": 1}, {"b": 2}]})
        assert _matches_filters(payload, {"OR": [{"a": 9}, {"b": 2}]})
        assert _matches_filters(payload, {"NOT": [{"a": 9}]})
        assert not _matches_filters(payload, {"AND": [{"a": 1}, {"b": 9}]})

    def test_unknown_operator_raises(self):
        with pytest.raises(ValueError, match="Unsupported filter operator"):
            _matches_filters({"a": 1}, {"a": {"approx": 1}})


class TestRegistration:
    def test_provider_registered_in_config(self):
        from mem0.vector_stores.configs import VectorStoreConfig

        cfg = VectorStoreConfig(provider="scylladb", config={"contact_points": ["127.0.0.1"]})
        assert cfg.provider == "scylladb"

    def test_provider_registered_in_factory(self):
        from mem0.utils.factory import VectorStoreFactory

        assert VectorStoreFactory.provider_to_class["scylladb"] == "mem0.vector_stores.scylladb.ScyllaDB"
