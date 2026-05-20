# docs/superpowers/

Handoff documentation for the **Claude state holistic import** feature for `mem0-plugin`.

This work was researched and designed but **never implemented** — the original owner left the company before code was written. The three files below are the complete picture so the next engineer can pick this up cold.

## Reading order

1. **`research/2026-05-19-claude-state-holistic-import-research.md`** — start here. Problem framing, complete Claude Code state inventory, competitive landscape, mem0 `infer` modes deep-dive, chunking research, and the full design decision trail with rationale.
2. **`specs/2026-05-18-claude-state-holistic-import-design.md`** — what we decided to build (architecture, components, data flow, error handling, testing strategy).
3. **`plans/2026-05-18-claude-state-holistic-import.md`** — 14-task TDD implementation plan with code in every step.

## Status

| Artifact | Status |
|---|---|
| Research doc | complete |
| Design spec | complete, approved |
| Implementation plan | complete, never executed |
| `mem0-plugin/scripts/import_claude_state.py` | not created |
| Hook block in `on_session_start.sh` | not added |
| Tests at `tests/plugin_scripts/` | not created |

## The PR this lives in

Opened as a **non-merge handoff PR**. Branch: `feat/claude-state-holistic-import-handoff`. The PR exists so the next engineer can reference the discussion, the spec, and the plan all in one place. Do not merge — close it once implementation is picked up on a fresh branch.
