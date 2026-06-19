# Changelog

All notable changes to `@mem0/cli` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.9] — 2026-06-19

### Security

- Telemetry no longer passes the Mem0 API key to its child process via
  command-line arguments. The context is now sent over stdin, so the key is no
  longer visible in the process list (`ps`, `/proc/<pid>/cmdline`, Activity
  Monitor). Fixes #4862.

## [0.2.8] — 2026-06-01

### Security

- Pinned transitive dependencies via pnpm overrides to remediate high-severity CVEs:
  - `jws` → 4.0.1 (CVE-2025-65945)
  - `langsmith` → ^0.6.0 (CVE-2026-45134)
  - `tar-fs` → ^2.1.4 (CVE-2025-48387, CVE-2025-59343)
  - `picomatch` → ^2.3.2 (CVE-2026-33671)
  - `minimatch` → ^3.1.3 / ^5.1.8 / ^9.0.7 (CVE-2026-27903, CVE-2026-27904, CVE-2026-26996)
  - `path-to-regexp` → ^8.4.0 (CVE-2026-4926)
  - `rollup` → ^4.59.0 (CVE-2026-27606)
  - `glob` → ^10.5.0 (CVE-2025-64756)
  - `@modelcontextprotocol/sdk` → ^1.25.4 (CVE-2025-66414, CVE-2026-0621)

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
