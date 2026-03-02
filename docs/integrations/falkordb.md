# FalkorDB Integration for Mem0

This document describes the FalkorDB integration for Mem0's graph memory functionality.

## Overview

FalkorDB is a high-performance graph database that is Redis-compatible and designed for real-time graph analytics. This integration allows Mem0 to use FalkorDB as a graph memory store for enhanced relationship tracking and memory retrieval.

## Features

- **High Performance**: FalkorDB is optimized for speed and low latency
- **Vector Similarity**: Native support for vector operations with cosine similarity
- **Redis Compatibility**: Uses familiar Redis protocols and commands
- **Scalability**: Designed to handle large-scale graph workloads
- **Real-time Analytics**: Supports real-time graph pattern matching

## Configuration

### Basic Configuration

```python
config = {
    "embedder": {
        "provider": "openai",
        "config": {
            "model": "text-embedding-3-large", 
            "embedding_dims": 3072
        }
    },
    "graph_store": {
        "provider": "falkordb",
        "config": {
            "host": "localhost",
            "port": 6379,
            "graph_name": "my_memory_graph"
        }
    }
}
```

### Configuration with Authentication

```python
config = {
    "embedder": {
        "provider": "openai",
        "config": {
            "model": "text-embedding-3-large", 
            "embedding_dims": 3072
        }
    },
    "graph_store": {
        "provider": "falkordb",
        "config": {
            "host": "localhost",
            "port": 6379,
            "username": "default",
            "password": "your_password",
            "graph_name": "my_memory_graph"
        }
    }
}
```

## Installation

Install Mem0 with graph support:

```bash
pip install "mem0ai[graph]"
```

## FalkorDB Setup

### Using Docker

```bash
docker run -p 6379:6379 -it --rm falkordb/falkordb:latest
```

### Local Installation

Follow the [FalkorDB installation guide](https://docs.falkordb.com/setup.html) for your platform.

## Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | string | `"localhost"` | FalkorDB server host |
| `port` | int | `6379` | FalkorDB server port |
| `username` | string | `None` | Username for authentication |
| `password` | string | `None` | Password for authentication |
| `graph_name` | string | `"memgraph"` | Name of the graph to use |

## Usage Example

```python
from mem0 import Memory

# Initialize with FalkorDB
memory = Memory.from_config(config_dict=config)

# Add memories
messages = [
    {"role": "user", "content": "I love playing tennis with my friend Alice"},
    {"role": "assistant", "content": "I've noted your interest in tennis and friendship with Alice"}
]
memory.add(messages, user_id="john")

# Search memories
results = memory.search("tennis Alice friend", user_id="john")
print(results)

# Get all relationships
all_memories = memory.get_all(user_id="john")
if 'graph_entities' in all_memories:
    for entity in all_memories['graph_entities']:
        print(f"{entity['source']} --[{entity['relationship']}]--> {entity['target']}")
```

## Technical Details

### Vector Indexing

The integration automatically creates:
- A vector index on Entity nodes for similarity search
- Range indexes on user_id for filtering performance
- Proper node and relationship schemas

### Query Optimization

- Uses cosine similarity for vector comparisons
- Implements efficient relationship traversal patterns
- Supports filtered queries by user_id, agent_id, and run_id

### Data Model

```cypher
// Nodes
CREATE (:Entity {
    name: string,
    user_id: string,
    agent_id: string,
    run_id: string,
    embedding: vector,
    mentions: int,
    created: timestamp
})

// Relationships  
CREATE ()-[:CONNECTED_TO {
    name: string,
    mentions: int,
    created: timestamp,
    updated: timestamp
}]->()
```

## Performance Considerations

1. **Vector Similarity**: Uses cosine distance for consistent results
2. **Indexing**: Automatic creation of performance indexes
3. **Batch Operations**: Optimized for multiple relationship operations
4. **Memory Management**: Efficient handling of large embedding vectors

## Example Notebook

See `examples/graph-db-demo/falkordb-example.ipynb` for a complete working example demonstrating:

- Basic setup and configuration
- Adding and retrieving memories
- Cross-user relationship discovery
- Graph structure visualization
- Performance optimization tips

## Troubleshooting

### Connection Issues
- Ensure FalkorDB is running on the specified host and port
- Check firewall settings if connecting remotely
- Verify authentication credentials if using username/password

### Performance Issues
- Monitor vector index usage with appropriate embedding dimensions
- Consider increasing graph capacity for large datasets
- Use appropriate threshold values for similarity search

### Memory Issues
- FalkorDB handles memory management automatically
- Monitor graph size and consider periodic cleanup for large applications