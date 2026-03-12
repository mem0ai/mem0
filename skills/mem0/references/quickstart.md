# Mem0 Platform Quickstart

Get running with Mem0 in 2 minutes. No infrastructure to deploy -- just an API key.

## Prerequisites

- Python 3.10+ or Node.js 18+
- A Mem0 Platform API key ([Get one here](https://app.mem0.ai/dashboard/api-keys))

## Python Setup

### 1. Install

```bash
pip install mem0ai
```

### 2. Set API Key

```bash
export MEM0_API_KEY="m0-your-api-key"
```

### 3. Use

```python
from mem0 import MemoryClient

client = MemoryClient(api_key="your-api-key")

# Add a memory
messages = [
    {"role": "user", "content": "I'm a vegetarian and allergic to nuts."},
    {"role": "assistant", "content": "Got it! I'll remember your dietary preferences."}
]
client.add(messages, user_id="user123")

# Search memories
results = client.search("What are my dietary restrictions?", filters={"user_id": "user123"})
print(results)
```

### Output

```json
{
  "results": [
    {
      "id": "14e1b28a-2014-40ad-ac42-69c9ef42193d",
      "memory": "Allergic to nuts",
      "user_id": "user123",
      "categories": ["health"],
      "created_at": "2025-10-22T04:40:22.864647-07:00",
      "score": 0.30
    }
  ]
}
```

## TypeScript / JavaScript Setup

### 1. Install

```bash
npm install mem0ai
```

### 2. Set API Key

```bash
export MEM0_API_KEY="m0-your-api-key"
```

### 3. Use

```javascript
import MemoryClient from 'mem0ai';

const client = new MemoryClient({ apiKey: 'your-api-key' });

// Add a memory
const messages = [
    {"role": "user", "content": "I'm a vegetarian and allergic to nuts."},
    {"role": "assistant", "content": "Got it! I'll remember your dietary preferences."}
];
await client.add(messages, { user_id: "user123" });

// Search memories
const results = await client.search("What are my dietary restrictions?", {
    filters: { user_id: "user123" }
});
console.log(results);
```

## cURL

```bash
export MEM0_API_KEY="m0-your-api-key"

# Add memory
curl -X POST https://api.mem0.ai/v1/memories/ \
  -H "Authorization: Token $MEM0_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "I am a vegetarian and allergic to nuts."},
      {"role": "assistant", "content": "Got it! I will remember your dietary preferences."}
    ],
    "user_id": "user123"
  }'

# Search memories
curl -X POST https://api.mem0.ai/v2/memories/search/ \
  -H "Authorization: Token $MEM0_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are my dietary restrictions?",
    "filters": {"user_id": "user123"}
  }'
```

## Async Client (Python)

For high-throughput applications:

```python
from mem0 import AsyncMemoryClient

client = AsyncMemoryClient(api_key="your-api-key")

await client.add(messages, user_id="user123")
results = await client.search("query", user_id="user123")
```

## With Organization & Project Scope

```python
client = MemoryClient(
    api_key="your-api-key",
    org_id="your-org-id",
    project_id="your-project-id"
)
```

## Next Steps

- [Platform API Reference](general.md)
- [Integration Patterns](integration-patterns.md) -- add memory to LangChain, CrewAI, Vercel AI, etc.
- [TypeScript SDK Reference](typescript-sdk.md) -- complete TS/JS API
