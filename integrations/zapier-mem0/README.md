# Zapier integration for Mem0

A [Zapier](https://zapier.com) integration for [Mem0](https://mem0.ai) — the memory layer for AI agents. Add, search, list, and delete long-term memories from any Zap.

Built with the [Zapier Platform CLI](https://docs.zapier.com/platform/quickstart/cli-tutorial).

## Actions

| Type | Name | Endpoint |
| --- | --- | --- |
| Create | **Add Memory** | `POST /v3/memories/add/` |
| Create | **Delete Memory** | `DELETE /v1/memories/{id}/` |
| Search | **Search Memories** | `POST /v3/memories/search/` |
| Search | **Get Memories** | `POST /v3/memories/` |

**Add Memory** runs LLM extraction asynchronously and returns immediately with an event ID by default. Turn on **Wait for Completion** to have the action poll until extraction finishes and return the resulting memories — note that extraction can take longer than Zapier allows a single step to run, and a timeout there does **not** mean the add failed (it typically still completes server-side). Set **Infer = false** to store the message verbatim instead of extracting.

**Get Memories** returns one page at a time; use the **Page** and **Limit** fields to page through larger result sets.

## Authentication

Custom (API key) auth. Provide a Mem0 API key from [app.mem0.ai](https://app.mem0.ai) → Settings → API Keys. It is sent as `Authorization: Token <key>`.

## Development

Written in TypeScript; the app compiles to `dist/` (Zapier runs the compiled JS).

```bash
pnpm install
pnpm build                      # compile src/ → dist/
pnpm test:unit                  # offline unit tests (mocked, no network)
MEM0_API_KEY=m0-... pnpm test   # unit + live E2E against api.mem0.ai
```

Anonymous usage telemetry is sent to Mem0; opt out with `MEM0_TELEMETRY=false`.

To deploy (maintainers): `pnpm build && zapier push`.

## License

MIT
