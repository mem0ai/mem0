# Migration Guide: Upgrading to mem0 1.0.0

## TL;DR

**What changed?** We simplified the API by removing confusing version parameters. Now everything returns a consistent format: `{"results": [...]}`.

**What you need to do:**
1. Upgrade: `pip install mem0ai==1.0.0`
2. Remove `version` and `output_format` parameters from your code
3. Update response handling to use `result["results"]` instead of treating responses as lists

**Time needed:** ~5-10 minutes for most projects

---

## Quick Migration Guide

### 1. Install the Update

```bash
pip install mem0ai==1.0.0
```

### 2. Update Your Code

**If you're using the Memory API:**

```python
# Before
memory = Memory(config=MemoryConfig(version="v1.1"))
result = memory.add("I like pizza")

# After
memory = Memory()  # That's it - version is automatic now
result = memory.add("I like pizza")
```

**If you're using the Client API:**

```python
# Before
client.add(messages, output_format="v1.1")
client.search(query, version="v2", output_format="v1.1")

# After
client.add(messages)  # Just remove those extra parameters
client.search(query)
```

### 3. Update How You Handle Responses

All responses now use the same format: a dictionary with `"results"` key.

```python
# Before - you might have done this
result = memory.add("I like pizza")
for item in result:  # Treating it as a list
    print(item)

# After - do this instead
result = memory.add("I like pizza")
for item in result["results"]:  # Access the results key
    print(item)

# Graph relations (if you use them)
if "relations" in result:
    for relation in result["relations"]:
        print(relation)
```

---

## Enhanced Message Handling

The platform client (MemoryClient) now supports the same flexible message formats as the OSS version:

```python
from mem0 import MemoryClient

client = MemoryClient(api_key="your-key")

# All three formats now work:

# 1. Single string (automatically converted to user message)
client.add("I like pizza", user_id="alice")

# 2. Single message dictionary
client.add({"role": "user", "content": "I like pizza"}, user_id="alice")

# 3. List of messages (conversation)
client.add([
    {"role": "user", "content": "I like pizza"},
    {"role": "assistant", "content": "I'll remember that!"}
], user_id="alice")
```

### Async Mode Configuration

The `async_mode` parameter now defaults to `True` but can be configured:

```python
# Default behavior (async_mode=True)
client.add(messages, user_id="alice")

# Explicitly set async mode
client.add(messages, user_id="alice", async_mode=True)

# Disable async mode if needed
client.add(messages, user_id="alice", async_mode=False)
```

**Note:** `async_mode=True` provides better performance for most use cases. Only set it to `False` if you have specific synchronous processing requirements.

---

## That's It!

For most users, that's all you need to know. The changes are:
- ✅ No more `version` or `output_format` parameters
- ✅ Consistent `{"results": [...]}` response format
- ✅ Cleaner, simpler API

---

## Common Issues

**Getting `KeyError: 'results'`?**

Your code is still treating the response as a list. Update it:
```python
# Change this:
for memory in response:

# To this:
for memory in response["results"]:
```

**Getting `TypeError: unexpected keyword argument`?**

You're still passing old parameters. Remove them:
```python
# Change this:
client.add(messages, output_format="v1.1")

# To this:
client.add(messages)
```

**Seeing deprecation warnings?**

Remove any explicit `version="v1.0"` from your config:
```python
# Change this:
memory = Memory(config=MemoryConfig(version="v1.0"))

# To this:
memory = Memory()
```

---

## What's New in 1.0.0

- **Better vector stores:** Fixed OpenSearch and improved reliability across all stores
- **Cleaner API:** One way to do things, no more confusing options
- **Enhanced GCP support:** Better Vertex AI configuration options
- **Flexible message input:** Platform client now accepts strings, dicts, and lists (aligned with OSS)
- **Configurable async_mode:** Now defaults to `True` but users can override if needed

---

## Need Help?

- Check [GitHub Issues](https://github.com/mem0ai/mem0/issues)
- Read the [documentation](https://docs.mem0.ai/)
- Open a new issue if you're stuck

---

## Advanced: Configuration Changes

**If you configured vector stores with version:**

```python
# Before
config = MemoryConfig(
    version="v1.1",
    vector_store=VectorStoreConfig(...)
)

# After
config = MemoryConfig(
    vector_store=VectorStoreConfig(...)
)
```

---

## Testing Your Migration

Quick sanity check:

```python
from mem0 import Memory

memory = Memory()

# Add should return a dict with "results"
result = memory.add("I like pizza", user_id="test")
assert "results" in result

# Search should return a dict with "results"
search = memory.search("food", user_id="test")
assert "results" in search

# Get all should return a dict with "results"
all_memories = memory.get_all(user_id="test")
assert "results" in all_memories

print("✅ Migration successful!")
```
