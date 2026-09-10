# Changelog

## 0.3.1

- An explicit `mem0_handoff` call uses the current DeepSeek session’s derived messages; invoke it outside nested code mode. Uses the [shared handoff logic](../agent-plugin-core/CHANGELOG.md#032).
- List and resume shared resources from any supported plugin; the destination is the common local store.
- Lightened search prompts: search when prior work may help; repeat only for a specific gap.
