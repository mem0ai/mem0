# Changelog

All notable changes to the `@mem0/openclaw-mem0` plugin will be documented in this file.

## [1.0.1] - 2026-04-02

### Added
- **CD workflow**: Added continuous deployment workflow for `@mem0/openclaw-mem0` with OIDC trusted publishing ([#4672](https://github.com/mem0ai/mem0/pull/4672))
- **Plugin configuration manifest**: Added `compat` and `build` metadata to `package.json` specifying minimum gateway version and OpenClaw SDK compatibility (`>=2026.3.24-beta.2`) ([#4667](https://github.com/mem0ai/mem0/pull/4667))
- **LICENSE**: Added Apache-2.0 license file to the package ([#4667](https://github.com/mem0ai/mem0/pull/4667))

### Fixed
- **Dream gate correctness**: Fixed cheap-first ordering, session isolation, and verified completion in the dream gate memory consolidation pipeline ([#4666](https://github.com/mem0ai/mem0/pull/4666))
- **Graceful startup without API key**: Plugin now starts gracefully when no API key is configured instead of crashing on init ([#4669](https://github.com/mem0ai/mem0/pull/4669))

## [1.0.0] - 2026-04-01

### Added
- **Skills-based memory architecture**: New skill-loader and skill-based extraction pipeline with batched extraction for higher quality memory capture ([#4624](https://github.com/mem0ai/mem0/pull/4624))
- **Dream gate**: Added `dream-gate.ts` for memory consolidation and dream-cycle processing
- **Enhanced recall**: New `recall.ts` module with improved recall logic and skill-aware retrieval
- **Memory triage skill**: Domain-aware memory triage with companion domain support and recall protocol
- **Memory dream skill**: Skill for memory consolidation during idle periods
- **Plugin configuration**: Added `openclaw.plugin.json` manifest and `scripts/configure.py` setup helper

### Changed
- Extraction pipeline refactored to use skills-based architecture for more contextual and higher quality memory capture

## [0.4.1] - 2026-03-26

### Added
- **Improved extraction quality**: Enhanced noise filtering, deduplication, and better extraction instructions for higher-quality memory capture (#4302)

### Fixed
- **Credential detection in extraction**: Improved detection of credentials, API keys, and secrets in extraction instructions to prevent them from being stored as memories (#4552)
- **Standalone timestamp extraction**: Prevented extraction of standalone timestamps as memories when no meaningful content accompanies them (#4550)

## [0.4.0] - 2026-03-16

### Added
- **Non-interactive trigger filtering**: Skips recall and capture for `cron`, `heartbeat`, `automation`, and `schedule` triggers — prevents system-generated noise from polluting memory
- **Subagent hallucination prevention**: `isSubagentSession()` detects ephemeral subagent sessions and routes recall to the parent (main user) namespace instead of empty ephemeral namespaces; skips capture to prevent orphaned memories
- **Subagent-specific preamble**: Subagents receive "You are a subagent — use these memories for context but do not assume you are this user" to prevent identity assumption
- **User identity in recall preamble**: Recalled memories now include `userId` attribution for better context
- **User identity in extraction preamble**: Extraction context includes user identity and current date for accurate attribution and temporal anchoring
- **User-content guard**: Skips extraction when no meaningful user messages remain after filtering
- **Dynamic recall thresholding**: Memories scoring less than 50% of the top result are dropped to filter out the long tail of weak matches
- **SQLite resilience for OSS mode**: Init error recovery with automatic retry (history disabled) when native SQLite bindings fail under jiti
- **`disableHistory` config option**: New `oss.disableHistory` flag to explicitly skip history DB initialization
- **Updated minimum package version of mem0ai package**: Updated minimum package version of mem0ai package to ^2.3.0 to force old users to migrate to better-sqlite3
- 78 unit tests covering filtering, isolation, trigger filtering, subagent detection, and SQLite resilience

### Changed
- Auto-recall threshold raised from 0.5 to 0.6 for stricter precision during automatic injection (explicit tool searches remain at 0.5)
- Recall candidate pool increased to `topK * 2` for better filtering headroom
- Provider init promises now reset on failure, allowing retry on subsequent calls
- Relaxed extraction instructions: related facts are kept together to preserve context (removed atomic memory requirement)

### Fixed
- **Concurrent session race condition**: Lifecycle hooks (`before_agent_start`, `agent_end`) now use `ctx.sessionKey` directly from the event context instead of a shared mutable `currentSessionId` variable, preventing cross-session data leaks when multiple sessions run simultaneously

## [0.3.1] - 2026-03-12

### Added
- **Message filtering pipeline**: Multi-stage noise removal before extraction — drops heartbeats, timestamps, single-word acks, system routing metadata, compaction audit logs, and generic assistant acknowledgments
- **Broad recall for new sessions**: Short or new-session prompts trigger a secondary broad search to avoid cold-start blindness
- **Client-side threshold filtering**: Safety net that drops low-relevance results even if the API doesn't honor the threshold parameter
- **Temporal anchoring**: Extraction instructions now include current date so memories are prefixed with "As of YYYY-MM-DD, ..."
- **Summary message inclusion**: Earlier assistant messages containing work summaries are included in extraction context even if outside the recent-message window
- 55 unit tests covering filtering and isolation helpers

### Changed
- Default `searchThreshold` remains at 0.5, with client-side filtering as a safety net
- Extraction window expanded from last 10 → last 20 messages for richer context
- Rewritten custom extraction instructions: conciseness, outcome-over-intent, deduplication guidance, language preservation
- **Refactored** monolithic `index.ts` (1772 lines) into 6 focused modules: `types.ts`, `providers.ts`, `config.ts`, `filtering.ts`, `isolation.ts`, `index.ts`

### Fixed
- **README image on npmjs.com**: Changed architecture diagram from relative path to absolute GitHub URL so it renders correctly on the npm registry

## [0.3.0] - 2026-03-10

### Fixed
- Updated `mem0ai` dependency which includes the sqlite3 to better-sqlite3 migration for native binding resolution (#4270)

## [0.2.0] - 2026-03-09

### Added
- "Understanding userId" section in docs clarifying that `userId` is user-defined
- Per-agent memory isolation for multi-agent setups via `agentId`
- Regression tests for per-agent isolation helpers

### Changed
- Updated config examples to use concrete `userId` values instead of placeholders

### Fixed
- Migrated platform search to Mem0 v2 API

## [0.1.2] - 2026-02-19

### Added
- Source field for openclaw memory entries

### Fixed
- Auto-recall injection and auto-capture message drop

## [0.1.0] - 2026-02-02

### Added
- Initial release of the OpenClaw Mem0 plugin
- Platform mode (Mem0 Cloud) and open-source mode support
- Auto-recall: inject relevant memories before each turn
- Auto-capture: store facts after each turn
- Configurable `topK`, `threshold`, and `apiVersion` options
