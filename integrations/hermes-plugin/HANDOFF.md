# Source and compatibility notes

Imported from [NousResearch/hermes-plugin-mem0](https://github.com/NousResearch/hermes-plugin-mem0)
version 1.3.0 at commit `3fc36950b2b7c19cdd81c6de99f10d2cbed850af`.
The original native provider MIT license is retained in `LICENSE`. Generated shared core
is Apache-2.0, with its license in `LICENSE-APACHE-2.0`; package metadata records both.
This Mem0-owned port is version 1.4.0.
The source was a handoff of Hermes' bundled provider, with package-relative imports and
standalone dependency declarations; its historical authors remain in the upstream repositories.

## Changes in this port

- Generates only shared `core/message_utils.py` through `plugin-build.json`.
- Uses shared secret redaction and token-aware batching for non-empty completed-turn text.
- Preserves full message text after redaction; explicit `sync_max_chars` and the OSS default of 450
  limit chunk size instead of discarding the tail. Platform/HTTP has no default character cap.
- Attaches Hermes session IDs as top-level Mem0 `run_id` on writes; existing user recall
  remains unfiltered by session. The queue is in-memory, with bounded shutdown, logged failures,
  and no durable retry.
- Keeps `mem0`, `memory.provider`, `mem0.json`, environment fallbacks, all four tool names,
  identity precedence, SDK backends, and the three setup modes.

- Refuses OSS collection dimension mismatches without deleting existing vectors.

## Hermes contract review

Reviewed the [official memory-provider documentation](https://hermes-agent.nousresearch.com/docs/developer-guide/memory-provider-plugin),
release [v0.21.3 / v2026.9.14](https://github.com/NousResearch/hermes-agent/releases/tag/v2026.9.14)
(commit `345cd2b057a452236de401d3534b8502a7465e8d`), and main at
`c62bd9f2078a946108f1c9d9b24bf118963277ef` on September 18, 2026.

- These Hermes revisions still bundle Mem0. Bundled providers take precedence over user
  directories. See README for an isolated preview; installation alone does not replace core.
- The installer supports `owner/repo/subdirectory` and copies only that subtree. All runtime
  imports must stay within this directory or use Hermes/declared Python dependencies.
- Main installs dependencies from `[project].dependencies` and reapplies them after updates;
  v0.21.3 does not. Install dependencies explicitly in the Hermes environment on that release.
- `register(ctx)` registers a `MemoryProvider` instance. Hermes dispatches tool schemas and
  lifecycle hooks; no general-plugin hook registration is required. Background work retains
  context variables through `spawn_context_thread`, including profile and secret scope.
- Hermes supports the existing `sync_turn(user, assistant, *, session_id="")` signature.
  New optional `messages`/`turn_author` arguments are passed only to providers accepting them.
- `post_setup(hermes_home, config)` takes over setup and activation. The copied wizard already
  owns its prompt helpers; it still uses Hermes config, curses and credential utilities.
- The handoff's original notes mentioned `config_schema.py`, but neither its actual directory
  nor the checked Hermes Mem0 directory contains it. This port preserves CLI setup and does
  not claim a provider-specific dashboard configuration panel.

Older Hermes releases and live cloud/OSS services require additional validation; preserving
configuration and tool names does not imply compatibility with every historical host API.

Actual external-loader and `MemoryManager` smoke checks passed on both pinned host
revisions: initialization, tool dispatch, optional sync arguments, full-turn tail capture,
session ID forwarding and shutdown. SDK backends were mocked; no live service was contacted.

Reproduce the host smoke from the repository root (use the Hermes environment or a test
venv with its imported dependencies installed):

```bash
HERMES_SOURCE=/path/to/hermes-agent python integrations/hermes-plugin/tests/smoke_hermes.py
```

The check confirms bundled precedence, then isolates external discovery by replacing the
bundled search root with an empty temporary directory in the test process only.
