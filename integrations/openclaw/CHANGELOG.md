# Changelog

## 1.1.1

- `/mem0-handoff` uses the current session’s trusted transcript path. Uses the [shared handoff logic](../agent-plugin-core/CHANGELOG.md#032).
- List and resume shared resources from any supported plugin; the destination is the common local store.
- Lightened search prompts: search when prior work may help; repeat only for a specific gap.
