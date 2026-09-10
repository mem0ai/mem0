# Changelog

## 0.3.1

- `/mem0-handoff` uses Pi’s selected branch and native compaction context (Node.js 22.19+). Uses the [shared handoff logic](../agent-plugin-core/CHANGELOG.md#032).
- List and resume shared resources from any supported plugin; the destination is the common local store.
- Lightened search prompts: search when prior work may help; repeat only for a specific gap.
