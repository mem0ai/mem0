# Changelog

## 0.3.2

- The `handoff` skill accepts a completed Codex rollout with readable active context. Uses the [shared handoff logic](../agent-plugin-core/CHANGELOG.md#032).
- List and resume shared resources from any supported plugin; the destination is the common local store.
- Read current Codex rollouts containing harness snapshots and usage records; only conversation records enter the handoff.
- Lightened search prompts: search when prior work may help; repeat only for a specific gap.
