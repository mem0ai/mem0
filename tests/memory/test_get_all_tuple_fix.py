"""
Test for fix of issue #3419: 'mem0.get_all() failed: tuple object has no attribute id'

This test verifies that the get_all method correctly handles tuple results from vector stores,
specifically when the vector store returns a tuple containing (points, next_page_offset).
"""

import unittest
from unittest.mock import MagicMock, patch

from mem0.memory.main import Memory


class TestGetAllTupleFix(unittest.TestCase):
    """Test the fix for the get_all tuple issue"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock the Memory class to avoid requiring actual API keys
        with patch.object(Memory, '__init__', return_value=None):
            self.memory = Memory()
            self.memory.vector_store = MagicMock()
            self.memory.embedding_model = MagicMock()
            self.memory.graph = MagicMock()
            self.memory.enable_graph = False
            self.memory.api_version = "v1.1"
            self.memory.collection_name = "test_collection"
    
    @patch('mem0.memory.main.capture_event')
    def test_get_all_with_tuple_result(self, mock_capture_event):
        """Test that get_all handles tuple results correctly"""
        # Mock a tuple result that would cause the original error
        mock_memory_item = MagicMock()
        mock_memory_item.id = "test_id_1"
        mock_memory_item.payload = {
            "data": "Test memory content",
            "hash": "test_hash",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "user_id": "test_user"
        }
        
        # Mock the vector store to return a tuple (points, next_page_offset)
        tuple_result = ([mock_memory_item], None)
        self.memory.vector_store.list.return_value = tuple_result
        
        # This should not raise an AttributeError
        result = self.memory.get_all(user_id="test_user")
        
        # Verify the result structure
        self.assertIn("results", result)
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["results"][0]["id"], "test_id_1")
        self.assertEqual(result["results"][0]["memory"], "Test memory content")
    
    @patch('mem0.memory.main.capture_event')
    def test_get_all_with_dict_result(self, mock_capture_event):
        """Test that get_all handles dict results correctly"""
        # Mock a dict result - this represents a memory item where the payload is embedded
        dict_result = {
            "id": "test_id_2",
            "data": "Test memory content 2",
            "hash": "test_hash_2",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "user_id": "test_user"
        }
        
        # Mock the vector store to return a list of dicts
        self.memory.vector_store.list.return_value = [dict_result]
        
        # This should not raise an AttributeError
        result = self.memory.get_all(user_id="test_user")
        
        # Verify the result structure
        self.assertIn("results", result)
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["results"][0]["id"], "test_id_2")
        self.assertEqual(result["results"][0]["memory"], "Test memory content 2")
    
    @patch('mem0.memory.main.capture_event')
    def test_get_all_with_single_dict_result(self, mock_capture_event):
        """Test that get_all handles a single dict result correctly"""
        # Mock a single dict result (not wrapped in a list)
        dict_result = {
            "id": "test_id_3",
            "data": "Test memory content 3",
            "hash": "test_hash_3",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "user_id": "test_user"
        }
        
        # Mock the vector store to return a single dict
        self.memory.vector_store.list.return_value = dict_result
        
        # This should not raise an AttributeError
        result = self.memory.get_all(user_id="test_user")
        
        # Verify the result structure
        self.assertIn("results", result)
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["results"][0]["id"], "test_id_3")
        self.assertEqual(result["results"][0]["memory"], "Test memory content 3")


if __name__ == "__main__":
    unittest.main()
