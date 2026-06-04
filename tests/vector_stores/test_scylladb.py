import json
from unittest.mock import Mock, patch

import pytest

from mem0.vector_stores.scylladb import OutputData, ScyllaDB


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session():
    session = Mock()
    session.execute = Mock(return_value=Mock())
    session.prepare = Mock(return_value=Mock())
    session.set_keyspace = Mock()
    return session


@pytest.fixture
def mock_cluster(mock_session):
    cluster = Mock()
    cluster.connect = Mock(return_value=mock_session)
    cluster.shutdown = Mock()
    return cluster


@pytest.fixture
def scylladb_instance(mock_cluster, mock_session):
    """ScyllaDB instance backed by a mocked cluster/session."""
    with patch("mem0.vector_stores.scylladb.Cluster") as mock_cluster_class:
        mock_cluster_class.return_value = mock_cluster

        instance = ScyllaDB(
            contact_points=["127.0.0.1"],
            port=9042,
            username="testuser",
            password="testpass",
            keyspace="test_keyspace",
            collection_name="test_collection",
            embedding_model_dims=3,
        )
        # Reset call history accumulated during __init__ (keyspace/table creation).
        mock_session.reset_mock()
        return instance


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


def test_init_stores_config(mock_cluster, mock_session):
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

    assert instance.contact_points == ["127.0.0.1"]
    assert instance.port == 9042
    assert instance.username == "testuser"
    assert instance.keyspace == "test_keyspace"
    assert instance.collection_name == "test_collection"
    assert instance.embedding_model_dims == 128


def test_init_with_ssl_and_datacenter(mock_cluster, mock_session):
    with (
        patch("mem0.vector_stores.scylladb.Cluster") as mock_cluster_class,
        patch("mem0.vector_stores.scylladb.DCAwareRoundRobinPolicy") as mock_policy,
    ):
        mock_cluster_class.return_value = mock_cluster

        instance = ScyllaDB(
            contact_points=["node-0.aws-us-east-1.x.clusters.scylla.cloud"],
            port=9042,
            username="scylla",
            password="secret",
            keyspace="mem0",
            collection_name="memories",
            embedding_model_dims=1536,
            datacenter="AWS_US_EAST_1"
        )

    assert instance.datacenter == "AWS_US_EAST_1"
    mock_policy.assert_called_once_with(local_dc="AWS_US_EAST_1")


def test_invalid_keyspace_name_rejected(mock_cluster, mock_session):
    with patch("mem0.vector_stores.scylladb.Cluster") as mock_cluster_class:
        mock_cluster_class.return_value = mock_cluster

        with pytest.raises(ValueError, match="Invalid keyspace"):
            ScyllaDB(
                contact_points=["127.0.0.1"],
                keyspace="bad keyspace!",
                collection_name="memories",
                embedding_model_dims=3,
            )


# ---------------------------------------------------------------------------
# create_col
# ---------------------------------------------------------------------------


def test_create_col(scylladb_instance):
    scylladb_instance.create_col(name="new_collection", vector_size=256)

    assert scylladb_instance.session.execute.called


# ---------------------------------------------------------------------------
# insert
# ---------------------------------------------------------------------------


def test_insert(scylladb_instance):
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    payloads = [{"text": "hello"}, {"text": "world"}]
    ids = ["id1", "id2"]

    mock_prepared = Mock()
    scylladb_instance.session.prepare = Mock(return_value=mock_prepared)

    scylladb_instance.insert(vectors=vectors, payloads=payloads, ids=ids)

    scylladb_instance.session.prepare.assert_called_once()
    assert scylladb_instance.session.execute.call_count == 2


def test_insert_auto_generates_ids(scylladb_instance):
    mock_prepared = Mock()
    scylladb_instance.session.prepare = Mock(return_value=mock_prepared)

    scylladb_instance.insert(vectors=[[0.1, 0.2, 0.3]])

    # execute is called once for the insert
    assert scylladb_instance.session.execute.called


def test_insert_without_payloads(scylladb_instance):
    mock_prepared = Mock()
    scylladb_instance.session.prepare = Mock(return_value=mock_prepared)

    scylladb_instance.insert(vectors=[[0.1, 0.2, 0.3]], ids=["id1"])

    assert scylladb_instance.session.prepare.called
    assert scylladb_instance.session.execute.called


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


def _make_ann_row(id_, score, payload_dict):
    row = Mock()
    row.id = id_
    row.score = score
    row.payload = json.dumps(payload_dict)
    return row


def test_search_returns_results(scylladb_instance):
    rows = [
        _make_ann_row("id1", 0.95, {"text": "alpha"}),
        _make_ann_row("id2", 0.80, {"text": "beta"}),
    ]
    mock_prepared = Mock()
    scylladb_instance.session.prepare = Mock(return_value=mock_prepared)
    scylladb_instance.session.execute = Mock(return_value=rows)

    results = scylladb_instance.search(query="test", vectors=[0.1, 0.2, 0.3], top_k=5)

    assert isinstance(results, list)
    assert len(results) == 2
    assert all(isinstance(r, OutputData) for r in results)


def test_search_score_is_inverted_similarity(scylladb_instance):
    """score returned to Mem0 should be distance (1 - cosine_similarity)."""
    rows = [_make_ann_row("id1", 0.9, {"text": "alpha"})]
    mock_prepared = Mock()
    scylladb_instance.session.prepare = Mock(return_value=mock_prepared)
    scylladb_instance.session.execute = Mock(return_value=rows)

    results = scylladb_instance.search(query="q", vectors=[0.1, 0.2, 0.3], top_k=5)

    assert pytest.approx(results[0].score, abs=1e-6) == 0.1  # 1.0 - 0.9


def test_search_respects_top_k(scylladb_instance):
    rows = [_make_ann_row(f"id{i}", 0.9 - i * 0.1, {"text": f"item {i}"}) for i in range(10)]
    mock_prepared = Mock()
    scylladb_instance.session.prepare = Mock(return_value=mock_prepared)
    scylladb_instance.session.execute = Mock(return_value=rows)

    results = scylladb_instance.search(query="q", vectors=[0.1, 0.2, 0.3], top_k=3)

    assert len(results) == 3


def test_search_with_filters(scylladb_instance):
    rows = [
        _make_ann_row("id1", 0.95, {"text": "alpha", "category": "A"}),
        _make_ann_row("id2", 0.80, {"text": "beta", "category": "B"}),
    ]
    mock_prepared = Mock()
    scylladb_instance.session.prepare = Mock(return_value=mock_prepared)
    scylladb_instance.session.execute = Mock(return_value=rows)

    results = scylladb_instance.search(
        query="q", vectors=[0.1, 0.2, 0.3], top_k=5, filters={"category": "A"}
    )

    assert len(results) == 1
    assert results[0].payload["category"] == "A"


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


def test_delete(scylladb_instance):
    mock_prepared = Mock()
    scylladb_instance.session.prepare = Mock(return_value=mock_prepared)

    scylladb_instance.delete(vector_id="test_id")

    scylladb_instance.session.prepare.assert_called_once()
    scylladb_instance.session.execute.assert_called_once()


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


def test_update_vector_and_payload(scylladb_instance):
    mock_prepared = Mock()
    scylladb_instance.session.prepare = Mock(return_value=mock_prepared)

    scylladb_instance.update(
        vector_id="test_id",
        vector=[0.7, 0.8, 0.9],
        payload={"text": "updated"},
    )

    # Two UPDATE statements: one for vector, one for payload
    assert scylladb_instance.session.prepare.call_count == 2
    assert scylladb_instance.session.execute.call_count == 2


def test_update_only_payload(scylladb_instance):
    mock_prepared = Mock()
    scylladb_instance.session.prepare = Mock(return_value=mock_prepared)

    scylladb_instance.update(vector_id="test_id", payload={"text": "new"})

    assert scylladb_instance.session.prepare.call_count == 1
    assert scylladb_instance.session.execute.call_count == 1


def test_update_only_vector(scylladb_instance):
    mock_prepared = Mock()
    scylladb_instance.session.prepare = Mock(return_value=mock_prepared)

    scylladb_instance.update(vector_id="test_id", vector=[0.1, 0.2, 0.3])

    assert scylladb_instance.session.prepare.call_count == 1


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


def test_get_existing_record(scylladb_instance):
    mock_row = Mock()
    mock_row.id = "test_id"
    mock_row.payload = json.dumps({"text": "hello"})

    mock_result = Mock()
    mock_result.one = Mock(return_value=mock_row)

    mock_prepared = Mock()
    scylladb_instance.session.prepare = Mock(return_value=mock_prepared)
    scylladb_instance.session.execute = Mock(return_value=mock_result)

    result = scylladb_instance.get(vector_id="test_id")

    assert result is not None
    assert isinstance(result, OutputData)
    assert result.id == "test_id"
    assert result.payload == {"text": "hello"}
    assert result.score is None


def test_get_missing_record_returns_none(scylladb_instance):
    mock_result = Mock()
    mock_result.one = Mock(return_value=None)

    mock_prepared = Mock()
    scylladb_instance.session.prepare = Mock(return_value=mock_prepared)
    scylladb_instance.session.execute = Mock(return_value=mock_result)

    result = scylladb_instance.get(vector_id="nonexistent")

    assert result is None


# ---------------------------------------------------------------------------
# list_cols
# ---------------------------------------------------------------------------


def test_list_cols(scylladb_instance):
    mock_rows = [Mock(table_name="table_a"), Mock(table_name="table_b")]

    mock_prepared = Mock()
    scylladb_instance.session.prepare = Mock(return_value=mock_prepared)
    scylladb_instance.session.execute = Mock(return_value=mock_rows)

    cols = scylladb_instance.list_cols()

    assert isinstance(cols, list)
    assert cols == ["table_a", "table_b"]


# ---------------------------------------------------------------------------
# delete_col
# ---------------------------------------------------------------------------


def test_delete_col(scylladb_instance):
    scylladb_instance.delete_col()

    assert scylladb_instance.session.execute.called


# ---------------------------------------------------------------------------
# col_info
# ---------------------------------------------------------------------------


def test_col_info(scylladb_instance):
    mock_row = Mock()
    mock_row.count = 42

    mock_result = Mock()
    mock_result.one = Mock(return_value=mock_row)
    scylladb_instance.session.execute = Mock(return_value=mock_result)

    info = scylladb_instance.col_info()

    assert info["name"] == "test_collection"
    assert info["keyspace"] == "test_keyspace"
    assert info["count"] == 42
    assert info["vector_dims"] == 3


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def test_list_all(scylladb_instance):
    mock_rows = [
        Mock(id="id1", payload=json.dumps({"text": "a"})),
        Mock(id="id2", payload=json.dumps({"text": "b"})),
    ]
    scylladb_instance.session.execute = Mock(return_value=mock_rows)

    results = scylladb_instance.list(top_k=10)

    assert isinstance(results, list)
    assert len(results[0]) == 2


def test_list_with_filter(scylladb_instance):
    mock_rows = [
        Mock(id="id1", payload=json.dumps({"tag": "X"})),
        Mock(id="id2", payload=json.dumps({"tag": "Y"})),
    ]
    scylladb_instance.session.execute = Mock(return_value=mock_rows)

    results = scylladb_instance.list(filters={"tag": "X"}, top_k=10)

    assert len(results[0]) == 1
    assert results[0][0].payload["tag"] == "X"


# ---------------------------------------------------------------------------
# reset
# ---------------------------------------------------------------------------


def test_reset(scylladb_instance):
    scylladb_instance.reset()

    assert scylladb_instance.session.execute.called


# ---------------------------------------------------------------------------
# OutputData model
# ---------------------------------------------------------------------------


def test_output_data_model():
    data = OutputData(id="abc", score=0.05, payload={"key": "value"})
    assert data.id == "abc"
    assert data.score == 0.05
    assert data.payload == {"key": "value"}


def test_output_data_allows_none():
    data = OutputData(id=None, score=None, payload=None)
    assert data.id is None
    assert data.score is None
