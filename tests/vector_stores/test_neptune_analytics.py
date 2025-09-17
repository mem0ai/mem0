import logging
import os
import sys

import pytest
from dotenv import load_dotenv

from mem0.utils.factory import VectorStoreFactory

load_dotenv()

# Configure logging
logging.getLogger("mem0.vector.neptune.main").setLevel(logging.INFO)
logging.getLogger("mem0.vector.neptune.base").setLevel(logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

logging.basicConfig(
    format="%(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)

# Test constants
EMBEDDING_MODEL_DIMS = 1024
VECTOR_1 = [-0.1] * EMBEDDING_MODEL_DIMS
VECTOR_2 = [-0.2] * EMBEDDING_MODEL_DIMS
VECTOR_3 = [-0.3] * EMBEDDING_MODEL_DIMS

SAMPLE_PAYLOADS = [
    {"test_text": "text_value", "another_field": "field_2_value"},
    {"test_text": "text_value_BBBB"},
    {"test_text": "text_value_CCCC"}
]


@pytest.mark.skipif(not os.getenv("RUN_TEST_NEPTUNE_ANALYTICS"), reason="Only run with RUN_TEST_NEPTUNE_ANALYTICS is true")
class TestNeptuneAnalyticsOperations:
    """Test basic CRUD operations."""

    @pytest.fixture
    def na_instance(self):
        """Create Neptune Analytics vector store instance for testing."""
        config = {
            "endpoint": f"neptune-graph://{os.getenv('GRAPH_ID')}",
            "collection_name": "test",
        }
        return VectorStoreFactory.create("neptune", config)


    def test_insert_and_list(self, na_instance):
        """Test vector insertion and listing."""
        na_instance.reset()
        na_instance.insert(
            vectors=[VECTOR_1, VECTOR_2, VECTOR_3],
            ids=["A", "B", "C"],
            payloads=SAMPLE_PAYLOADS
        )
        
        list_result = na_instance.list()[0]
        assert len(list_result) == 3
        assert "label" not in list_result[0].payload


    def test_get(self, na_instance):
        """Test retrieving a specific vector."""
        na_instance.reset()
        na_instance.insert(
            vectors=[VECTOR_1],
            ids=["A"],
            payloads=[SAMPLE_PAYLOADS[0]]
        )
        
        vector_a = na_instance.get("A")
        assert vector_a.id == "A"
        assert vector_a.score is None
        assert vector_a.payload["test_text"] == "text_value"
        assert vector_a.payload["another_field"] == "field_2_value"
        assert "label" not in vector_a.payload


    def test_update(self, na_instance):
        """Test updating vector payload."""
        na_instance.reset()
        na_instance.insert(
            vectors=[VECTOR_1],
            ids=["A"],
            payloads=[SAMPLE_PAYLOADS[0]]
        )
        
        na_instance.update(vector_id="A", payload={"updated_payload_str": "update_str"})
        vector_a = na_instance.get("A")
        
        assert vector_a.id == "A"
        assert vector_a.score is None
        assert vector_a.payload["updated_payload_str"] == "update_str"
        assert "label" not in vector_a.payload


    def test_delete(self, na_instance):
        """Test deleting a specific vector."""
        na_instance.reset()
        na_instance.insert(
            vectors=[VECTOR_1],
            ids=["A"],
            payloads=[SAMPLE_PAYLOADS[0]]
        )
        
        size_before = na_instance.list()[0]
        assert len(size_before) == 1
        
        na_instance.delete("A")
        size_after = na_instance.list()[0]
        assert len(size_after) == 0


    def test_search(self, na_instance):
        """Test vector similarity search."""
        na_instance.reset()
        na_instance.insert(
            vectors=[VECTOR_1, VECTOR_2, VECTOR_3],
            ids=["A", "B", "C"],
            payloads=SAMPLE_PAYLOADS
        )
        
        result = na_instance.search(query="", vectors=VECTOR_1, limit=1)
        assert len(result) == 1
        assert "label" not in result[0].payload


    def test_reset(self, na_instance):
        """Test resetting the collection."""
        na_instance.reset()
        na_instance.insert(
            vectors=[VECTOR_1, VECTOR_2, VECTOR_3],
            ids=["A", "B", "C"],
            payloads=SAMPLE_PAYLOADS
        )

        list_result = na_instance.list()[0]
        assert len(list_result) == 3

        na_instance.reset()
        list_result = na_instance.list()[0]
        assert len(list_result) == 0


    def test_delete_col(self, na_instance):
        """Test deleting the entire collection."""
        na_instance.reset()
        na_instance.insert(
            vectors=[VECTOR_1, VECTOR_2, VECTOR_3],
            ids=["A", "B", "C"],
            payloads=SAMPLE_PAYLOADS
        )

        list_result = na_instance.list()[0]
        assert len(list_result) == 3

        na_instance.delete_col()
        list_result = na_instance.list()[0]
        assert len(list_result) == 0


    def test_list_cols(self, na_instance):
        """Test listing collections."""
        na_instance.reset()
        na_instance.insert(
            vectors=[VECTOR_1, VECTOR_2, VECTOR_3],
            ids=["A", "B", "C"],
            payloads=SAMPLE_PAYLOADS
        )

        result = na_instance.list_cols()
        assert result == ["MEM0_VECTOR_test"]


    def test_invalid_endpoint_format(self):
        """Test that invalid endpoint format raises ValueError."""
        config = {
            "endpoint": f"xxx://{os.getenv('GRAPH_ID')}",
            "collection_name": "test",
        }

        with pytest.raises(ValueError):
            VectorStoreFactory.create("neptune", config)
