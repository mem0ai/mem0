# Changelog

## 0.3.2

- The `handoff` skill accepts a completed Cursor JSONL transcript and its project directory. Uses the [shared handoff logic](../agent-plugin-core/CHANGELOG.md#032).
- List and resume shared resources from any supported plugin; the destination is the common local store.
- Lightened search prompts: search when prior work may help; repeat only for a specific gap.
