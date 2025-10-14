# Mem0 DynamoDB Implementation

This module provides DynamoDB implementations for mem0's storage components:

1. **Conversation History Storage**: Replaces SQLite with DynamoDB for storing conversation history
2. **Graph Database**: Implements graph database functionality using DynamoDB's flexible schema

## Features

- **Scalable**: Leverages DynamoDB's virtually unlimited scaling capabilities
- **Managed**: No need to maintain database infrastructure
- **Durable**: Built on AWS's highly available and durable storage
- **Flexible**: Supports both conversation history and graph database use cases
- **Cost-effective**: Pay only for what you use with on-demand capacity

## Setup

### 1. Create DynamoDB Tables

You can create the required DynamoDB tables using one of these methods:

#### Using CloudFormation

```bash
aws cloudformation deploy \
  --template-file mem0/dynamodb/cloudformation.yaml \
  --stack-name mem0-dynamodb \
  --capabilities CAPABILITY_IAM
```

#### Using dynamodb-shell

```bash
ddbsh < schema.sql
```

#### Using the Utility Function

```python
from mem0.dynamodb.utils import create_dynamodb_tables

create_dynamodb_tables(
    region="us-east-1",
    conversation_table_name="Mem0Conversations",
    graph_table_name="Mem0Graph",
    ttl_enabled=True,
    gsi_enabled=True
)
```

### 2. Configure Mem0 to Use DynamoDB

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

## Performance Considerations

- Use appropriate DynamoDB capacity mode (on-demand or provisioned) based on your workload
- Consider enabling DynamoDB Accelerator (DAX) for high-throughput read scenarios
- Monitor and optimize access patterns to avoid hot keys
- Use batch operations for bulk data processing

## Security

- Use IAM roles for authentication when possible
- Encrypt data at rest using AWS KMS
- Implement least privilege access policies
- Consider using VPC endpoints for enhanced security
