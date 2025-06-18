import unittest
from unittest.mock import MagicMock, patch
from mem0.vector_stores.tair_vector import TairVector, TairVectorExtendClient, MemoryResult


class TestTairVector(unittest.TestCase):

    def setUp(self):
        self.mock_client = MagicMock(spec=TairVectorExtendClient)
        patcher = patch('mem0.vector_stores.tair_vector.TairVectorExtendClient', return_value=self.mock_client)
        self.mock_tair = patcher.start()
        self.addCleanup(patcher.stop)

        self.tair_vector = TairVector(
            host='localhost',
            port=6379,
            db='mem0',
            username='test_user',
            password='test_password',
            collection_name='test_collection',
            embedding_model_dims=1536
        )
        self.mock_client.reset_mock()

    def test_create_col(self):
        self.mock_client.tvs_get_index.return_value = None
        self.mock_client.tvs_create_index.return_value = True

        self.tair_vector.create_col('test_collection', 1536)

        self.mock_client.tvs_get_index.assert_called_once_with('test_collection')
        self.mock_client.tvs_create_index.assert_called_once()
        create_args = self.mock_client.tvs_create_index.call_args[0]
        self.assertEqual(create_args[0], 'test_collection')
        self.assertEqual(create_args[1], 1536)

    def test_insert(self):
        vectors = [[0.1] * 1536, [0.2] * 1536]
        payloads = [
            {"hash": "hash1", "data": "data1", "created_at": "2023-01-01T00:00:00"},
            {"hash": "hash2", "data": "data2", "created_at": "2023-01-02T00:00:00"}
        ]
        ids = ["id1", "id2"]

        self.tair_vector.insert(vectors=vectors, payloads=payloads, ids=ids)

        self.assertEqual(self.mock_client.tvs_hset.call_count, 2)
        first_call = self.mock_client.tvs_hset.call_args_list[0]
        self.assertEqual(first_call[0][0], 'test_collection')
        self.assertEqual(first_call[0][1], 'id1')
        self.assertEqual(first_call[0][2], vectors[0])

    def test_search(self):
        mock_response = [
            [b'id1', b'0.8', b'TEXT', b'data1', b'metadata', b'{"key": "value"}'],
            [b'id2', b'0.7', b'TEXT', b'data2', b'metadata', b'{"key": "value"}']
        ]
        self.mock_client.tvs_knnsearchfield.return_value = mock_response

        results = self.tair_vector.search(query="test", vectors=[0.1] * 1536, limit=2)

        self.mock_client.tvs_knnsearchfield.assert_called_once()
        self.assertEqual(len(results), 2)
        self.assertIsInstance(results[0], MemoryResult)
        self.assertEqual(results[0].id, 'id1')
        self.assertEqual(results[0].score, 0.8)

    def test_delete(self):
        self.tair_vector.delete("id1")
        self.mock_client.tvs_del.assert_called_once_with('test_collection', 'id1')

    def test_update(self):
        vector = [0.3] * 1536
        payload = {
            "hash": "hash3",
            "data": "data3",
            "created_at": "2023-01-03T00:00:00",
            "updated_at": "2023-01-04T00:00:00"
        }

        self.tair_vector.update("id3", vector=vector, payload=payload)

        self.mock_client.tvs_hset.assert_called_once()
        call_args = self.mock_client.tvs_hset.call_args[0]
        self.assertEqual(call_args[0], 'test_collection')
        self.assertEqual(call_args[1], 'id3')
        self.assertEqual(call_args[2], vector)

    def test_get(self):
        mock_response = {
            "hash": "hash1",
            "TEXT": "data1",
            "created_at": "1672531200",
            "metadata": '{"key": "value"}'
        }
        self.mock_client.tvs_hgetall.return_value = mock_response

        result = self.tair_vector.get("id1")

        self.mock_client.tvs_hgetall.assert_called_once_with('test_collection', 'id1')
        self.assertIsInstance(result, MemoryResult)
        self.assertEqual(result.id, 'id1')
        self.assertEqual(result.payload['hash'], 'hash1')
        self.assertEqual(result.payload['data'], 'data1')

    def test_list_cols(self):
        self.mock_client.tvs_scan_index.return_value.iter.return_value = [b'col1', b'col2']

        result = self.tair_vector.list_cols()

        self.mock_client.tvs_scan_index.assert_called_once()
        self.assertEqual(result, ['col1', 'col2'])

    def test_delete_col(self):
        self.tair_vector.delete_col()
        self.mock_client.tvs_del_index.assert_called_once_with('test_collection')

    def test_col_info(self):
        self.tair_vector.col_info()
        self.mock_client.tvs_get_index.assert_called_once_with('test_collection')

    def test_list(self):
        mock_scan_response = [b'id1', b'id2']
        self.mock_client.tvs_scan.return_value = mock_scan_response

        mock_hgetall_responses = [
            {
                "hash": "hash1",
                "TEXT": "data1",
                "created_at": "1672531200",
                "metadata": '{"key": "value"}'
            },
            {
                "hash": "hash2",
                "TEXT": "data2",
                "created_at": "1672617600",
                "metadata": '{"key": "value"}'
            }
        ]
        self.mock_client.tvs_hgetall.side_effect = mock_hgetall_responses

        results = self.tair_vector.list(filters={"user_id": "user1"}, limit=2)

        self.mock_client.tvs_scan.assert_called_once()
        self.assertEqual(self.mock_client.tvs_hgetall.call_count, 2)
        self.assertEqual(len(results), 2)
        self.assertIsInstance(results[0], MemoryResult)
        self.assertEqual(results[0].id, 'id1')
        self.assertEqual(results[1].id, 'id2')

    def test_reset(self):
        self.mock_client.tvs_get_index.return_value = None
        self.tair_vector.reset()
        self.mock_client.tvs_del_index.assert_called_once_with('test_collection')
        self.mock_client.tvs_get_index.assert_called_once_with('test_collection')
        self.mock_client.tvs_create_index.assert_called_once()
        create_args = self.mock_client.tvs_create_index.call_args[0]
        self.assertEqual(create_args[0], 'test_collection')
        self.assertEqual(create_args[1], self.tair_vector.embedding_model_dims)


if __name__ == '__main__':
    unittest.main()
