# import os
# import uuid
# import httpx
# import unittest
# from unittest.mock import MagicMock, patch

# import dotenv
# import weaviate
# from weaviate.classes.query import MetadataQuery, Filter
# from weaviate.exceptions import UnexpectedStatusCodeException

# from mem0.vector_stores.weaviate import Weaviate, OutputData


# class TestWeaviateDB(unittest.TestCase):
#     @classmethod
#     def setUpClass(cls):
#         dotenv.load_dotenv()

#         cls.original_env = {
#             'WEAVIATE_CLUSTER_URL': os.getenv('WEAVIATE_CLUSTER_URL', 'http://localhost:8080'),
#             'WEAVIATE_API_KEY': os.getenv('WEAVIATE_API_KEY', 'test_api_key'),
#         }

#         os.environ['WEAVIATE_CLUSTER_URL'] = 'http://localhost:8080'
#         os.environ['WEAVIATE_API_KEY'] = 'test_api_key'

#     def setUp(self):
#         self.client_mock = MagicMock(spec=weaviate.WeaviateClient)
#         self.client_mock.collections = MagicMock()
#         self.client_mock.collections.exists.return_value = False
#         self.client_mock.collections.create.return_value = None
#         self.client_mock.collections.delete.return_value = None

#         patcher = patch('mem0.vector_stores.weaviate.weaviate.connect_to_local', return_value=self.client_mock)
#         self.mock_weaviate = patcher.start()
#         self.addCleanup(patcher.stop)

#         self.weaviate_db = Weaviate(
#             collection_name="test_collection",
#             embedding_model_dims=1536,
#             cluster_url=os.getenv('WEAVIATE_CLUSTER_URL'),
#             auth_client_secret=os.getenv('WEAVIATE_API_KEY'),
#             additional_headers={"X-OpenAI-Api-Key": "test_key"},
#         )

#         self.client_mock.reset_mock()

#     @classmethod
#     def tearDownClass(cls):
#         for key, value in cls.original_env.items():
#             if value is not None:
#                 os.environ[key] = value
#             else:
#                 os.environ.pop(key, None)

#     def tearDown(self):
#         self.client_mock.reset_mock()

#     def test_create_col(self):
#         self.client_mock.collections.exists.return_value = False
#         self.weaviate_db.create_col(vector_size=1536)


#         self.client_mock.collections.create.assert_called_once()


#         self.client_mock.reset_mock()

#         self.client_mock.collections.exists.return_value = True
#         self.weaviate_db.create_col(vector_size=1536)

#         self.client_mock.collections.create.assert_not_called()

#     def test_insert(self):
#         self.client_mock.batch = MagicMock()

#         self.client_mock.batch.fixed_size.return_value.__enter__.return_value = MagicMock()

#         self.client_mock.collections.get.return_value.data.insert_many.return_value = {
#             "results": [{"id": "id1"}, {"id": "id2"}]
#         }

#         vectors = [[0.1] * 1536, [0.2] * 1536]
#         payloads = [{"key1": "value1"}, {"key2": "value2"}]
#         ids = [str(uuid.uuid4()), str(uuid.uuid4())]

#         results = self.weaviate_db.insert(vectors=vectors, payloads=payloads, ids=ids)

#     def test_get(self):
#         valid_uuid = str(uuid.uuid4())

#         mock_response = MagicMock()
#         mock_response.properties = {
#             "hash": "abc123",
#             "created_at": "2025-03-08T12:00:00Z",
#             "updated_at": "2025-03-08T13:00:00Z",
#             "user_id": "user_123",
#             "agent_id": "agent_456",
#             "run_id": "run_789",
#             "data": {"key": "value"},
#             "category": "test",
#         }
#         mock_response.uuid = valid_uuid

#         self.client_mock.collections.get.return_value.query.fetch_object_by_id.return_value = mock_response

#         result = self.weaviate_db.get(vector_id=valid_uuid)

#         assert result.id == valid_uuid

#         expected_payload = mock_response.properties.copy()
#         expected_payload["id"] = valid_uuid

#         assert result.payload == expected_payload


#     def test_get_not_found(self):
#         mock_response = httpx.Response(status_code=404, json={"error": "Not found"})

#         self.client_mock.collections.get.return_value.data.get_by_id.side_effect = UnexpectedStatusCodeException(
#             "Not found", mock_response
#         )


#     def test_search(self):
#         mock_objects = [
#             {
#                 "uuid": "id1",
#                 "properties": {"key1": "value1"},
#                 "metadata": {"distance": 0.2}
#             }
#         ]

#         mock_response = MagicMock()
#         mock_response.objects = []

#         for obj in mock_objects:
#             mock_obj = MagicMock()
#             mock_obj.uuid = obj["uuid"]
#             mock_obj.properties = obj["properties"]
#             mock_obj.metadata = MagicMock()
#             mock_obj.metadata.distance = obj["metadata"]["distance"]
#             mock_response.objects.append(mock_obj)

#         mock_hybrid = MagicMock()
#         self.client_mock.collections.get.return_value.query.hybrid = mock_hybrid
#         mock_hybrid.return_value = mock_response

#         vectors = [[0.1] * 1536]
#         results = self.weaviate_db.search(query="", vectors=vectors, limit=5)

#         mock_hybrid.assert_called_once()

#         self.assertEqual(len(results), 1)
#         self.assertEqual(results[0].id, "id1")
#         self.assertEqual(results[0].score, 0.8)

#     def test_delete(self):
#         self.weaviate_db.delete(vector_id="id1")

#         self.client_mock.collections.get.return_value.data.delete_by_id.assert_called_once_with("id1")

#     def test_list(self):
#         mock_objects = []

#         mock_obj1 = MagicMock()
#         mock_obj1.uuid = "id1"
#         mock_obj1.properties = {"key1": "value1"}
#         mock_objects.append(mock_obj1)

#         mock_obj2 = MagicMock()
#         mock_obj2.uuid = "id2"
#         mock_obj2.properties = {"key2": "value2"}
#         mock_objects.append(mock_obj2)

#         mock_response = MagicMock()
#         mock_response.objects = mock_objects

#         mock_fetch = MagicMock()
#         self.client_mock.collections.get.return_value.query.fetch_objects = mock_fetch
#         mock_fetch.return_value = mock_response

#         results = self.weaviate_db.list(limit=10)

#         mock_fetch.assert_called_once()

#         # Verify results
#         self.assertEqual(len(results), 1)
#         self.assertEqual(len(results[0]), 2)
#         self.assertEqual(results[0][0].id, "id1")
#         self.assertEqual(results[0][0].payload["key1"], "value1")
#         self.assertEqual(results[0][1].id, "id2")
#         self.assertEqual(results[0][1].payload["key2"], "value2")


#     def test_list_cols(self):
#         mock_collection1 = MagicMock()
#         mock_collection1.name = "collection1"

#         mock_collection2 = MagicMock()
#         mock_collection2.name = "collection2"
#         self.client_mock.collections.list_all.return_value = [mock_collection1, mock_collection2]

#         result = self.weaviate_db.list_cols()
#         expected = {"collections": [{"name": "collection1"}, {"name": "collection2"}]}

#         assert result == expected

#         self.client_mock.collections.list_all.assert_called_once()


#     def test_delete_col(self):
#         self.weaviate_db.delete_col()

#         self.client_mock.collections.delete.assert_called_once_with("test_collection")


# if __name__ == '__main__':
#     unittest.main()
