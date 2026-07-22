# n8n-nodes-mem0

This is an n8n community node that lets you use [Mem0](https://mem0.ai) — the memory layer for AI agents — in your n8n workflows.

Mem0 gives your agents long-term memory: add memories from conversations, then search and recall them across sessions.

[n8n](https://n8n.io) is a [fair-code licensed](https://docs.n8n.io/reference/license/) workflow automation platform.

[Installation](#installation) · [Operations](#operations) · [Credentials](#credentials) · [Usage](#usage) · [Resources](#resources)

## Installation

Follow the [community nodes installation guide](https://docs.n8n.io/integrations/community-nodes/installation/) and install `n8n-nodes-mem0`.

## Operations

The **Memory** resource supports:

| Operation | Description | Endpoint |
| --- | --- | --- |
| **Add** | Extract and store memories from messages | `POST /v3/memories/add/` |
| **Search** | Semantic search over stored memories | `POST /v3/memories/search/` |
| **Get Many** | List memories for a user (paginated) | `POST /v3/memories/` |
| **Get** | Retrieve a single memory by ID | `GET /v1/memories/{id}/` |
| **Update** | Update a memory's text or metadata | `PUT /v1/memories/{id}/` |
| **Delete** | Delete a single memory by ID | `DELETE /v1/memories/{id}/` |

### Add & asynchronous extraction

By default, **Add** runs LLM-based extraction asynchronously — the API returns an event ID and the node polls until extraction finishes, then returns the resulting memories. Disable **Wait for Completion** to return immediately with the event ID, or set **Infer = false** (under Additional Fields) to store messages verbatim and return synchronously.

## Credentials

You need a Mem0 API key. Create one at [app.mem0.ai](https://app.mem0.ai) → Settings → API Keys. The key is sent as `Authorization: Token <key>`.

## Usage

This node is also **usable as a tool** by n8n's AI Agent node — attach it so an agent can "remember" and "recall" autonomously.

A typical loop:

1. **Search** memory before answering, filtered by `User ID`.
2. **Add** durable facts after a meaningful exchange.

Memory writes are asynchronous by default; allow a moment after an Add before searching for the same content.

## Resources

- [Mem0 documentation](https://docs.mem0.ai)
- [n8n community nodes documentation](https://docs.n8n.io/integrations/community-nodes/)

## License

[MIT](./LICENSE)
