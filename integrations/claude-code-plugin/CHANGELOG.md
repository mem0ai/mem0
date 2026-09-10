# Changelog

## 0.3.2

- `/mem0:handoff` reads the current Claude session before model invocation. Uses the [shared handoff logic](../agent-plugin-core/CHANGELOG.md#032).
- List and resume shared resources from any supported plugin; the destination is the common local store.
- Match the handoff command’s quoted path in its shell permission rule, including installation paths with spaces.
- Lightened search prompts: search when prior work may help; repeat only for a specific gap.
