# Mem0 Platform Quickstart

Get running with Mem0 in 2 minutes. No infrastructure to deploy -- just an API key.

## Prerequisites

- Python 3.10+ or Node.js 18+
- A Mem0 Platform API key ([Get one here](https://app.mem0.ai/dashboard/api-keys?utm_source=oss&utm_medium=mem0-plugin-skill-quickstart))

## Python Setup

```bash
pip install mem0ai
export MEM0_API_KEY="m0-your-api-key"
```

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

### Async Client

```python
from mem0 import AsyncMemoryClient

client = AsyncMemoryClient(api_key="your-api-key")

await client.add(messages, user_id="user123")
results = await client.search("query", filters={"user_id": "user123"})
```

## TypeScript / JavaScript Setup

```bash
npm install mem0ai
export MEM0_API_KEY="m0-your-api-key"
```

```javascript
import MemoryClient from 'mem0ai';

const client = new MemoryClient({ apiKey: 'your-api-key' });

// Add a memory
const messages = [
    {"role": "user", "content": "I'm a vegetarian and allergic to nuts."},
    {"role": "assistant", "content": "Got it! I'll remember your dietary preferences."}
];
await client.add(messages, { userId: "user123" });

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
curl -X POST https://api.mem0.ai/v3/memories/search/ \
  -H "Authorization: Token $MEM0_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are my dietary restrictions?",
    "filters": {"user_id": "user123"}
  }'
```

## Sample Response

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

## Next Steps

- [SDK Guide](sdk-guide.md) -- all methods for Python and TypeScript
- [API Reference](api-reference.md) -- REST endpoints and memory object structure
- [Integration Patterns](integration-patterns.md) -- LangChain, CrewAI, Vercel AI, etc.
