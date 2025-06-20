# DynamoDB Implementation for Mem0

This implementation adds support for using Amazon DynamoDB as a storage backend for both conversation history and graph database functionality in mem0.

## Overview

The implementation consists of the following components:

1. **DynamoDB Conversation Store**: Replaces SQLite for storing conversation history
2. **DynamoDB Graph Store**: Implements graph database functionality using DynamoDB's flexible schema
3. **Configuration Classes**: Provides configuration options for DynamoDB
4. **Factory Integration**: Updates the factory system to support DynamoDB providers
5. **CloudFormation Template**: Provides infrastructure-as-code for creating DynamoDB tables
6. **Utility Functions**: Helpers for creating tables and generating CloudFormation templates
7. **Example Code**: Demonstrates how to use the DynamoDB implementation
8. **Tests**: Unit tests for the DynamoDB implementation

## Key Features

- **Scalable**: Leverages DynamoDB's virtually unlimited scaling capabilities
- **Managed**: No need to maintain database infrastructure
- **Durable**: Built on AWS's highly available and durable storage
- **Flexible**: Supports both conversation history and graph database use cases
- **Cost-effective**: Pay only for what you use with on-demand capacity

## Data Model

### Conversation Table

- **Primary Key**:
  - `user_id`: User identifier
  - `conversation_id`: Conversation identifier

- **Attributes**:
  - `messages`: JSON string of messages
  - `timestamp`: Creation timestamp
  - `metadata`: Optional JSON string of metadata
  - `expiration_time`: Optional TTL attribute

### Graph Table

- **Primary Key**:
  - `node_id`: Node identifier
  - `edge_id`: Edge identifier

- **GSI**: RelationshipTypeIndex
  - Partition Key: `relationship_type`
  - Sort Key: `created_at`

- **Node Attributes**:
  - `content`: Memory content
  - `metadata`: Optional JSON string of metadata
- **Edge Attributes**:
  - `source_id`: Source node identifier
  - `target_id`: Target node identifier
  - `relationship_type`: Type of relationship
  - `properties`: Optional JSON string of properties
  - `direction`: `incoming` or `outgoing`
  - `created_at`: Creation timestamp

## Usage

```python
from mem0 import Memory
from mem0.configs import MemoryConfig
from mem0.dynamodb.config import DynamoDBConversationConfig, DynamoDBGraphConfig

# Configure DynamoDB for conversation history
conversation_config = DynamoDBConversationConfig(
    table_name="Mem0Conversations",
    region="us-east-1",
    ttl_enabled=True,
    ttl_days=30
)

# Configure DynamoDB for graph database
graph_config = DynamoDBGraphConfig(
    table_name="Mem0Graph",
    region="us-east-1",
    enable_gsi=True
)

# Create memory config with DynamoDB providers
config = MemoryConfig(
    conversation_store={"provider": "dynamodb", "config": conversation_config},
    graph_store={"provider": "dynamodb", "config": graph_config}
)

# Initialize memory with DynamoDB
memory = Memory(config)
```

## Implementation Details

1. **Factory Pattern**: The implementation uses the factory pattern to create the appropriate storage instances based on configuration.
2. **Bidirectional Edges**: Graph relationships are stored as bidirectional edges for efficient traversal.
3. **Global Secondary Index**: An optional GSI is provided for efficient querying by relationship type.
4. **Time-to-Live**: TTL support for conversation history to automatically expire old conversations.
5. **Batch Operations**: Support for batch operations to improve performance.

## Future Enhancements

1. **DynamoDB Streams**: Integration with DynamoDB Streams for event-driven processing.
2. **Caching Layer**: Add a caching layer to reduce DynamoDB read operations.
3. **DAX Support**: Support for DynamoDB Accelerator (DAX) for high-throughput scenarios.
4. **Backup and Restore**: Utilities for backing up and restoring DynamoDB data.
5. **Migration Tools**: Tools for migrating from SQLite to DynamoDB.

## Testing

The implementation includes unit tests that use the moto library to mock DynamoDB for testing without requiring actual AWS resources.
