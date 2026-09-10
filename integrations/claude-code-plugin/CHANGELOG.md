# Changelog

## 0.3.2

- `/mem0:handoff codex` reads the current Claude session before model invocation. Uses the [shared handoff logic](../agent-plugin-core/CHANGELOG.md#032).
- Lightened search prompts: search when prior work may help; repeat only for a specific gap.
