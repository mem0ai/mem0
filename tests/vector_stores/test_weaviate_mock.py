import unittest
from unittest.mock import MagicMock, patch

from mem0.vector_stores.weaviate import OutputData, Weaviate


class TestWeaviateMock(unittest.TestCase):
    """
    Test the Weaviate class with mock objects.
    """

    def setUp(self):
        # Mock the weaviate client and its components
        self.client_mock = MagicMock()
        self.collection_mock = MagicMock()
        self.query_mock = MagicMock()
        self.fetch_objects_mock = MagicMock()
        
        # Set up the mock chain
        self.client_mock.collections.get.return_value = self.collection_mock
        self.collection_mock.query = self.query_mock
        self.query_mock.fetch_objects = self.fetch_objects_mock
        
        # Mock weaviate.connect_to_local to return our mock client
        with patch('mem0.vector_stores.weaviate.weaviate.connect_to_local', return_value=self.client_mock):
            self.weaviate_db = Weaviate(
                collection_name="test_collection",
                embedding_model_dims=1536,
                cluster_url="http://localhost:8080",
                auth_client_secret="test_api_key",
            )
        
        # Set the client directly to our mock
        self.weaviate_db.client = self.client_mock

    def test_list_without_sort(self):
        """Test list method without sort parameter (default behavior)"""
        # Create mock response objects
        mock_obj1 = MagicMock()
        mock_obj1.uuid = "id1"
        mock_obj1.properties = {"key1": "value1", "data": "test_data", "created_at": "2024-01-01"}
        
        mock_response = MagicMock()
        mock_response.objects = [mock_obj1]
        
        self.fetch_objects_mock.return_value = mock_response

        results = self.weaviate_db.list(limit=10)

        # Verify fetch_objects was called without sort parameter
        self.fetch_objects_mock.assert_called_once()
        call_args = self.fetch_objects_mock.call_args
        self.assertNotIn('sort', call_args[1])
        
        # Verify results format and content
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 1)  # list method returns [results]
        
        result_list = results[0]
        self.assertIsInstance(result_list, list)
        self.assertEqual(len(result_list), 1)
        
        result_item = result_list[0]
        self.assertIsInstance(result_item, OutputData)
        self.assertEqual(result_item.id, "id1")
        self.assertEqual(result_item.score, 1.0)
        self.assertIn("key1", result_item.payload)
        self.assertEqual(result_item.payload["key1"], "value1")
        self.assertIn("data", result_item.payload)
        self.assertEqual(result_item.payload["data"], "test_data")

    def test_list_with_sort(self):
        """Test list method with sort parameter"""
        # Create mock response objects
        mock_obj1 = MagicMock()
        mock_obj1.uuid = "id1"
        mock_obj1.properties = {"key1": "value1", "data": "test_data", "updated_at": "2024-01-01"}
        
        mock_response = MagicMock()
        mock_response.objects = [mock_obj1]
        
        self.fetch_objects_mock.return_value = mock_response

        # Test with sort parameter
        sort_config = {"property": "updated_at", "order": "desc"}
        results = self.weaviate_db.list(limit=10, sort=sort_config)

        # Verify fetch_objects was called with sort parameter
        self.fetch_objects_mock.assert_called_once()
        call_args = self.fetch_objects_mock.call_args
        self.assertIn('sort', call_args[1])
        
        # Verify the sort configuration was passed correctly
        sort_param = call_args[1]['sort']
        self.assertIsNotNone(sort_param)
        
        # Verify results format and content
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 1)
        
        result_list = results[0]
        self.assertIsInstance(result_list, list)
        self.assertEqual(len(result_list), 1)
        
        result_item = result_list[0]
        self.assertIsInstance(result_item, OutputData)
        self.assertEqual(result_item.id, "id1")
        self.assertEqual(result_item.score, 1.0)

    def test_list_with_invalid_sort(self):
        """Test list method with invalid sort parameter"""
        # Create mock response objects
        mock_obj1 = MagicMock()
        mock_obj1.uuid = "id1"
        mock_obj1.properties = {"key1": "value1", "data": "test_data"}
        
        mock_response = MagicMock()
        mock_response.objects = [mock_obj1]
        
        self.fetch_objects_mock.return_value = mock_response

        # Test with invalid sort parameter (not a dict)
        results = self.weaviate_db.list(limit=10, sort="invalid")

        # Verify fetch_objects was called without sort parameter
        self.fetch_objects_mock.assert_called_once()
        call_args = self.fetch_objects_mock.call_args
        self.assertNotIn('sort', call_args[1])
        
        # Verify results are still returned correctly
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 1)
        self.assertEqual(len(results[0]), 1)

    def test_list_with_empty_sort(self):
        """Test list method with empty sort parameter"""
        # Create mock response objects
        mock_obj1 = MagicMock()
        mock_obj1.uuid = "id1"
        mock_obj1.properties = {"key1": "value1", "data": "test_data"}
        
        mock_response = MagicMock()
        mock_response.objects = [mock_obj1]
        
        self.fetch_objects_mock.return_value = mock_response

        # Test with empty sort parameter
        results = self.weaviate_db.list(limit=10, sort={})

        # Verify fetch_objects was called without sort parameter
        self.fetch_objects_mock.assert_called_once()
        call_args = self.fetch_objects_mock.call_args
        self.assertNotIn('sort', call_args[1])
        
        # Verify results are still returned correctly
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 1)
        self.assertEqual(len(results[0]), 1)

    def test_list_with_filters(self):
        """Test list method with filters"""
        # Create mock response objects
        mock_obj1 = MagicMock()
        mock_obj1.uuid = "id1"
        mock_obj1.properties = {"key1": "value1", "data": "test_data", "user_id": "user123"}
        
        mock_response = MagicMock()
        mock_response.objects = [mock_obj1]
        
        self.fetch_objects_mock.return_value = mock_response

        # Test with filters
        filters = {"user_id": "user123"}
        results = self.weaviate_db.list(limit=10, filters=filters)

        # Verify fetch_objects was called with filters
        self.fetch_objects_mock.assert_called_once()
        call_args = self.fetch_objects_mock.call_args
        self.assertIn('filters', call_args[1])
        
        # Verify the filters were passed correctly
        filters_param = call_args[1]['filters']
        self.assertIsNotNone(filters_param)
        
        # Verify results format and content
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 1)
        
        result_list = results[0]
        self.assertIsInstance(result_list, list)
        self.assertEqual(len(result_list), 1)
        
        result_item = result_list[0]
        self.assertIsInstance(result_item, OutputData)
        self.assertEqual(result_item.id, "id1")
        self.assertIn("user_id", result_item.payload)
        self.assertEqual(result_item.payload["user_id"], "user123")

    def test_list_with_multiple_results(self):
        """Test list method with multiple results"""
        # Create mock response objects
        mock_obj1 = MagicMock()
        mock_obj1.uuid = "id1"
        mock_obj1.properties = {"key1": "value1", "data": "test_data1"}
        
        mock_obj2 = MagicMock()
        mock_obj2.uuid = "id2"
        mock_obj2.properties = {"key2": "value2", "data": "test_data2"}
        
        mock_response = MagicMock()
        mock_response.objects = [mock_obj1, mock_obj2]
        
        self.fetch_objects_mock.return_value = mock_response

        results = self.weaviate_db.list(limit=10)

        # Verify results format and content
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 1)
        
        result_list = results[0]
        self.assertIsInstance(result_list, list)
        self.assertEqual(len(result_list), 2)
        
        # Verify first result
        result_item1 = result_list[0]
        self.assertIsInstance(result_item1, OutputData)
        self.assertEqual(result_item1.id, "id1")
        self.assertEqual(result_item1.payload["data"], "test_data1")
        
        # Verify second result
        result_item2 = result_list[1]
        self.assertIsInstance(result_item2, OutputData)
        self.assertEqual(result_item2.id, "id2")
        self.assertEqual(result_item2.payload["data"], "test_data2")

    def test_list_with_empty_response(self):
        """Test list method with empty response"""
        # Create mock response with no objects
        mock_response = MagicMock()
        mock_response.objects = []
        
        self.fetch_objects_mock.return_value = mock_response

        results = self.weaviate_db.list(limit=10)

        # Verify results format and content
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 1)
        
        result_list = results[0]
        self.assertIsInstance(result_list, list)
        self.assertEqual(len(result_list), 0)  # Empty list


if __name__ == '__main__':
    unittest.main() 