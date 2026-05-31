# Changelog

All notable changes to `@mem0/cli` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.7] — 2026-05-20

### Added

- `mem0 whoami` — print the active agent's `default_user_id` (the AGENTRUSH
  leaderboard identifier). Reads from local config, no network call.
- `mem0 agent-rush <add | search>` — subcommand group that wraps the new
  `/v1/agent-rush/` platform endpoints for the 7-day AGENTRUSH game. Project
  routing is implicit (resolved server-side); no flags exposed. Pretty-prints
  platform error codes into actionable hints (e.g. `agentrush_search_first`
  → "Run 3 'mem0 agent-rush search' commands before adding.").
- PII safety prompt on first `mem0 agent-rush add`. Interactive runs require
  explicit `y` to acknowledge that AGENTRUSH memories are public; the
  acknowledgement is persisted in `~/.mem0/config.json` under
  `agent_rush.acknowledged_at` so the prompt only appears once per machine.
  Non-interactive (agent) invocations surface the warning to stderr without
  blocking.
- New config schema field: `agent_rush.acknowledged_at` (ISO timestamp,
  empty until first interactive acknowledgement).

### Changed

- HTTP requests from the new agent-rush commands send `X-Mem0-Mode: agent-rush`
  in addition to the existing source headers, so platform telemetry can split
  game traffic from regular CLI usage.

## [0.2.6] and earlier

Unlogged historical releases. See git history under `cli/node/`.
