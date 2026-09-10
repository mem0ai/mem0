# Changelog

## 0.3.1

- `/mem0-handoff` uses the current OpenCode session API and completed tool results. Uses the [shared handoff logic](../agent-plugin-core/CHANGELOG.md#032).
- List and resume shared resources from any supported plugin; the destination is the common local store.
- Lightened search prompts: search when prior work may help; repeat only for a specific gap.
