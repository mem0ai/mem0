# Jean Memory V2 🧠✨

**Advanced Memory Ingestion & Search Library**

A modular, enterprise-grade memory system that combines the power of Mem0 Graph Memory, Graphiti temporal reasoning, and Gemini AI synthesis to create the most intelligent memory management solution available.

## 🌟 Features

### 🔍 **Hybrid Search Intelligence**
- **Mem0 Graph Memory**: Semantic vector search with graph relationships
- **Graphiti**: Temporal reasoning and entity relationship mapping  
- **Gemini AI Synthesis**: Intelligent answer generation from multiple sources
- **Confidence Scoring**: AI-powered relevance assessment

### 📥 **Advanced Ingestion Pipeline**
- **Safety Checks**: Content validation and contamination detection
- **Deduplication**: Intelligent duplicate removal
- **Batch Processing**: Efficient handling of large memory sets
- **Multi-Engine Storage**: Parallel ingestion to Mem0 and Graphiti

### 🔧 **Enterprise Ready**
- **Async/Await**: Full async support for high performance
- **Error Handling**: Comprehensive exception hierarchy
- **Configuration Management**: Flexible API key and setting management
- **Health Monitoring**: Built-in health checks and diagnostics
- **V1 Compatibility**: Seamless integration with existing systems

## 🚀 Quick Start

### Installation

```bash
# Install from your repository
pip install -e ./jean_memory_v2

# Or install dependencies directly
pip install -r jean_memory_v2/requirements.txt
```

### Basic Usage

```python
import asyncio
from jean_memory_v2 import JeanMemoryV2

async def main():
    # Option 1: Initialize with your API keys manually
    jm = JeanMemoryV2(
        openai_api_key="sk-...",
        qdrant_api_key="your-qdrant-key",
        qdrant_host="your-qdrant-host",
        qdrant_port="6333",
        neo4j_uri="neo4j://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="password",
        gemini_api_key="AIza..."  # Optional for AI synthesis
    )
    
    # Option 2: Load from openmemory test environment (recommended for testing)
    # jm = JeanMemoryV2.from_openmemory_test_env()
    
    # Ingest memories
    result = await jm.ingest_memories(
        memories=["I love hiking", "My favorite color is blue"],
        user_id="user123"
    )
    print(f"Ingested {result.successful_ingestions} memories")
    
    # Search with AI synthesis
    search_result = await jm.search("What are my hobbies?", user_id="user123")
    print(search_result.synthesis)
    
    # Clean up
    await jm.close()

if __name__ == "__main__":
    asyncio.run(main())
```

### OpenMemory Test Environment (Recommended)

For easy testing with your existing OpenMemory setup:

```python
import asyncio
from jean_memory_v2 import JeanMemoryV2

async def main():
    # Automatically loads from openmemory/api/.env.test
    jm = JeanMemoryV2.from_openmemory_test_env()
    
    # Ready to use with your test database credentials
    await jm.ingest_memories(["Test memory"], user_id="test_user")
    result = await jm.search("test", user_id="test_user")
    
    # Clean up for testing
    await jm.clear_user_data_for_testing("test_user", confirm=True)
    await jm.close()

if __name__ == "__main__":
    asyncio.run(main())
```

### Configuration from Environment

```python
from jean_memory_v2 import JeanMemoryV2

# Load from .env file
jm = JeanMemoryV2.from_env_file(".env")

# Or from environment variables
jm = JeanMemoryV2.from_environment()
```

## 📖 API Reference

### Core Classes

#### `JeanMemoryV2`
Main interface combining search and ingestion capabilities.

```python
# Initialize
jm = JeanMemoryV2(openai_api_key="...", qdrant_api_key="...", ...)

# Ingestion
result = await jm.ingest_memories(memories, user_id)
result = await jm.ingest_from_file("memories.txt", user_id)

# Search
result = await jm.search(query, user_id, limit=20)
mem0_results = await jm.search_mem0_only(query, user_id)
graphiti_results = await jm.search_graphiti_only(query, user_id)

# Management
stats = await jm.get_user_stats(user_id)
health = await jm.health_check()
await jm.clear_user_memories(user_id)  # ⚠️ Use with caution
```

#### `SearchResult`
Structured search results with AI synthesis.

```python
result = await jm.search("query", "user_id")

print(result.synthesis)           # AI-generated answer
print(result.confidence_score)    # Confidence (0.0-1.0)
print(result.total_results)       # Number of results found
print(result.processing_time)     # Search time in seconds
print(result.mem0_results)        # Raw Mem0 results
print(result.graphiti_results)    # Raw Graphiti results
```

#### `IngestionResult`
Detailed ingestion statistics and results.

```python
result = await jm.ingest_memories(memories, user_id)

print(result.success_rate)           # Success percentage
print(result.successful_ingestions)  # Number succeeded
print(result.failed_ingestions)      # Number failed
print(result.processing_time)        # Processing time
print(result.errors)                 # List of error messages
```

### Configuration

#### `JeanMemoryConfig`
Comprehensive configuration management.

```python
from jean_memory_v2 import JeanMemoryConfig

# Manual configuration
config = JeanMemoryConfig(
    openai_api_key="sk-...",
    qdrant_api_key="...",
    # ... other settings
    enable_safety_checks=True,
    enable_deduplication=True,
    batch_size=100
)

# From environment file
config = JeanMemoryConfig.from_env_file(".env")

# Convert to engine-specific configs
mem0_config = config.to_mem0_config()
graphiti_config = config.to_graphiti_config()
```

## 🧪 Database Cleaning for Testing

Jean Memory V2 includes comprehensive database cleaning utilities specifically designed for testing scenarios. These functions help ensure clean test environments and proper test isolation.

### Quick Testing Functions

```python
import asyncio
from jean_memory_v2 import JeanMemoryV2

async def test_with_clean_database():
    jm = JeanMemoryV2(...)
    
    try:
        # 1. Clear user data before test
        await jm.clear_user_data_for_testing("test_user", confirm=True)
        
        # 2. Verify clean state
        verification = await jm.verify_clean_state_for_testing(["test_user"])
        assert verification["is_clean"], "Database not clean!"
        
        # 3. Run your test operations
        await jm.ingest_memories(["test memory"], user_id="test_user")
        result = await jm.search("test query", user_id="test_user")
        
        # 4. Clean up after test
        await jm.clear_user_data_for_testing("test_user", confirm=True)
        
    finally:
        await jm.close()
```

### Convenience Functions

```python
from jean_memory_v2 import (
    clear_user_for_testing, 
    clear_all_for_testing, 
    verify_clean_database,
    JeanMemoryConfig
)

async def quick_cleanup():
    config = JeanMemoryConfig.from_environment()
    
    # Clear specific user
    result = await clear_user_for_testing(config, "test_user")
    print(f"Cleared: {result['mem0_deleted']} Mem0 + {result['graphiti_deleted']} Graphiti")
    
    # Verify database is clean
    is_clean = await verify_clean_database(config, ["test_user"])
    print(f"Database clean: {is_clean}")
    
    # ⚠️ DANGER: Clear ALL data (only for isolated test environments)
    # await clear_all_for_testing(config)
```

### Advanced Database Cleaner

```python
from jean_memory_v2 import DatabaseCleaner, JeanMemoryConfig

async def advanced_testing_setup():
    config = JeanMemoryConfig.from_environment()
    cleaner = DatabaseCleaner(config)
    
    try:
        await cleaner.initialize()
        
        # Get comprehensive database statistics
        stats = await cleaner.get_database_stats()
        print(f"Database stats: {stats}")
        
        # Create test isolation with unique prefixes
        test_prefix = await cleaner.create_test_isolation("my_test")
        print(f"Test isolation prefix: {test_prefix}")
        
        # Verify clean state for multiple users
        verification = await cleaner.verify_clean_state(["user1", "user2", "user3"])
        print(f"Multi-user verification: {verification}")
        
        # Clear data by prefix (when implemented)
        # await cleaner.clear_collections_by_prefix("test_", confirm=True)
        
    finally:
        await cleaner.close()
```

### Test Isolation Pattern

```python
async def run_isolated_test(test_name: str, user_id: str):
    """Perfect test isolation with cleanup"""
    
    jm = JeanMemoryV2.from_environment()
    
    try:
        await jm.initialize()
        
        # Ensure clean state
        await jm.clear_user_data_for_testing(user_id, confirm=True)
        verification = await jm.verify_clean_state_for_testing([user_id])
        assert verification["is_clean"], "Database not clean before test!"
        
        # Run test operations
        await jm.ingest_memories([f"Test data for {test_name}"], user_id=user_id)
        search_result = await jm.search(f"What is {test_name}?", user_id=user_id)
        
        # Verify test worked
        assert len(search_result.mem0_results) > 0, "No search results found!"
        
        # Clean up
        await jm.clear_user_data_for_testing(user_id, confirm=True)
        final_verification = await jm.verify_clean_state_for_testing([user_id])
        assert final_verification["is_clean"], "Database not clean after test!"
        
    finally:
        await jm.close()

# Run multiple isolated tests
await run_isolated_test("memory_ingestion", "test_user_1")
await run_isolated_test("search_functionality", "test_user_2")
```

### Available Cleaning Functions

| Function | Description | Safety |
|----------|-------------|--------|
| `clear_user_data_for_testing()` | Clear all data for specific user | ⚠️ Requires `confirm=True` |
| `clear_all_data_for_testing()` | Clear ALL database data | 🚨 Extremely dangerous |
| `verify_clean_state_for_testing()` | Check if database is clean | ✅ Read-only |
| `get_database_stats_for_testing()` | Get database statistics | ✅ Read-only |
| `clear_user_for_testing()` | Convenience function for user clearing | ⚠️ Requires `confirm=True` |
| `verify_clean_database()` | Convenience function for verification | ✅ Read-only |

## 🔌 API Integration

### FastAPI Integration

```python
from fastapi import FastAPI, Depends
from jean_memory_v2.api_adapter import JeanMemoryV2ApiAdapter, create_v2_adapter_from_env

app = FastAPI()
v2_adapter = create_v2_adapter_from_env(".env")

@app.post("/api/v2/memories/")
async def create_memory_v2(user_id: str, text: str):
    result = await v2_adapter.create_memory_v2(user_id, text)
    return result

@app.post("/api/v2/memories/search/")
async def search_memories_v2(user_id: str, query: str):
    result = await v2_adapter.search_memories_v2(user_id, query)
    return result
```

### V1 Compatibility

```python
# Enhance existing V1 routes with V2 capabilities
@app.post("/api/v1/memories/")
async def create_memory_v1_enhanced(user_id: str, text: str):
    # Uses V2 under the hood but returns V1-compatible response
    result = await v2_adapter.create_memory_v2(user_id, text)
    return {"status": result["status"], "memory_id": result["memory_id"]}
```

## 🏗️ Architecture

### Multi-Engine Design

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Jean Memory   │    │                  │    │     Gemini      │
│       V2        │───▶│  Hybrid Search   │───▶│   AI Synthesis  │
│   (Main API)    │    │     Engine       │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐    ┌──────────────────┐
│   Ingestion     │    │                  │
│    Engine       │    │   Search Sources │
└─────────────────┘    └──────────────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐    ┌──────────────────┐
│                 │    │                  │
│ Mem0 + Graphiti │    │ Mem0 + Graphiti  │
│   (Storage)     │    │   (Retrieval)    │
│                 │    │                  │
└─────────────────┘    └──────────────────┘
```

### Data Flow

1. **Ingestion**: Memories → Safety Checks → Deduplication → Mem0 + Graphiti
2. **Search**: Query → Mem0 Search + Graphiti Search → Result Merging → Gemini Synthesis
3. **Response**: Structured results with confidence scores and source attribution

## 🔧 Configuration

### Environment Variables

```bash
# Required
OPENAI_API_KEY=sk-...
QDRANT_API_KEY=your-key
QDRANT_HOST=your-host
QDRANT_PORT=6333
NEO4J_URI=neo4j://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Optional
GEMINI_API_KEY=AIza...
QDRANT_COLLECTION_PREFIX=jeanmemory_v2
DEFAULT_SEARCH_LIMIT=20
BATCH_SIZE=100
ENABLE_SAFETY_CHECKS=true
ENABLE_DEDUPLICATION=true
```

### Advanced Configuration

```python
config = JeanMemoryConfig(
    # ... API keys ...
    
    # Search settings
    default_search_limit=20,
    max_search_limit=100,
    enable_graph_memory=True,
    enable_gemini_synthesis=True,
    
    # Ingestion settings  
    batch_size=100,
    enable_safety_checks=True,
    enable_deduplication=True,
    
    # Performance
    connection_timeout=30,
    max_retries=3
)
```

## 🧪 Examples

See the `examples/` directory for comprehensive examples:

- **`basic_usage.py`**: Core functionality demonstration
- **`api_integration.py`**: FastAPI integration with V1/V2 compatibility
- **`advanced_search.py`**: Advanced search patterns and configurations
- **`batch_ingestion.py`**: Large-scale memory ingestion

## 🔍 Monitoring & Debugging

### Health Checks

```python
health = await jm.health_check()
print(f"System status: {health['jean_memory_v2']}")
print(f"Mem0: {health['components']['mem0']}")
print(f"Graphiti: {health['components']['graphiti']}")
print(f"Gemini: {health['components']['gemini']}")
```

### User Statistics

```python
stats = await jm.get_user_stats(user_id)
print(f"Mem0 memories: {stats.get('mem0_memory_count', 0)}")
print(f"Graphiti nodes: {stats.get('graphiti_node_count', 0)}")
```

### Logging

```python
from jean_memory_v2.utils import setup_logging

# Enable detailed logging
setup_logging(level="DEBUG")
```

## 🚨 Safety & Best Practices

### Content Safety
- Automatic validation of memory content
- Detection of suspicious patterns and contamination
- Length limits and character filtering

### Performance
- Async/await throughout for non-blocking operations
- Batch processing for large datasets
- Connection pooling and retry logic

### Security
- API key validation and secure storage
- User ID validation and sanitization
- Error handling without information leakage

## 🔄 Migration from V1

### Gradual Migration Strategy

1. **Install V2 alongside V1**
2. **Use API adapter for backward compatibility**
3. **Gradually enable V2 features**
4. **Monitor performance and health**
5. **Full migration when ready**

### V1 Compatibility Layer

```python
# V1 route enhanced with V2
@app.post("/api/v1/memories/search/enhanced/")
async def search_v1_with_v2_features(user_id: str, query: str, enable_ai: bool = False):
    result = await v2_adapter.search_memories_v2(
        user_id=user_id, 
        query=query, 
        include_synthesis=enable_ai
    )
    # Return V1 format with optional V2 enhancements
    return format_for_v1_compatibility(result, include_v2_features=enable_ai)
```

## 📝 License

[Your License Here]

## 🤝 Contributing

[Contributing Guidelines]

## 🐛 Issues & Support

[Issue Tracking Information]

---

**Jean Memory V2** - Intelligent memory management for the AI age 🧠✨ 