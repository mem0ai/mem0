# @mem0/n8n-nodes-mem0

This is an n8n community node that lets you use [Mem0](https://mem0.ai) — the memory layer for AI agents — in your n8n workflows.

Mem0 gives your agents long-term memory: add memories from conversations, then search and recall them across sessions.

[n8n](https://n8n.io) is a [fair-code licensed](https://docs.n8n.io/reference/license/) workflow automation platform.

[Installation](#installation) · [Operations](#operations) · [Credentials](#credentials) · [Usage](#usage) · [Resources](#resources)

## Installation

Follow the [community nodes installation guide](https://docs.n8n.io/integrations/community-nodes/installation/) and install `@mem0/n8n-nodes-mem0`.

## Operations

The **Memory** resource supports:

| Operation | Description | Endpoint |
| --- | --- | --- |
| **Add** | Extract and store memories from messages | `POST /v3/memories/add/` |
| **Search** | Semantic search over stored memories | `POST /v3/memories/search/` |
| **Get Many** | List stored memories (single page, or **Return All**) | `POST /v3/memories/` |
| **Get** | Retrieve a single memory by ID | `GET /v1/memories/{id}/` |
| **Update** | Update a memory's text or metadata | `PUT /v1/memories/{id}/` |
| **Delete** | Delete a single memory by ID | `DELETE /v1/memories/{id}/` |

### Add & asynchronous extraction

By default, **Add** runs LLM-based extraction asynchronously: the API returns an event ID and the node polls until extraction finishes, then returns the resulting memories.

Two independent controls:

- **Wait for Completion** (on by default) decides whether the node polls. Turn it off to return immediately with the event ID.
- **Infer** (on by default, under Additional Fields) decides whether the API runs LLM extraction at all. Turn it off to store the messages verbatim.

**Custom Instructions**, **Custom Categories**, **Includes**, and **Excludes** (also under Additional Fields) steer what extraction keeps for that call. **Agent ID**, **App ID**, and **Run ID** live there too, and scope the memory alongside (or instead of) **User ID**.

### Entity filters on Search & Get Many

Both take **User ID**, **Agent ID**, **App ID**, and **Run ID**, and at least one is required — the API rejects a query with no entity scope, and the node fails with a clear message before calling it.

Supplying several combines them with **OR**, giving the union of those scopes. Mem0 indexes each entity separately, so an `AND` across `user_id` and `agent_id` matches nothing even for a memory written with both. To narrow instead of widen, run one operation per entity id.

## Credentials

You need a Mem0 API key. Create one at [app.mem0.ai](https://app.mem0.ai) → Settings → API Keys. The key is sent as `Authorization: Token <key>`.

## Usage

This node is also **usable as a tool** by n8n's AI Agent node — attach it so an agent can "remember" and "recall" autonomously.

A typical loop:

1. **Search** memory before answering, filtered by `User ID` (or `Agent ID` / `App ID` / `Run ID`).
2. **Add** durable facts after a meaningful exchange.

Memory writes are asynchronous by default; allow a moment after an Add before searching for the same content.

## Telemetry

This node sends no third-party telemetry. Its API requests are tagged with `source: "N8N"` so Mem0 can see aggregate usage of the integration. No separate analytics service is contacted and nothing else is collected.

## Resources

- [Mem0 documentation](https://docs.mem0.ai)
- [n8n community nodes documentation](https://docs.n8n.io/integrations/community-nodes/)

## License

[Apache-2.0](./LICENSE)
