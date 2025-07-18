# Advanced OpenMemory MCP Features

## New Search Parameters
- `topK`: Limit results (default 10)
- `threshold`: Minimum similarity (0-1)
- `filters`: Metadata filtering object
- `projectId`: Project-level isolation
- `orgId`: Organization-level isolation

## New Add Parameters
- `metadata`: Custom tags/categories
- `projectId`: Assign to project
- `orgId`: Assign to organization

These features work with the updated Qdrant vector store using 1024-dimensional embeddings.
