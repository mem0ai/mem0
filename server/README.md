# Mem0 REST API Server

Mem0 provides a REST API server (written using FastAPI). Users can perform all operations through REST endpoints. The API also includes OpenAPI documentation, accessible at `/docs` when the server is running.

## Features

- **Create memories:** Create memories based on messages for a user, agent, or run.
- **Retrieve memories:** Get all memories for a given user, agent, or run.
- **Search memories:** Search stored memories based on a query.
- **Update memories:** Update an existing memory.
- **Delete memories:** Delete a specific memory or all memories for a user, agent, or run.
- **Reset memories:** Reset all memories for a user, agent, or run.
- **OpenAPI Documentation:** Accessible via `/docs` endpoint.

## Running the server

Follow the instructions in the [docs](https://docs.mem0.ai/open-source/features/rest-api) to run the server.

## Custom Categories

The `custom_categories` feature allows you to define your own classification rules when adding memories. When provided, the server will use the LLM to automatically classify extracted memories into the specified categories and store the classification results in the memory's `metadata.categories` field.

### How It Works

1. **Define categories**: Pass a `custom_categories` dictionary when creating a memory. Keys are category names, values are descriptions that guide the LLM's classification.
2. **Automatic classification**: The server calls the LLM to analyze each extracted memory and assign it to one or more of the defined categories.
3. **Stored in metadata**: Classification results are stored as a JSON array string in `metadata.categories` (e.g., `'["food_preferences", "restaurants"]'`).
4. **Filter by categories**: Use the `filters` parameter in search/list APIs to retrieve memories by their categories.

### API Examples (curl)

> **Note**: Replace `YOUR_API_KEY` with your actual API key, and `localhost:8888` with your server address.

#### 1. Add a Memory with Custom Categories

```bash
curl -X POST http://localhost:8888/memories \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "I love sushi and ramen. My favorite restaurant is Ichiran."}
    ],
    "user_id": "test-user-001",
    "custom_categories": {
      "food_preferences": "User food preferences and dietary habits",
      "restaurants": "Favorite restaurants and dining experiences"
    },
    "infer": true
  }'
```

The response will contain the created memories. Each memory's `metadata.categories` will include the LLM-assigned categories, for example:

```json
{
  "results": [
    {
      "id": "abc123",
      "memory": "Loves sushi and ramen",
      "metadata": {
        "categories": "[\"food_preferences\"]"
      }
    },
    {
      "id": "def456",
      "memory": "Favorite restaurant is Ichiran",
      "metadata": {
        "categories": "[\"food_preferences\", \"restaurants\"]"
      }
    }
  ]
}
```

#### 2. Search Memories by Categories (POST /search)

Search for memories that belong to a specific category:

```bash
curl -X POST http://localhost:8888/search \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "food",
    "user_id": "test-user-001",
    "filters": {
      "categories": ["food_preferences"]
    }
  }'
```

Search with multiple categories (OR logic — matches memories in any of the specified categories):

```bash
curl -X POST http://localhost:8888/search \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "food",
    "user_id": "test-user-001",
    "filters": {
      "categories": ["food_preferences", "restaurants"]
    }
  }'
```

#### 3. List Memories with Category Filters (POST /memories/list)

Use the `POST /memories/list` endpoint for complex filter queries:

```bash
curl -X POST http://localhost:8888/memories/list \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user-001",
    "filters": {
      "categories": {"contains": "restaurants"}
    }
  }'
```

#### 4. Get Memories with Category Filters (GET /memories)

Pass filters as a JSON-encoded query parameter:

```bash
curl -g -X GET 'http://localhost:8888/memories?user_id=test-user-001&filters={"categories":"restaurants"}' \
  -H "X-API-Key: YOUR_API_KEY"
```

### Supported Filter Operators for Categories

Since `categories` is stored as a JSON array string in metadata, the following filter operators are supported:

| Operator | Description | Example |
|---|---|---|
| Direct list | Match memories containing any of the listed categories | `"categories": ["food_preferences"]` |
| `contains` | Partial string match (case-sensitive) | `"categories": {"contains": "food"}` |
| `icontains` | Partial string match (case-insensitive) | `"categories": {"icontains": "FOOD"}` |
| `in` | Exact match — matches if categories contain any value in the list | `"categories": {"in": ["food_preferences"]}` |
| `nin` | Exclusion — matches if categories do NOT contain any value in the list | `"categories": {"nin": ["restaurants"]}` |

### Adding Memories Without Custom Categories

If `custom_categories` is not provided, the memory creation behaves as usual — no classification is performed and no `categories` field is added to metadata. This ensures full backward compatibility.
