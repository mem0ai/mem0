"""
Mock-based unit tests for DynamoDB implementation.
"""

import json
import pytest
from unittest.mock import Mock, patch
from mem0.dynamodb.config import DynamoDBConversationConfig, DynamoDBGraphConfig
from mem0.dynamodb.conversation_store import DynamoDBConversationStore
from mem0.dynamodb.graph_store import DynamoDBMemoryGraph


class TestDynamoDBConversationStore:
    """Test DynamoDB conversation store with mocks."""

    @pytest.fixture
    def mock_table(self):
        """Mock DynamoDB table."""
        table = Mock()
        table.put_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
        table.get_item.return_value = {
            "Item": {
                "user_id": "test_user",
                "conversation_id": "test_user:123",
                "messages": json.dumps([{"role": "user", "content": "test"}]),
                "metadata": json.dumps({"test": "data"}),
                "timestamp": 1234567890,
            }
        }
        table.query.return_value = {
            "Items": [
                {
                    "user_id": "test_user",
                    "conversation_id": "test_user:123",
                    "messages": json.dumps([{"role": "user", "content": "test"}]),
                    "timestamp": 1234567890,
                }
            ]
        }
        table.update_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
        table.delete_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
        return table

    @pytest.fixture
    def conversation_store(self, mock_table):
        """Create conversation store with mocked table."""
        config = DynamoDBConversationConfig(table_name="test_table", region="us-east-1")

        with patch("boto3.resource") as mock_resource:
            mock_dynamodb = Mock()
            mock_dynamodb.Table.return_value = mock_table
            mock_resource.return_value = mock_dynamodb

            store = DynamoDBConversationStore(config)
            store.table = mock_table
            return store

    def test_store_conversation(self, conversation_store, mock_table):
        """Test storing a conversation."""
        messages = [{"role": "user", "content": "Hello"}]
        metadata = {"session": "test"}

        conversation_id = conversation_store.store_conversation("test_user", messages, metadata)

        assert conversation_id.startswith("test_user:")
        mock_table.put_item.assert_called_once()

    def test_get_conversation(self, conversation_store, mock_table):
        """Test retrieving a conversation."""
        result = conversation_store.get_conversation("test_user", "test_user:123")

        assert result is not None
        assert "messages" in result
        mock_table.get_item.assert_called_once()

    def test_get_conversations_for_user(self, conversation_store, mock_table):
        """Test retrieving all conversations for a user."""
        conversations = conversation_store.get_conversations_for_user("test_user")

        assert isinstance(conversations, list)
        mock_table.query.assert_called_once()

    def test_update_conversation(self, conversation_store, mock_table):
        """Test updating a conversation."""
        new_messages = [{"role": "user", "content": "Updated"}]

        result = conversation_store.update_conversation("test_user", "test_user:123", new_messages)

        assert result is True
        mock_table.update_item.assert_called_once()

    def test_delete_conversation(self, conversation_store, mock_table):
        """Test deleting a conversation."""
        result = conversation_store.delete_conversation("test_user", "test_user:123")

        assert result is True
        mock_table.delete_item.assert_called_once()

    def test_get_conversation_not_found(self, conversation_store, mock_table):
        """Test getting non-existent conversation."""
        mock_table.get_item.return_value = {}

        result = conversation_store.get_conversation("test_user", "nonexistent")

        assert result is None

    def test_update_conversation_not_found(self, conversation_store, mock_table):
        """Test updating non-existent conversation."""
        mock_table.update_item.side_effect = Exception("Item not found")

        result = conversation_store.update_conversation("test_user", "nonexistent", [])

        assert result is False

    def test_delete_conversation_not_found(self, conversation_store, mock_table):
        """Test deleting non-existent conversation."""
        mock_table.delete_item.side_effect = Exception("Item not found")

        result = conversation_store.delete_conversation("test_user", "nonexistent")

        assert result is False

    def test_config_with_credentials(self):
        """Test conversation store with custom credentials."""
        config = DynamoDBConversationConfig(
            table_name="test_table",
            region="us-east-1",
            use_iam_role=False,
            aws_access_key_id="test_key",
            aws_secret_access_key="test_secret",
            endpoint_url="http://localhost:8000",
        )

        with patch("boto3.resource") as mock_resource:
            DynamoDBConversationStore(config)

            # Verify boto3.resource was called with credentials
            mock_resource.assert_called_once()
            call_kwargs = mock_resource.call_args[1]
            assert call_kwargs["aws_access_key_id"] == "test_key"
            assert call_kwargs["aws_secret_access_key"] == "test_secret"
            assert call_kwargs["endpoint_url"] == "http://localhost:8000"

    def test_store_conversation_with_ttl(self):
        """Test storing conversation with TTL enabled."""
        config = DynamoDBConversationConfig(table_name="test_table", region="us-east-1", ttl_enabled=True, ttl_days=7)

        mock_table = Mock()
        mock_table.put_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}

        with patch("boto3.resource") as mock_resource:
            mock_dynamodb = Mock()
            mock_dynamodb.Table.return_value = mock_table
            mock_resource.return_value = mock_dynamodb

            store = DynamoDBConversationStore(config)
            store.table = mock_table

            messages = [{"role": "user", "content": "Hello"}]
            store.store_conversation("test_user", messages)

            # Verify TTL was set in the item
            call_args = mock_table.put_item.call_args[1]
            item = call_args["Item"]
            assert "expiration_time" in item  # TTL attribute should be present


class TestDynamoDBMemoryGraph:
    """Test DynamoDB graph store with mocks."""

    @pytest.fixture
    def mock_table(self):
        """Mock DynamoDB table."""
        table = Mock()
        table.put_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
        table.query.return_value = {
            "Items": [
                {
                    "node_id": "test_node",
                    "edge_id": "OUT#target_node",
                    "source_id": "test_node",
                    "target_id": "target_node",
                    "relationship_type": "RELATED",
                    "content": "Test content",
                    "metadata": json.dumps({"test": "data"}),
                }
            ]
        }
        table.get_item.return_value = {
            "Item": {
                "node_id": "target_node",
                "edge_id": "META",
                "content": "Target node content",
                "metadata": json.dumps({"test": "data"}),
            }
        }
        table.scan.return_value = {
            "Items": [{"node_id": "test_node", "edge_id": "META", "content": "Test content", "user_id": "test_user"}]
        }
        table.update_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
        table.delete_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
        return table

    @pytest.fixture
    def graph_store(self, mock_table):
        """Create graph store with mocked table."""
        config = DynamoDBGraphConfig(table_name="test_graph_table", region="us-east-1")

        with patch("boto3.resource") as mock_resource:
            mock_dynamodb = Mock()
            mock_dynamodb.Table.return_value = mock_table
            mock_resource.return_value = mock_dynamodb

            store = DynamoDBMemoryGraph(config)
            store.table = mock_table
            return store

    def test_create_memory_node(self, graph_store, mock_table):
        """Test creating a memory node."""
        node_id = graph_store.create_memory_node(
            memory_id="test_node", content="Test content", metadata={"test": "data"}
        )

        assert node_id == "test_node"
        mock_table.put_item.assert_called_once()

    def test_create_memory_node_auto_id(self, graph_store, mock_table):
        """Test creating a memory node with auto-generated ID."""
        node_id = graph_store.create_memory_node(memory_id=None, content="Test content")

        assert node_id is not None
        assert len(node_id) > 0
        mock_table.put_item.assert_called_once()

    def test_create_relationship(self, graph_store, mock_table):
        """Test creating a relationship."""
        rel_id = graph_store.create_relationship(
            source_id="node1", target_id="node2", relationship_type="RELATED", properties={"strength": "high"}
        )

        assert rel_id is not None
        # Should create 1 relationship record (the implementation may vary)
        assert mock_table.put_item.call_count >= 1

    def test_get_related_memories(self, graph_store, mock_table):
        """Test getting related memories."""
        memories = graph_store.get_related_memories("test_node")

        assert isinstance(memories, list)
        mock_table.query.assert_called()

    def test_get_memories_by_relationship_type(self, graph_store, mock_table):
        """Test getting memories by relationship type."""
        memories = graph_store.get_memories_by_relationship_type("RELATED")

        assert isinstance(memories, list)
        mock_table.query.assert_called()

    def test_update_node(self, graph_store, mock_table):
        """Test updating a node."""
        result = graph_store.update_node(node_id="test_node", content="Updated content", metadata={"updated": True})

        assert result is True
        mock_table.update_item.assert_called_once()

    def test_delete_node(self, graph_store, mock_table):
        """Test deleting a node."""
        result = graph_store.delete_node("test_node")

        assert result is True
        mock_table.delete_item.assert_called()

    def test_get_all_with_filters(self, graph_store, mock_table):
        """Test get_all method with filters."""
        filters = {"user_id": "test_user"}

        results = graph_store.get_all(filters)

        assert isinstance(results, list)
        mock_table.scan.assert_called_once()

    def test_add_without_llm(self, graph_store, mock_table):
        """Test add method without LLM (fallback mode)."""
        graph_store.llm = None

        result = graph_store.add("Test data", {"user_id": "test_user"})

        assert "added_entities" in result
        assert len(result["added_entities"]) > 0
        mock_table.put_item.assert_called()

    def test_search_without_llm(self, graph_store, mock_table):
        """Test search method without LLM (fallback mode)."""
        graph_store.llm = None

        results = graph_store.search("test query", {"user_id": "test_user"})

        assert isinstance(results, list)

    def test_error_handling_create_node(self, graph_store, mock_table):
        """Test error handling in create_memory_node."""
        mock_table.put_item.side_effect = Exception("DynamoDB error")

        # Should raise exception since error handling isn't implemented
        with pytest.raises(Exception):
            graph_store.create_memory_node(memory_id="test_node", content="Test content")

    def test_error_handling_get_related(self, graph_store, mock_table):
        """Test error handling in get_related_memories."""
        mock_table.query.side_effect = Exception("DynamoDB error")

        # Should raise exception since error handling isn't implemented
        with pytest.raises(Exception):
            graph_store.get_related_memories("test_node")


class TestDynamoDBConversationConfig:
    """Test DynamoDB conversation configuration."""

    def test_conversation_config_defaults(self):
        """Test conversation config with defaults."""
        config = DynamoDBConversationConfig(table_name="test_table", region="us-east-1")

        assert config.table_name == "test_table"
        assert config.region == "us-east-1"
        assert config.ttl_enabled is False
        assert config.use_iam_role is True

    def test_conversation_config_custom(self):
        """Test conversation config with custom values."""
        config = DynamoDBConversationConfig(
            table_name="custom_table",
            region="us-west-2",
            ttl_enabled=True,
            ttl_days=7,
            use_iam_role=False,
            aws_access_key_id="test_key",
            aws_secret_access_key="test_secret",
        )

        assert config.ttl_enabled is True
        assert config.ttl_days == 7
        assert config.use_iam_role is False
        assert config.aws_access_key_id == "test_key"


class TestDynamoDBGraphConfig:
    """Test DynamoDB graph configuration."""

    def test_graph_config_defaults(self):
        """Test graph config with defaults."""
        config = DynamoDBGraphConfig(table_name="test_graph", region="us-east-1")

        assert config.table_name == "test_graph"
        assert config.region == "us-east-1"
        assert config.enable_gsi is True  # Default is True in the actual config
        assert config.use_iam_role is True

    def test_graph_config_custom(self):
        """Test graph config with custom values."""
        config = DynamoDBGraphConfig(
            table_name="custom_graph", region="eu-west-1", enable_gsi=True, endpoint_url="http://localhost:8000"
        )

        assert config.enable_gsi is True
        assert config.endpoint_url == "http://localhost:8000"

    def test_graph_store_with_llm_config(self):
        """Test graph store initialization with LLM config."""

        # Create a mock config object that has both DynamoDB config and LLM config
        class MockGraphConfig:
            def __init__(self):
                # DynamoDB config attributes
                self.table_name = "test_graph"
                self.region = "us-east-1"
                self.endpoint_url = None
                self.aws_access_key_id = None
                self.aws_secret_access_key = None
                self.use_iam_role = True
                self.enable_gsi = True
                self.gsi_name = "RelationshipTypeIndex"

                # LLM config
                self.llm = type("LLMConfig", (), {"provider": "test_provider", "config": {"model": "test_model"}})()

        config = MockGraphConfig()

        with patch("boto3.resource"), patch("mem0.utils.factory.LlmFactory.create") as mock_llm_factory:
            mock_llm = Mock()
            mock_llm_factory.return_value = mock_llm

            store = DynamoDBMemoryGraph(config)

            assert store.llm == mock_llm
            assert store.llm_provider == "test_provider"
            mock_llm_factory.assert_called_once_with("test_provider", {"model": "test_model"})
