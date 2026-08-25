# Engine / harness contract

The plugin is split in two:

| Directory | Role | Harness-specific? |
|-----------|------|-------------------|
| `core/` | The engine: evidence storage, checkpointing, extraction, search, MCP server, CLI | No |
| `adapters/claude/` | Harness glue: maps Claude Code lifecycle events onto engine calls | Yes |

A new per-harness plugin starts by copying `core/` unchanged and writing a new
adapter beside `adapters/claude/`. **`core/` must not learn about a harness.**
If a change to `core/` needs an `if harness == ...`, it belongs in the adapter.

## What the engine gives an adapter

Import surface from `core/memory_core.py`, everything the Claude adapter uses:

| Symbol | Purpose |
|--------|---------|
| `EvidenceStore` | SQLite handle; open one per hook invocation, always `close()` it |
| `api_key()`, `cache_plugin_api_key()` | Resolve and cache the Mem0 key |
| `data_dir()` | Root for the database, pending packets, and logs |
| `record_session_start`, `record_user_prompt`, `record_tool`, `record_stop` | Capture evidence |
| `record_sidekick_start`, `record_sidekick_stop` | Capture sub-agent lifecycle |
| `checkpoint_session` | Synchronous extraction, used only when `MEM0_CODE_SYNC_FLUSH=1` |
| `search_memories`, `format_context` | Retrieval and rendering |

`core/flush_worker.py` is the detached background worker. `core/mcp_server.py`
serves the single `search_memories` tool. `core/memory_cli.py` backs the skills.
None of the three are Claude-specific.

## What an adapter must do

1. **Translate one harness event into one engine call.** Nine Claude Code events
   map onto eight adapter actions, listed in `hooks/hooks.json`.
2. **Pass a `hook_input` dict** parsed from stdin. The engine reads only these
   keys, all optional:
   `agent_id`, `agent_transcript_path`, `agent_type`, `cwd`, `duration_ms`,
   `error`, `last_assistant_message`, `model`, `prompt`, `session_id`, `source`,
   `task`, `task_outcome`, `tool_input`, `tool_name`, `tool_response`,
   `transcript_path`.
   A harness that names a field differently renames it in the adapter, not in the engine.
3. **Never block the coding agent.** Every adapter entry point exits 0 even on an
   unhandled exception. See the top-level guard at the bottom of
   `adapters/claude/hook.py`.
4. **Keep remote calls out of the hot path.** Hooks write to SQLite and return.
   Anything touching the network is handed to `flush_worker.py` through a pending
   packet, so extraction survives the session closing.
5. **Detach the worker on every platform it ships to.** See
   `detached_process_kwargs()`; `start_new_session` is a silent no-op on Windows.
6. **Honour the pause switch.** Check `store.is_paused()` before capturing anything.

## Scope rules

- `resolve_repo()` collapses every subdirectory to the git root, so a monorepo is
  one `app_id` today.
- `repo_for_session()` pins that scope at session start so all hooks in one
  session agree. Adapters with a session id must use it rather than
  `resolve_repo()` directly.
- `core/mcp_server.py` is the documented exception: an MCP server is a separate
  stateless process and is never given a session id, so it calls `resolve_repo()`.
  The two disagree only if the user moves into a different git repository
  mid-session.
- Scope must live in **metadata**, never in a changed `app_id`. Changing `app_id`
  makes it a different entity and memory superseding stops working.
- Never filter on `app_id: "*"`. The wildcard matches only non-null values, so
  memories written without an `app_id` become unreachable. Use
  `{"app_id": {"in": [...]}}`.

## The contract tests

`tests/test_memory_core.py` is the contract. A new adapter keeps these passing
verbatim, substituting only its own adapter import:

| Test | Guarantees |
|------|------------|
| `test_offline_hook_flow_records_evidence_without_remote_writes` | Capture works with no API key |
| `test_paused_hook_does_not_capture` | The pause switch is honoured |
| `test_post_tool_hook_is_silent_after_recording_output` | Hooks stay quiet on stdout |
| `test_launch_handoff_resolves_flush_worker_under_core` | Adapter resolves the worker path into `core/` |
| `test_launch_handoff_always_requests_detachment` | The worker is always detached |
| `test_flush_worker_detaches_on_windows_as_well_as_posix` | Detachment is not POSIX-only |
| `test_pending_recovery_is_capped_and_leaves_the_rest_for_next_session` | Recovery cannot stampede |
| `test_pending_recovery_drops_packets_past_the_expiry_window` | Dead packets are collected |
| `test_repo_scope_matches_the_previous_plugin_mapping` | Scope stays compatible across versions |
| `test_non_git_session_keeps_starting_project_scope_after_nested_commands` | Session scope is pinned |
| `test_secrets_are_redacted_from_commands_and_results` | No credential reaches the Platform |
| `test_plugin_entrypoints_share_explicit_claude_data_dir` | Every entry point agrees on the data dir |
| `test_version_is_single_sourced` | Version matches both marketplace manifests |

Run them with `python3 -m pytest tests/ -q` from the plugin root. Pure stdlib
plus pytest, nothing to install.
