# Migration Guide: Upgrading to mem0ai 1.0.0

This guide will help you migrate from mem0ai 0.x to the new 1.0.0 version.

## Breaking Changes

### 1. API Version Changes

**Before (0.x):**
```python
# Multiple API versions supported
memory = Memory(config=MemoryConfig(version="v1.1"))

# Client with output_format parameter
client.add(messages, output_format="v1.1")
client.search(query, version="v1", output_format="v1.1") 
client.get_all(version="v1", output_format="v1.1")
```

**After (1.0.0):**
```python
# v1.1 API is default (v1.0 is deprecated)
memory = Memory()  # Defaults to v1.1 format

# Client API with correct versioning behavior:
client.add(messages)  # Uses v1 API endpoint
client.add(messages, output_format="v1.1")  # Uses v1.1 API endpoint
client.search(query)  # Uses v2 API endpoint  
client.get_all()  # Uses v2 API endpoint
```

### 2. API Versioning Behavior

**New API versioning behavior:**

- **Add operations**: Use v1 endpoint by default, v1.1 when `output_format="v1.1"` is specified  
- **Get/Search operations**: Always use v2 endpoints for enhanced filtering capabilities
- **Removed parameters**: `version` parameter from `get_all()` and `search()` methods
- **Async mode**: Now default behavior (no parameter needed)

### 3. Response Format Standardization

**Before (0.x):**
```python
# Inconsistent response formats based on api_version
result = memory.add(messages)
# Could return list or dict depending on version

memories = memory.get_all()  
# Could return list or dict depending on version
```

**After (1.0.0):**
```python
# v1.1 format is now default (consistent dict format)
result = memory.add(messages)
# Returns: {"results": [...], "relations": [...] (if graph enabled)}

memories = memory.get_all()
# Returns: {"results": [...], "relations": [...] (if graph enabled)}

# v1.0 format still works but shows deprecation warning
memory_v1 = Memory(config=MemoryConfig(version="v1.0"))
result = memory_v1.add(messages)  # Returns raw list (with warning)
```

## Migration Steps

### Step 1: Update Dependencies

```bash
pip install mem0ai==1.0.0
```

### Step 2: Update Code

#### Memory API Changes

```python
# Before
from mem0 import Memory

memory = Memory(config=MemoryConfig(version="v1.1"))

# After - no changes needed, v1.1 is automatic
from mem0 import Memory

memory = Memory()  # Defaults to v1.1 format
```

#### Client API Changes

```python
# Before
from mem0 import MemoryClient

client = MemoryClient(api_key="your-key")

# Remove all version and output_format parameters
result = client.add(messages, output_format="v1.1")
memories = client.search(query, version="v2", output_format="v1.1")
all_memories = client.get_all(version="v2", output_format="v1.1")

# After
from mem0 import MemoryClient

client = MemoryClient(api_key="your-key")

# Simplified API calls
result = client.add(messages)
memories = client.search(query)
all_memories = client.get_all()
```

#### Response Handling

```python
# Before - inconsistent response formats
result = memory.add(messages)
if isinstance(result, list):
    # Handle v1.0 format
    for item in result:
        print(item)
else:
    # Handle v1.1+ format
    for item in result["results"]:
        print(item)

# After - consistent response format
result = memory.add(messages)
for item in result["results"]:
    print(item)

# Access graph relations if enabled
if "relations" in result:
    for relation in result["relations"]:
        print(relation)
```

### Step 3: Remove Deprecated Code

Remove any code that handled multiple API versions:

```python
# Remove these patterns
if version == "v1.0":
    # handle old format
elif version == "v1.1":
    # handle new format

# Remove version-specific logic
def handle_response(response, api_version):
    if api_version == "v1.0":
        return response  # list format
    else:
        return response["results"]  # dict format
```

### Step 4: Update Configuration

#### Vector Store Configuration

```python
# Before - version in config
config = MemoryConfig(
    version="v1.1",
    vector_store=VectorStoreConfig(...)
)

# After - no version needed
config = MemoryConfig(
    vector_store=VectorStoreConfig(...)
)
```

#### Enhanced GCP Support

```python
# New: Enhanced Vertex AI configuration options
from mem0.configs.vector_stores.vertex_ai_vector_search import GoogleMatchingEngineConfig

# Option 1: Using credentials file (existing)
config = GoogleMatchingEngineConfig(
    project_id="your-project",
    credentials_path="/path/to/service-account.json",
    # ... other params
)

# Option 2: Using credentials dict (new in v1.0.0)
service_account_info = {
    "type": "service_account",
    "project_id": "your-project",
    # ... rest of service account JSON
}

config = GoogleMatchingEngineConfig(
    project_id="your-project",
    service_account_json=service_account_info,
    # ... other params
)
```

## Testing Your Migration

### 1. Test Basic Functionality

```python
from mem0 import Memory

# Test memory operations
memory = Memory()

# Test adding memories
result = memory.add("I like pizza")
assert "results" in result
assert len(result["results"]) > 0

# Test searching
search_result = memory.search("food preferences", user_id="test_user")
assert "results" in search_result

# Test listing all
all_memories = memory.get_all(user_id="test_user")
assert "results" in all_memories
```

### 2. Test Client Operations

```python
from mem0 import MemoryClient

client = MemoryClient(api_key="your-api-key")

# Test all client methods work without deprecated parameters
messages = [{"role": "user", "content": "I love traveling"}]
result = client.add(messages, user_id="test_user")
assert "results" in result or isinstance(result, list)  # Platform may vary

memories = client.search("travel", user_id="test_user")
all_memories = client.get_all(user_id="test_user")
```

## New Features in v1.0.0

### 1. Improved Vector Store Support

- Fixed OpenSearch vector store integration
- Enhanced error handling across all vector stores
- Better performance and reliability

### 2. Enhanced GCP Integration

- Support for service account JSON dict (in addition to file path)
- Improved Vertex AI Vector Search configuration

### 3. Simplified API

- Default API version is now v1.1 (v1.0 deprecated)
- Removed deprecated parameters
- Standardized response formats

## Deprecation Warning for v1.0 Users

If you're currently using `version="v1.0"`, you'll see a deprecation warning:

```
DeprecationWarning: The v1.0 API format is deprecated and will be removed in mem0ai 2.0.0. 
Please upgrade to v1.1 format which returns a dict with 'results' key. 
Set version='v1.1' in your MemoryConfig.
```

**To resolve this:**
```python
# Before (shows warning)
memory = Memory(config=MemoryConfig(version="v1.0"))

# After (no warning)
memory = Memory()  # Uses v1.1 by default
# OR explicitly set v1.1
memory = Memory(config=MemoryConfig(version="v1.1"))
```

## Common Issues and Solutions

### Issue 1: "KeyError: 'results'"

**Problem:** Your code expects the old list format response.

**Solution:** Update response handling:
```python
# Before
for memory in response:  # Assuming response is a list
    print(memory)

# After  
for memory in response["results"]:
    print(memory)
```

### Issue 2: "TypeError: unexpected keyword argument 'output_format'"

**Problem:** Code still passing deprecated parameters.

**Solution:** Remove all deprecated parameters:
```python
# Before
client.add(messages, output_format="v1.1", async_mode=True)

# After
client.add(messages)
```

### Issue 3: Vector Store Connection Issues

**Problem:** Vector store tests failing after upgrade.

**Solution:** The OpenSearch integration has been fixed. Update your test configurations and retry.

## Support

If you encounter issues during migration:

1. Check the [GitHub Issues](https://github.com/mem0ai/mem0/issues) for similar problems
2. Review the updated [API documentation](https://docs.mem0.ai/)  
3. Create a new issue with your specific migration problem

## Summary

mem0ai 1.0.0 provides a cleaner, more consistent API while removing deprecated features. The migration primarily involves:

1. Removing deprecated parameters (`output_format`, `version`, `async_mode`)
2. Updating response handling to expect consistent `{"results": [...]}` format
3. Updating dependencies to v1.0.0

Most applications will require minimal changes, mainly removing deprecated parameters and updating response parsing logic.