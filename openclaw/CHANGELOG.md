# Changelog

All notable changes to the `@mem0/openclaw-mem0` plugin will be documented in this file.

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
