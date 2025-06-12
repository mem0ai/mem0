# Jean Memory Agent API v1: API Reference

## 1. Overview

The Jean Memory Agent API is a specialized, stateless REST API designed to provide a shared memory pool for "swarms" of AI agents. It allows multiple agents to collaborate on complex tasks by reading and writing to a common, taggable memory store, ensuring context is shared effectively and without interference.

This API is architecturally isolated from the core MCP/SSE tools and is designed for programmatic, high-throughput use cases. For advanced, real-world examples, please see our [Agent API Cookbook](./api_cookbook.md).

## 2. Authentication

All endpoints are protected and require a `Bearer` token for authentication. This should be a JWT token issued to your organization.

-   **Header:** `Authorization: Bearer <YOUR_JWT_TOKEN>`

### Application Scoping (Client Name)

To keep memories from different applications or agent teams separate, even under the same user account, you must provide a client name header. This is highly recommended.

-   **Header:** `X-Client-Name: <your_app_or_team_name>`

If this header is provided, memories will be created and scoped to that specific client name. Searches can also be filtered by this name, ensuring data from different agent swarms does not interfere.

## 3. Endpoints

The base path for the agent API is `/agent`.

---

### Add Tagged Memory

Adds a new memory with associated metadata tags to the pool.

-   **Endpoint:** `POST /v1/memory/add_tagged`
-   **Success Code:** `201 Created`

**Request Body:**

```json
{
  "text": "The content of the memory to be stored.",
  "metadata": {
    "task_id": "task_abc_123",
    "agent_id": "researcher-01",
    "type": "fact",
    "priority": "high"
  }
}
```

**Example `curl` Request:**

```bash
curl -X POST https://api.jeanmemory.com/agent/v1/memory/add_tagged \
-H "Authorization: Bearer <YOUR_JWT_TOKEN>" \
-H "Content-Type: application/json" \
-H "X-Client-Name: koii_swarm_app" \
-d '{
  "text": "The market shows a growing demand for premium, high-performance EVs.",
  "metadata": {"task_id": "strat_task_456", "agent_id": "market-researcher-02"}
}'
```

**Response Body:**

```json
{
  "status": "success",
  "memory_id": "a1b2c3d4-e5f6-a7b8-c9d0-e1f2a3b4c5d6"
}
```

---

### Search by Tags

Searches the memory pool for memories matching a specific set of metadata tags.

-   **Endpoint:** `POST /v1/memory/search_by_tags`
-   **Success Code:** `200 OK`

**Request Body:**

The `filter` object performs a key-value search within the `metadata` of the memories. The search is an `AND` search; all key-value pairs in the filter must be present in a memory's metadata for it to be returned.

```json
{
  "filter": {
    "task_id": "strat_task_456",
    "type": "fact"
  }
}
```

**Example `curl` Request:**

```bash
curl -X POST https://api.jeanmemory.com/agent/v1/memory/search_by_tags \
-H "Authorization: Bearer <YOUR_JWT_TOKEN>" \
-H "Content-Type: application/json" \
-H "X-Client-Name: koii_swarm_app" \
-d '{
  "filter": {"task_id": "strat_task_456"}
}'
```

**Response Body:**

The response is a list of full memory objects that match the filter.

```json
[
  {
    "id": "a1b2c3d4-e5f6-a7b8-c9d0-e1f2a3b4c5d6",
    "user_id": "...",
    "app_id": "...",
    "content": "The market shows a growing demand for premium, high-performance EVs.",
    "metadata_": {
      "task_id": "strat_task_456",
      "agent_id": "market-researcher-02"
    },
    "state": "active",
    "created_at": "...",
    "updated_at": "...",
    "archived_at": null,
    "deleted_at": null
  }
]
``` 