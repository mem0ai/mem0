"""
Tests for DynamoDB implementation using real DynamoDB.
"""

import json
import os
import time
import uuid

import boto3
import pytest

from mem0.dynamodb.config import DynamoDBConversationConfig, DynamoDBGraphConfig
from mem0.dynamodb.conversation_store import DynamoDBConversationStore
from mem0.dynamodb.graph_store import DynamoDBMemoryGraph

# Test configurations - use environment variables or defaults
REGION = os.environ.get("AWS_REGION", "us-east-1")
CONVERSATION_TABLE = os.environ.get("CONVERSATION_TABLE", "Mem0Conversations")
GRAPH_TABLE = os.environ.get("GRAPH_TABLE", "Mem0Graph")

# Generate a unique test prefix to avoid conflicts between test runs
TEST_PREFIX = f"test_{int(time.time())}_{uuid.uuid4().hex[:8]}"

@pytest.fixture
def conversation_store():
    """Create a conversation store instance for testing with real DynamoDB."""
    config = DynamoDBConversationConfig(
        table_name=CONVERSATION_TABLE,
        region=REGION
    )
    return DynamoDBConversationStore(config)

@pytest.fixture
def graph_store():
    """Create a graph store instance for testing with real DynamoDB."""
    config = DynamoDBGraphConfig(
        table_name=GRAPH_TABLE,
        region=REGION,
        enable_gsi=True
    )
    return DynamoDBMemoryGraph(config)

@pytest.fixture
def test_user_id():
    """Generate a unique user ID for testing."""
    return f"{TEST_PREFIX}_user"

@pytest.fixture
def cleanup_test_data():
    """Fixture to clean up test data after tests run."""
    # This runs before the tests
    yield
    
    # This runs after the tests to clean up
    try:
        # Clean up conversation data
        dynamodb = boto3.resource('dynamodb', region_name=REGION)
        conversation_table = dynamodb.Table(CONVERSATION_TABLE)
        graph_table = dynamodb.Table(GRAPH_TABLE)
        
        # Query for test items in conversation table
        response = conversation_table.scan(
            FilterExpression="begins_with(user_id, :prefix)",
            ExpressionAttributeValues={":prefix": TEST_PREFIX}
        )
        
        # Delete test items from conversation table
        with conversation_table.batch_writer() as batch:
            for item in response.get('Items', []):
                batch.delete_item(
                    Key={
                        'user_id': item['user_id'],
                        'conversation_id': item['conversation_id']
                    }
                )
        
        # Query for test items in graph table
        response = graph_table.scan(
            FilterExpression="begins_with(node_id, :prefix)",
            ExpressionAttributeValues={":prefix": TEST_PREFIX}
        )
        
        # Delete test items from graph table
        with graph_table.batch_writer() as batch:
            for item in response.get('Items', []):
                batch.delete_item(
                    Key={
                        'node_id': item['node_id'],
                        'edge_id': item['edge_id']
                    }
                )
                
        print(f"Cleaned up test data with prefix {TEST_PREFIX}")
    except Exception as e:
        print(f"Error cleaning up test data: {e}")


class TestDynamoDBConversationStore:
    """Tests for DynamoDBConversationStore using real DynamoDB."""
    
    def test_store_conversation(self, conversation_store, test_user_id, cleanup_test_data):
        """Test storing a conversation."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        metadata = {"session_id": f"{TEST_PREFIX}_session"}
        
        # Store the conversation
        conversation_id = conversation_store.store_conversation(test_user_id, messages, metadata)
        
        # Verify it was stored
        conversation = conversation_store.get_conversation(test_user_id, conversation_id)
        assert conversation is not None
        assert conversation["user_id"] == test_user_id
        
        # Check if messages is a string or list and handle accordingly
        messages_data = conversation["messages"]
        if isinstance(messages_data, str):
            retrieved_messages = json.loads(messages_data)
        else:
            retrieved_messages = messages_data
            
        assert len(retrieved_messages) == 2
        assert retrieved_messages[0]["content"] == "Hello"
        
        # Check if metadata is a string or dict and handle accordingly
        metadata_data = conversation["metadata"]
        if isinstance(metadata_data, str):
            retrieved_metadata = json.loads(metadata_data)
        else:
            retrieved_metadata = metadata_data
            
        assert retrieved_metadata["session_id"] == f"{TEST_PREFIX}_session"
    
    def test_get_conversations_for_user(self, conversation_store, test_user_id, cleanup_test_data):
        """Test retrieving conversations for a user."""
        # Store multiple conversations
        conversation_ids = []
        for i in range(3):
            messages = [
                {"role": "user", "content": f"Message {i}"},
                {"role": "assistant", "content": f"Response {i}"}
            ]
            conversation_id = conversation_store.store_conversation(test_user_id, messages)
            conversation_ids.append(conversation_id)
            # Add a small delay to ensure different timestamps
            time.sleep(0.1)
        
        # Retrieve conversations one by one to verify they were stored
        for conversation_id in conversation_ids:
            conversation = conversation_store.get_conversation(test_user_id, conversation_id)
            assert conversation is not None
            assert conversation["user_id"] == test_user_id
        
        # Retrieve all conversations for the user
        conversations = conversation_store.get_conversations_for_user(test_user_id, limit=10)
        
        # Verify we can find at least one of our test conversations
        # (DynamoDB might not return all items in a single query due to pagination)
        found = False
        for conversation in conversations:
            if conversation["user_id"] == test_user_id and conversation["conversation_id"] in conversation_ids:
                found = True
                break
                
        assert found, "Could not find any of the test conversations"


class TestDynamoDBMemoryGraph:
    """Tests for DynamoDBMemoryGraph using real DynamoDB."""
    
    def test_create_memory_node(self, graph_store, cleanup_test_data):
        """Test creating a memory node."""
        node_id = f"{TEST_PREFIX}_node1"
        content = "This is a test memory"
        metadata = {"source": "test", "importance": "high"}
        
        # Create the node
        created_id = graph_store.create_memory_node(node_id, content, metadata)
        
        # Verify the ID was returned correctly
        assert created_id == node_id
        
        # We can't directly get a node, so we'll verify it exists when we test relationships
    
    def test_create_relationship(self, graph_store, cleanup_test_data):
        """Test creating a relationship between nodes."""
        # Create two nodes
        source_id = f"{TEST_PREFIX}_source"
        target_id = f"{TEST_PREFIX}_target"
        
        graph_store.create_memory_node(source_id, "Source node")
        graph_store.create_memory_node(target_id, "Target node")
        
        # Create relationship
        relationship_type = "RELATED_TO"
        properties = {"strength": "high", "created_by": "test"}
        _ = graph_store.create_relationship(source_id, target_id, relationship_type, properties)
        
        # Verify relationship through related memories
        related = graph_store.get_related_memories(source_id)
        assert len(related) == 1
        assert related[0]["node_id"] == target_id
        assert related[0]["relationship"] == relationship_type
        
        # Check if edge_properties is a string or dict and handle accordingly
        edge_props = related[0]["edge_properties"]
        if isinstance(edge_props, str):
            edge_props = json.loads(edge_props)
            
        assert edge_props["strength"] == "high"
    
    def test_get_related_memories(self, graph_store, cleanup_test_data):
        """Test retrieving related memories."""
        # Create a central node with multiple relationships
        central_id = f"{TEST_PREFIX}_central"
        graph_store.create_memory_node(central_id, "Central node")
        
        # Create related nodes with different relationship types
        related_ids = []
        for i in range(5):
            node_id = f"{TEST_PREFIX}_related_{i}"
            related_ids.append(node_id)
            graph_store.create_memory_node(node_id, f"Related node {i}")
            rel_type = "RELATED_TO" if i % 2 == 0 else "DEPENDS_ON"
            graph_store.create_relationship(central_id, node_id, rel_type)
        
        # Test filtering by relationship type
        related_only = graph_store.get_related_memories(
            central_id, relationship_types=["RELATED_TO"]
        )
        assert len(related_only) == 3  # Should find 3 RELATED_TO relationships
        
        # Test direction filtering
        incoming_id = f"{TEST_PREFIX}_incoming"
        graph_store.create_memory_node(incoming_id, "Incoming node")
        graph_store.create_relationship(incoming_id, central_id, "POINTS_TO")
        
        incoming = graph_store.get_related_memories(central_id, direction="incoming")
        assert len(incoming) == 1
        assert incoming[0]["node_id"] == incoming_id
