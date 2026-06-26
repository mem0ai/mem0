import json
from unittest.mock import Mock, patch, call

import pytest

from mem0.vector_stores.cassandra import CassandraDB, OutputData, _validate_identifier


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
def cassandra_instance(mock_cluster, mock_session):
    with patch('mem0.vector_stores.cassandra.Cluster') as mock_cluster_class:
        mock_cluster_class.return_value = mock_cluster

        instance = CassandraDB(
            contact_points=['127.0.0.1'],
            port=9042,
            username='testuser',
            password='testpass',
            keyspace='test_keyspace',
            collection_name='test_collection',
            embedding_model_dims=128,
        )
        instance.session = mock_session
        # Reset mock call history from initialization
        mock_session.reset_mock()
        return instance


class TestValidateIdentifier:
    def test_valid_identifier(self):
        assert _validate_identifier("valid_name") == "valid_name"
        assert _validate_identifier("_underscore") == "_underscore"
        assert _validate_identifier("CamelCase123") == "CamelCase123"

    def test_invalid_identifier_starts_with_digit(self):
        with pytest.raises(ValueError):
            _validate_identifier("123invalid")

    def test_invalid_identifier_special_chars(self):
        with pytest.raises(ValueError):
            _validate_identifier("name-with-dashes")

    def test_invalid_identifier_spaces(self):
        with pytest.raises(ValueError):
            _validate_identifier("name with spaces")


class TestCassandraDBInit:
    def test_basic_init(self, mock_cluster, mock_session):
        with patch('mem0.vector_stores.cassandra.Cluster') as mock_cluster_class:
            mock_cluster_class.return_value = mock_cluster

            instance = CassandraDB(
                contact_points=['127.0.0.1'],
                port=9042,
                username='testuser',
                password='testpass',
                keyspace='test_keyspace',
                collection_name='test_collection',
                embedding_model_dims=128,
            )

            assert instance.contact_points == ['127.0.0.1']
            assert instance.port == 9042
            assert instance.username == 'testuser'
            assert instance.keyspace == 'test_keyspace'
            assert instance.collection_name == 'test_collection'
            assert instance.embedding_model_dims == 128

    def test_init_with_secure_connect_bundle(self, mock_cluster, mock_session):
        with patch('mem0.vector_stores.cassandra.Cluster') as mock_cluster_class:
            mock_cluster_class.return_value = mock_cluster

            instance = CassandraDB(
                contact_points=['127.0.0.1'],
                port=9042,
                username='testuser',
                password='testpass',
                keyspace='test_keyspace',
                collection_name='test_collection',
                embedding_model_dims=128,
                secure_connect_bundle='/path/to/bundle.zip'
            )

            assert instance.secure_connect_bundle == '/path/to/bundle.zip'
            mock_cluster_class.assert_called_once_with(
                cloud={'secure_connect_bundle': '/path/to/bundle.zip'},
                auth_provider=mock_cluster_class.call_args[1].get('auth_provider')
                if mock_cluster_class.call_args[1] else None,
                protocol_version=4
            )

    def test_init_without_auth(self, mock_cluster, mock_session):
        with patch('mem0.vector_stores.cassandra.Cluster') as mock_cluster_class:
            mock_cluster_class.return_value = mock_cluster

            instance = CassandraDB(
                contact_points=['192.168.1.1', '192.168.1.2'],
                port=9043,
                keyspace='my_keyspace',
                collection_name='my_table',
                embedding_model_dims=256,
            )

            assert instance.username is None
            assert instance.password is None

    def test_init_creates_keyspace_and_table(self, mock_cluster, mock_session):
        with patch('mem0.vector_stores.cassandra.Cluster') as mock_cluster_class:
            mock_cluster_class.return_value = mock_cluster

            CassandraDB(
                contact_points=['127.0.0.1'],
                port=9042,
                keyspace='test_ks',
                collection_name='test_tbl',
                embedding_model_dims=64,
            )

            # Verify keyspace creation, set_keyspace, table creation, and index creation
            assert mock_session.execute.call_count >= 3
            assert mock_session.set_keyspace.called

    def test_init_invalid_keyspace(self, mock_cluster, mock_session):
        with patch('mem0.vector_stores.cassandra.Cluster') as mock_cluster_class:
            mock_cluster_class.return_value = mock_cluster
            with pytest.raises(ValueError, match="Invalid keyspace"):
                CassandraDB(
                    contact_points=['127.0.0.1'],
                    keyspace='invalid-keyspace!',
                    collection_name='test',
                    embedding_model_dims=64,
                )


class TestCreateCol:
    def test_create_col_default(self, cassandra_instance):
        cassandra_instance.create_col(name="new_collection", vector_size=256)
        assert cassandra_instance.session.execute.called

    def test_create_col_with_distance(self, cassandra_instance):
        cassandra_instance.create_col(name="col_euc", vector_size=128, distance="euclidean")
        assert cassandra_instance.session.execute.called

    def test_create_col_dot_product(self, cassandra_instance):
        cassandra_instance.create_col(name="col_dot", vector_size=128, distance="dot_product")
        assert cassandra_instance.session.execute.called


class TestInsert:
    def test_insert_with_all_params(self, cassandra_instance):
        vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        payloads = [{"text": "test1"}, {"text": "test2"}]
        ids = ["id1", "id2"]

        mock_prepared = Mock()
        cassandra_instance.session.prepare = Mock(return_value=mock_prepared)

        cassandra_instance.insert(vectors=vectors, payloads=payloads, ids=ids)

        cassandra_instance.session.prepare.assert_called_once()
        assert cassandra_instance.session.execute.call_count == 2

    def test_insert_without_ids(self, cassandra_instance):
        vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        payloads = [{"text": "test1"}, {"text": "test2"}]

        mock_prepared = Mock()
        cassandra_instance.session.prepare = Mock(return_value=mock_prepared)

        cassandra_instance.insert(vectors=vectors, payloads=payloads)

        cassandra_instance.session.prepare.assert_called_once()
        assert cassandra_instance.session.execute.call_count == 2

    def test_insert_without_payloads(self, cassandra_instance):
        vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        ids = ["id1", "id2"]

        mock_prepared = Mock()
        cassandra_instance.session.prepare = Mock(return_value=mock_prepared)

        cassandra_instance.insert(vectors=vectors, ids=ids)

        cassandra_instance.session.prepare.assert_called_once()
        assert cassandra_instance.session.execute.call_count == 2
        # Verify empty payloads
        for c in cassandra_instance.session.execute.call_args_list:
            args = c[0]
            payload_json = args[1][2]
            assert json.loads(payload_json) == {}


class TestSearch:
    def test_search_basic(self, cassandra_instance):
        mock_row1 = Mock()
        mock_row1.id = 'id1'
        mock_row1.score = 0.95
        mock_row1.payload = json.dumps({"text": "result1"})

        mock_row2 = Mock()
        mock_row2.id = 'id2'
        mock_row2.score = 0.85
        mock_row2.payload = json.dumps({"text": "result2"})

        mock_prepared = Mock()
        cassandra_instance.session.prepare = Mock(return_value=mock_prepared)
        cassandra_instance.session.execute = Mock(return_value=[mock_row1, mock_row2])

        query_vector = [0.2, 0.3, 0.4]
        results = cassandra_instance.search(query="test", vectors=query_vector, top_k=5)

        assert isinstance(results, list)
        assert len(results) == 2
        assert results[0].id == 'id1'
        assert results[0].score == 0.95
        assert results[0].payload == {"text": "result1"}
        assert results[1].id == 'id2'
        assert results[1].score == 0.85

        # Verify ANN query was used
        cassandra_instance.session.prepare.assert_called_once()
        prepare_call_arg = cassandra_instance.session.prepare.call_args[0][0]
        assert "ORDER BY vector ANN OF" in prepare_call_arg
        assert "similarity_cosine" in prepare_call_arg

    def test_search_with_filters(self, cassandra_instance):
        mock_row1 = Mock()
        mock_row1.id = 'id1'
        mock_row1.score = 0.95
        mock_row1.payload = json.dumps({"text": "test1", "category": "A"})

        mock_row2 = Mock()
        mock_row2.id = 'id2'
        mock_row2.score = 0.85
        mock_row2.payload = json.dumps({"text": "test2", "category": "B"})

        mock_prepared = Mock()
        cassandra_instance.session.prepare = Mock(return_value=mock_prepared)
        cassandra_instance.session.execute = Mock(return_value=[mock_row1, mock_row2])

        query_vector = [0.2, 0.3, 0.4]
        results = cassandra_instance.search(
            query="test",
            vectors=query_vector,
            top_k=5,
            filters={"category": "A"}
        )

        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0].payload["category"] == "A"

    def test_search_empty_result(self, cassandra_instance):
        mock_prepared = Mock()
        cassandra_instance.session.prepare = Mock(return_value=mock_prepared)
        cassandra_instance.session.execute = Mock(return_value=[])

        results = cassandra_instance.search(query="test", vectors=[0.1, 0.2], top_k=5)
        assert results == []

    def test_search_with_none_score(self, cassandra_instance):
        mock_row = Mock()
        mock_row.id = 'id1'
        mock_row.score = None
        mock_row.payload = json.dumps({"text": "test"})

        mock_prepared = Mock()
        cassandra_instance.session.prepare = Mock(return_value=mock_prepared)
        cassandra_instance.session.execute = Mock(return_value=[mock_row])

        results = cassandra_instance.search(query="q", vectors=[0.1], top_k=1)
        assert results[0].score == 0.0

    def test_search_with_null_payload(self, cassandra_instance):
        mock_row = Mock()
        mock_row.id = 'id1'
        mock_row.score = 0.9
        mock_row.payload = None

        mock_prepared = Mock()
        cassandra_instance.session.prepare = Mock(return_value=mock_prepared)
        cassandra_instance.session.execute = Mock(return_value=[mock_row])

        results = cassandra_instance.search(query="q", vectors=[0.1], top_k=1)
        assert results[0].payload == {}


class TestDelete:
    def test_delete(self, cassandra_instance):
        mock_prepared = Mock()
        cassandra_instance.session.prepare = Mock(return_value=mock_prepared)

        cassandra_instance.delete(vector_id="test_id")

        cassandra_instance.session.prepare.assert_called_once()
        cassandra_instance.session.execute.assert_called_once()


class TestUpdate:
    def test_update_vector_only(self, cassandra_instance):
        mock_prepared = Mock()
        cassandra_instance.session.prepare = Mock(return_value=mock_prepared)

        cassandra_instance.update(vector_id="test_id", vector=[0.7, 0.8, 0.9])

        cassandra_instance.session.prepare.assert_called_once()
        cassandra_instance.session.execute.assert_called_once()

    def test_update_payload_only(self, cassandra_instance):
        mock_prepared = Mock()
        cassandra_instance.session.prepare = Mock(return_value=mock_prepared)

        cassandra_instance.update(vector_id="test_id", payload={"text": "updated"})

        cassandra_instance.session.prepare.assert_called_once()
        cassandra_instance.session.execute.assert_called_once()

    def test_update_both(self, cassandra_instance):
        mock_prepared = Mock()
        cassandra_instance.session.prepare = Mock(return_value=mock_prepared)

        cassandra_instance.update(
            vector_id="test_id",
            vector=[0.7, 0.8, 0.9],
            payload={"text": "updated"}
        )

        assert cassandra_instance.session.prepare.call_count == 2
        assert cassandra_instance.session.execute.call_count == 2


class TestGet:
    def test_get_existing(self, cassandra_instance):
        mock_row = Mock()
        mock_row.id = 'test_id'
        mock_row.vector = [0.1, 0.2, 0.3]
        mock_row.payload = json.dumps({"text": "test"})

        mock_result = Mock()
        mock_result.one = Mock(return_value=mock_row)

        mock_prepared = Mock()
        cassandra_instance.session.prepare = Mock(return_value=mock_prepared)
        cassandra_instance.session.execute = Mock(return_value=mock_result)

        result = cassandra_instance.get(vector_id="test_id")

        assert result is not None
        assert isinstance(result, OutputData)
        assert result.id == "test_id"
        assert result.payload == {"text": "test"}
        assert result.score is None

    def test_get_not_found(self, cassandra_instance):
        mock_result = Mock()
        mock_result.one = Mock(return_value=None)

        mock_prepared = Mock()
        cassandra_instance.session.prepare = Mock(return_value=mock_prepared)
        cassandra_instance.session.execute = Mock(return_value=mock_result)

        result = cassandra_instance.get(vector_id="nonexistent_id")
        assert result is None

    def test_get_with_null_payload(self, cassandra_instance):
        mock_row = Mock()
        mock_row.id = 'test_id'
        mock_row.vector = [0.1, 0.2, 0.3]
        mock_row.payload = None

        mock_result = Mock()
        mock_result.one = Mock(return_value=mock_row)

        mock_prepared = Mock()
        cassandra_instance.session.prepare = Mock(return_value=mock_prepared)
        cassandra_instance.session.execute = Mock(return_value=mock_result)

        result = cassandra_instance.get(vector_id="test_id")
        assert result.payload == {}


class TestListCols:
    def test_list_cols(self, cassandra_instance):
        mock_row1 = Mock()
        mock_row1.table_name = "collection1"
        mock_row2 = Mock()
        mock_row2.table_name = "collection2"

        mock_prepared = Mock()
        cassandra_instance.session.prepare = Mock(return_value=mock_prepared)
        cassandra_instance.session.execute = Mock(return_value=[mock_row1, mock_row2])

        collections = cassandra_instance.list_cols()

        assert isinstance(collections, list)
        assert len(collections) == 2
        assert "collection1" in collections
        assert "collection2" in collections

    def test_list_cols_empty(self, cassandra_instance):
        mock_prepared = Mock()
        cassandra_instance.session.prepare = Mock(return_value=mock_prepared)
        cassandra_instance.session.execute = Mock(return_value=[])

        collections = cassandra_instance.list_cols()
        assert collections == []


class TestDeleteCol:
    def test_delete_col(self, cassandra_instance):
        cassandra_instance.delete_col()
        assert cassandra_instance.session.execute.called


class TestColInfo:
    def test_col_info(self, cassandra_instance):
        mock_row = Mock()
        mock_row.count = 100

        mock_result = Mock()
        mock_result.one = Mock(return_value=mock_row)

        cassandra_instance.session.execute = Mock(return_value=mock_result)

        info = cassandra_instance.col_info()

        assert isinstance(info, dict)
        assert info['name'] == 'test_collection'
        assert info['keyspace'] == 'test_keyspace'
        assert info['count'] == 100
        assert info['vector_dims'] == 128


class TestList:
    def test_list_basic(self, cassandra_instance):
        mock_row = Mock()
        mock_row.id = 'id1'
        mock_row.vector = [0.1, 0.2, 0.3]
        mock_row.payload = json.dumps({"text": "test1"})

        cassandra_instance.session.execute = Mock(return_value=[mock_row])

        results = cassandra_instance.list(top_k=10)

        assert isinstance(results, list)
        assert len(results) == 1
        assert len(results[0]) == 1
        assert results[0][0].id == 'id1'

    def test_list_with_filters(self, cassandra_instance):
        mock_row1 = Mock()
        mock_row1.id = 'id1'
        mock_row1.vector = [0.1, 0.2, 0.3]
        mock_row1.payload = json.dumps({"text": "test1", "category": "A"})

        mock_row2 = Mock()
        mock_row2.id = 'id2'
        mock_row2.vector = [0.4, 0.5, 0.6]
        mock_row2.payload = json.dumps({"text": "test2", "category": "B"})

        cassandra_instance.session.execute = Mock(return_value=[mock_row1, mock_row2])

        results = cassandra_instance.list(filters={"category": "A"}, top_k=10)

        assert len(results[0]) == 1
        assert results[0][0].payload["category"] == "A"

    def test_list_empty(self, cassandra_instance):
        cassandra_instance.session.execute = Mock(return_value=[])
        results = cassandra_instance.list(top_k=10)
        assert results == [[]]


class TestReset:
    def test_reset(self, cassandra_instance):
        cassandra_instance.reset()
        assert cassandra_instance.session.execute.called


class TestOutputDataModel:
    def test_output_data_all_fields(self):
        data = OutputData(id="test_id", score=0.95, payload={"text": "test"})
        assert data.id == "test_id"
        assert data.score == 0.95
        assert data.payload == {"text": "test"}

    def test_output_data_optional_fields(self):
        data = OutputData(id=None, score=None, payload=None)
        assert data.id is None
        assert data.score is None
        assert data.payload is None


class TestConnectionSetup:
    def test_connection_with_auth(self, mock_cluster, mock_session):
        with patch('mem0.vector_stores.cassandra.Cluster') as mock_cluster_class:
            mock_cluster_class.return_value = mock_cluster
            with patch('mem0.vector_stores.cassandra.PlainTextAuthProvider') as mock_auth:
                mock_auth.return_value = Mock()

                CassandraDB(
                    contact_points=['127.0.0.1'],
                    username='user',
                    password='pass',
                    keyspace='ks',
                    collection_name='tbl',
                    embedding_model_dims=64,
                )

                mock_auth.assert_called_once_with(username='user', password='pass')

    def test_connection_without_auth(self, mock_cluster, mock_session):
        with patch('mem0.vector_stores.cassandra.Cluster') as mock_cluster_class:
            mock_cluster_class.return_value = mock_cluster

            instance = CassandraDB(
                contact_points=['127.0.0.1'],
                keyspace='ks',
                collection_name='tbl',
                embedding_model_dims=64,
            )

            call_kwargs = mock_cluster_class.call_args[1]
            assert 'auth_provider' not in call_kwargs

    def test_connection_failure(self, mock_cluster, mock_session):
        with patch('mem0.vector_stores.cassandra.Cluster') as mock_cluster_class:
            mock_cluster_class.return_value = mock_cluster
            mock_cluster.connect.side_effect = Exception("Connection refused")

            with pytest.raises(Exception, match="Connection refused"):
                CassandraDB(
                    contact_points=['127.0.0.1'],
                    keyspace='ks',
                    collection_name='tbl',
                    embedding_model_dims=64,
                )


class TestTableCreation:
    def test_table_uses_vector_type(self, mock_cluster, mock_session):
        with patch('mem0.vector_stores.cassandra.Cluster') as mock_cluster_class:
            mock_cluster_class.return_value = mock_cluster

            CassandraDB(
                contact_points=['127.0.0.1'],
                keyspace='ks',
                collection_name='tbl',
                embedding_model_dims=256,
            )

            # Check that VECTOR<FLOAT, 256> was used in table creation
            execute_calls = [str(c) for c in mock_session.execute.call_args_list]
            create_table_found = False
            sai_index_found = False
            for c in mock_session.execute.call_args_list:
                arg = str(c)
                if "VECTOR<FLOAT, 256>" in arg:
                    create_table_found = True
                if "StorageAttachedIndex" in arg:
                    sai_index_found = True

            assert create_table_found, "Table should use VECTOR<FLOAT, N> type"
            assert sai_index_found, "SAI index should be created on vector column"
