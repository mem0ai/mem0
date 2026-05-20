# Claude State Holistic Import — Research & Findings

**Date:** 2026-05-19
**Status:** Handoff document. Original owner left the company; this consolidates everything we learned so the next engineer can pick this up cold.
**Reads as:** problem statement → discovery → competitive landscape → mem0 platform behavior → design choices → why we settled where we did → recommended next steps.

---

## Table of contents

1. [Why this exists](#1-why-this-exists)
2. [Complete Claude Code state inventory (on disk)](#2-complete-claude-code-state-inventory-on-disk)
3. [Current `mem0-plugin` capabilities (what's already there)](#3-current-mem0-plugin-capabilities-whats-already-there)
4. [Competitive landscape](#4-competitive-landscape)
5. [`mem0`'s `infer=True` vs `infer=False` deep-dive](#5-mem0s-infertrue-vs-inferfalse-deep-dive)
6. [Chunking research (2026 benchmarks)](#6-chunking-research-2026-benchmarks)
7. [The design decision trail — what we considered and why we picked what we picked](#7-the-design-decision-trail--what-we-considered-and-why-we-picked-what-we-picked)
8. [Open questions / known unknowns](#8-open-questions--known-unknowns)
9. [Recommended next steps for new owner](#9-recommended-next-steps-for-new-owner)
10. [Source materials](#10-source-materials)

---

## 1. Why this exists

**The problem in one sentence:** When a user installs `mem0-plugin`, mem0 starts empty even though Claude Code has been quietly accumulating their CLAUDE.md instructions, auto-memory, and subagent learnings on disk for months.

The existing plugin hooks capture *live* state from the moment of install forward:
- `session_state` (PreCompact + Stop hooks)
- `compact_summary` (SessionStart-compact hook)
- Agent-authored `add_memory` calls (the Stop / TaskCompleted nudge rubric)

None of these backfill the user's prior state. A heavy Claude Code user can have 15+ project memories, hundreds of CLAUDE.md rules, and dozens of subagent feedback files that are all invisible to mem0 until they manually re-state every one of them.

**The differentiation play:** No other plugin in the space does this systematically. We confirmed this by surveying claude-mem, Memory Store Plugin, Serena, Cipher, and OpenCode (details in §4). Memory Store Plugin is the closest — it auto-syncs CLAUDE.md continuously — but doesn't do a bulk holistic backfill or touch MEMORY.md. Cloud-backed cross-machine recall of Claude's accumulated knowledge is an open lane.

**The strategic asks this answers:**
- "I switched machines and Claude doesn't remember the conventions I taught it on my old laptop."
- "Why does mem0 know nothing about my project even though Claude Code clearly does?"
- "I'd switch from MEMORY.md to mem0 but I'd lose six months of accumulated learnings."

---

## 2. Complete Claude Code state inventory (on disk)

We crawled the official Claude Code docs (https://code.claude.com/docs/en/memory) and the live filesystem to build this. Anything not listed here was deliberately excluded from scope (transient state, harness internals, secrets).

### User-authored ("how I want Claude to behave")

| Source | Path | Loaded into | Notes |
|---|---|---|---|
| Managed policy CLAUDE.md (org-wide) | macOS: `/Library/Application Support/ClaudeCode/CLAUDE.md` <br> Linux/WSL: `/etc/claude-code/CLAUDE.md` <br> Windows: `C:\Program Files\ClaudeCode\CLAUDE.md` | every session | rarely populated; exists in regulated environments |
| User CLAUDE.md | `~/.claude/CLAUDE.md` | every session | user-global rules across all projects |
| Project CLAUDE.md | `./CLAUDE.md` or `./.claude/CLAUDE.md` | every session in/under the dir | team-shared via VCS; also picked up walking up parent dirs |
| `CLAUDE.local.md` | `./CLAUDE.local.md` (gitignored) | every session | personal project-specific overrides |
| Nested CLAUDE.md | subdirectory CLAUDE.md | loaded on demand when Claude reads files in that subtree | not all loaded at startup |
| `@imports` | inline `@path/to/file` syntax | follows from any CLAUDE.md | recursive up to 5 hops; relative resolved against importer; non-`.md` extensions allowed |
| Path-scoped rules | `./.claude/rules/**/*.md` + `~/.claude/rules/*.md` | by path glob, or always if no `paths:` frontmatter | per-language / per-subdir guidance |
| AGENTS.md cross-tool config | `./AGENTS.md` | not loaded by Claude Code directly | usually imported via `@AGENTS.md` from CLAUDE.md, or symlinked |

### Claude-authored ("what Claude figured out") — Claude Code v2.1.59+, on by default

| Source | Path | Loaded into | Notes |
|---|---|---|---|
| Auto-memory index | `~/.claude/projects/<encoded-path>/memory/MEMORY.md` | every session, first 200 lines or 25 KB | one per repo; encoded path = `-Users-<user>-<repo-dir>-...` |
| Auto-memory topic files | `~/.claude/projects/<encoded-path>/memory/*.md` (other than MEMORY.md) | on demand | Claude moves detail out of MEMORY.md to keep the index short |
| Subagent auto-memory | `~/.claude/agent-memory/<agent>/MEMORY.md` + topic files | when that subagent runs | per subagent (e.g., `meta-reviewer`, `eks-perf-finops-tuner`) |
| Custom auto-memory dir | wherever `autoMemoryDirectory` in `~/.claude/settings.json` points | same | only accepted from policy / user / `--settings` flag; not project settings |

### Lower-signal / transient (excluded from scope)

| Source | Path | Why excluded |
|---|---|---|
| Shell history | `~/.claude/history.jsonl` (3.8 MB on the original owner's machine) | too noisy; not knowledge |
| Sessions | `~/.claude/sessions/*.json` | transient working state |
| Tasks | `~/.claude/tasks/<uuid>/` | task harness internals |
| Todos | `~/.claude/todos/*/` | transient |
| File-history | `~/.claude/file-history/*` | binary state |
| Plans | `~/.claude/plans/` | typically empty; transient |
| `session-env` | `~/.claude/session-env/` | environment snapshots |
| `paste-cache` | `~/.claude/paste-cache/` | UX cache |
| `settings.json` | `~/.claude/settings.json` | config, not memory; secrets risk |

### Already covered by mem0 hooks (don't re-import)

| Captured by | When | metadata.type |
|---|---|---|
| `on_pre_compact.py --source=pre-compaction` | PreCompact hook fires | `session_state` |
| `on_pre_compact.py --source=session-end` | Stop hook (background) | `session_state` |
| `capture_compact_summary.py` | SessionStart-compact (background) | `compact_summary` |
| Agent voluntary `add_memory` | Stop / TaskCompleted rubric prompts the agent | `task_learning` / `decision` / `anti_pattern` / `user_preference` |

So mem0 streams *live* state forward but has no eyes on what's already on disk. That's the gap.

### What the original owner's disk actually showed (May 2026)

For grounding — this is one heavy user's footprint:

```
~/.claude/CLAUDE.md                                  (0 B — empty)
~/.claude/projects/                                  15 project dirs
~/.claude/projects/-Users-mragankshekhar-mem0-platform/memory/
    ├── MEMORY.md                                    (2.4 KB)
    ├── graph-lambda-details.md                      (2.3 KB)
    ├── prod_db_topology.md                          (1.7 KB)
    └── project_team_gabe_departed.md                (1.2 KB)
~/.claude/agent-memory/meta-reviewer/                19 feedback files (35 KB total)
~/.claude/agent-memory/eks-perf-finops-tuner/        (also populated)
```

Sample content from one of the MEMORY.md files (anonymized concept-only):
```
## Critical Rules
- NEVER use raw docker/docker compose commands. Always use `make` targets.
- NEVER auto-commit. User handles all git commits manually.
- NEVER touch, clean, delete, or modify prod data/resources. EVER.

## Sandbox E2E Tests
- `make run_e2e_sandbox` runs E2E tests against local sandbox
- Django's APPEND_SLASH causes DELETE→GET redirect when URLs lack trailing slashes
- Categorization pipeline: lambda → SQS → categorization worker → OpenAI → Postgres
...
```

This is exactly the kind of content that should be searchable from mem0 cross-machine.

---

## 3. Current `mem0-plugin` capabilities (what's already there)

Read `mem0-plugin/README.md` for the user-facing pitch. The implementation details that matter for the import design:

### Hooks (per `mem0-plugin/hooks/hooks.json`)

| Hook | Script | What it does |
|---|---|---|
| `SessionStart` (matcher `startup|resume|compact`) | `on_session_start.sh` | Emits identity line + a context-bootstrap rubric. Branches by `source`. On `compact`, also spawns `capture_compact_summary.py` in background. |
| `PreToolUse` (matcher `Write|Edit`) | `block_memory_write.sh` | **Blocks writes to `MEMORY.md` and `.claude/memory/*`** — forces all memory operations through mem0 MCP. This is a *strong* opinion: mem0 wants to be the single source of truth, not coexist with native auto-memory. |
| `PreCompact` | `on_pre_compact.sh` → `on_pre_compact.py --source=pre-compaction` | Captures the transcript tail as a `session_state` memory before context is lost. |
| `Stop` | `on_stop.sh` → reminder text + `on_pre_compact.py --source=session-end` | Reminds the agent to `add_memory` learnings, then captures session_state as a safety net. |
| `UserPromptSubmit` | `on_user_prompt.sh` | Injects a "decide whether memory context helps" rubric — the agent decides; the hook never pre-searches. |
| `TaskCompleted` | `on_task_completed.sh` | Reminder rubric: extract decisions / anti_patterns / conventions / task_learnings via `add_memory`. |

### Cross-client parity

| Hook config | Used by |
|---|---|
| `mem0-plugin/hooks/hooks.json` | Claude Code |
| `mem0-plugin/hooks/cursor-hooks.json` | Cursor (sessionStart, preToolUse, preCompact, stop, beforeSubmitPrompt) |
| `mem0-plugin/hooks/codex-hooks.json` | Codex (SessionStart startup|resume, UserPromptSubmit, Stop) — installed via `install_codex_hooks.py` because Codex has no plugin auto-wire |

**All three clients call the same bash entry points (`on_session_start.sh`, etc.).** Extending those scripts propagates to every client for free.

### Identity (`scripts/_identity.sh` and `scripts/_identity.py`)

```
1. $MEM0_USER_ID env var (explicit override)
2. $USER, else "default"
```

Note: There was a brief experiment where the user_id was derived from the API key (`6a1597c6 fix(plugin): drop API-key-derived user_id, restore $USER fallback`). That was reverted. The `$USER` fallback is the deliberate convention.

### Reused REST pattern

`on_pre_compact.py` and `capture_compact_summary.py` both:
- Use stdlib `urllib.request` (no `requests` dependency)
- POST to `https://api.mem0.ai/v1/memories/`
- Auth: `Authorization: Token {api_key}` header
- Log to stderr, plus optional `~/.mem0/hooks.log` when `MEM0_DEBUG=1`
- Always `sys.exit(0)` so they never break the hook
- Use `infer=False` (because the content is already structured)

**The import script must follow this exact pattern.**

### Skills

- `mem0-plugin/skills/mem0/SKILL.md` — full SDK guide (Python + TS + framework integrations)
- `mem0-plugin/skills/mem0-mcp/SKILL.md` — **the metadata vocabulary** the import script must use: `decision`, `anti_pattern`, `user_preference`, `convention`, `task_learning`. Plus the v2 filter syntax (root must be AND/OR/NOT, metadata nested not dotted).

### MCP server

- Remote MCP at `https://mcp.mem0.ai/mcp/`, auth via `Authorization: Token ${MEM0_API_KEY}`
- 9 tools: `add_memory`, `search_memories`, `get_memories`, `get_memory`, `update_memory`, `delete_memory`, `delete_all_memories`, `delete_entities`, `list_entities`

---

## 4. Competitive landscape

Surveyed May 2026. Each entry: what they do, what they import, gaps.

### claude-mem (`thedotmack/claude-mem`)
- **Pitch:** "Persistent context across sessions for every agent."
- **Approach:** Captures tool outputs (1–10 K tokens) live, compresses to ~500-token semantic observations using Claude's Agent SDK. Typed schema: `decision`, `bugfix`, `feature`, `refactor`, `discovery`, `change`. Local SQLite + 3-tier retrieval (index → timeline → full details).
- **Backfill behavior:** None. Live-capture only.
- **Differs from us:** local-only; pays LLM cost at every tool call; no cloud sync.
- **Lesson:** their typed schema and ~500-token observation size validates our heading-based ~50-500-token chunk target as the right granularity for code-context memory.

### Memory Store Plugin (`julep-ai/memory-store-plugin`)
- **Pitch:** "Tracks dev flow, captures session context, analyzes git, maintains team knowledge across projects."
- **Approach:** Hook-based continuous sync via SessionStart / PreToolUse / SessionEnd. Reads CLAUDE.md files and **anchor comments** (`<!-- AUTH-FLOW -->`-style markers embedded in code). Internal queue `.memory-queue.jsonl` batched on every user message.
- **Backfill behavior:** **Closest to ours** — it auto-syncs CLAUDE.md on first run. But it doesn't touch MEMORY.md, agent-memory, or the @import graph.
- **Differs from us:** continuous sync (not one-shot), no opt-in/opt-out, no LLM extraction.
- **Lesson:** their continuous-sync model is plausible but more invasive; the one-shot model with explicit consent is the right v1 for us.

### Serena (`oraios/serena`)
- **Pitch:** "IDE for your agent" — semantic code retrieval and editing at the symbol level.
- **Approach:** Writes its own `.serena/memories/*.md` for project understanding. Read via `read_memory` MCP tool.
- **Backfill behavior:** None — creates its own files, doesn't ingest Claude's.
- **Differs from us:** local file-based memory in a parallel namespace; no semantic search beyond file content.

### Cipher / ByteRover (`campfirein/byterover-cli`, formerly `cipher`)
- **Pitch:** "Portable memory layer for autonomous coding agents."
- **Approach:** Dual memory architecture — System 1 (programming concepts, business logic, past interactions) + System 2 (deliberate step-by-step reasoning). Workspace Memory for team sharing. Multi-IDE: Cursor, Windsurf, Claude Desktop, Claude Code, Gemini CLI, Kiro, VS Code, Roo Code, Trae, Amp Code, Warp.
- **Backfill behavior:** Maps project structure on first connection; detects patterns; saves locally. Not a deliberate CLAUDE.md / MEMORY.md backfill.
- **Differs from us:** local-first with optional cloud; positions itself as a competitor to mem0 itself, not a complement.

### OpenCode plugin (`kuitos/opencode-claude-memory`)
- **Pitch:** "OpenCode plugin for Claude Code memory: persistent local Markdown memory shared with Claude Code, zero config, no migration."
- **Approach:** Stores memory as local Markdown in the same dirs Claude Code already uses. "Auto-dream" periodic background consolidation.
- **Backfill behavior:** "Zero config, no migration" because it reuses the same files Claude already writes. Functionally not an import — it's a different memory backend.
- **Differs from us:** doubles down on local; no cloud sync; no programmatic search beyond grep.

### Anthropic native (Claude Code v2.1.59+)
- **Pitch:** Built into Claude Code itself. Free.
- **Approach:** Writes `~/.claude/projects/<proj>/memory/MEMORY.md` automatically as Claude works. On by default.
- **Backfill behavior:** N/A — it IS the local store.
- **Differs from us:** local only, no cross-machine, no semantic search beyond loading the first 200 lines / 25 KB into context every session.

### The gap, restated

| Capability | claude-mem | Memory Store | Serena | Cipher | OpenCode | Anthropic native | **mem0 + this import** |
|---|---|---|---|---|---|---|---|
| Cloud-backed cross-machine memory | ✗ | ✗ | ✗ | optional | ✗ | ✗ | ✓ |
| Semantic search over accumulated memory | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ | ✓ |
| Live capture of new state | ✓ | ✓ | partial | ✓ | ✓ | ✓ | ✓ (already shipped) |
| **One-shot backfill of existing on-disk state** | ✗ | partial (CLAUDE.md only) | ✗ | partial | ✗ | N/A | **✓ (this feature)** |
| Ingest MEMORY.md auto-memory | ✗ | ✗ | ✗ | ✗ | ✗ | N/A | **✓ (this feature)** |
| Ingest subagent memory | ✗ | ✗ | ✗ | ✗ | ✗ | N/A | **✓ (this feature)** |
| Follow `@imports` recursively | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ (loader) | **✓ (this feature)** |

This is the wedge. Nobody else is doing this.

---

## 5. `mem0`'s `infer=True` vs `infer=False` deep-dive

From the source (`mem0/memory/main.py`) and platform docs (https://docs.mem0.ai/platform/features/direct-import).

### `infer=True` (default)

```python
client.add(messages, user_id=..., metadata=..., infer=True)
```

- An LLM extracts key facts from `messages`.
- The LLM decides ADD / UPDATE / DELETE relative to existing memories for the same `user_id`.
- **Auto-dedup** server-side.
- Cost: LLM tokens per call (chargeable on hosted platform).
- Latency: hundreds of ms to a couple of seconds per call.
- Output: one or many memories per input; the response's `results` array carries IDs + event types.

### `infer=False` (Direct Import)

```python
client.add(messages, user_id=..., metadata=..., infer=False)
```

- **Skips the inference pipeline entirely.**
- Only messages with `role: "user"` are stored. Assistant / system roles are dropped.
- **No dedup.** Re-sending the same content creates a duplicate.
- No LLM cost.
- Sub-100ms typical.
- Output: one memory per input message.

### When each is right

| Content type | Recommendation | Why |
|---|---|---|
| Raw conversation transcripts | `infer=True` | Need atomic fact extraction; lots of noise |
| Pre-curated structured content | `infer=False` | Already atomic; LLM extraction wastes tokens |
| Bulk import of pre-existing markdown | **Either, depends on goal** | See decision section |
| Security guardrails (must store verbatim) | `infer=False` | Wording matters |

### What the existing plugin does

`on_pre_compact.py` and `capture_compact_summary.py` both use `infer=False` because they already produce structured summaries. That's the plugin convention.

For the import: the original design intent was `infer=False` (preserve user wording, lean on heading-based chunks for granularity, use content-hash for idempotency). **The owner pivoted to `infer=True` by default** late in design (see decision §7) because they wanted server-side dedup and search quality over wording preservation. `--no-infer` was kept as an opt-out for power users who want raw fidelity.

---

## 6. Chunking research (2026 benchmarks)

### What we found

- **Recursive 512-token chunking** scored 69% retrieval accuracy in a February 2026 Vecta benchmark across 50 academic papers — winner among basic methods (https://www.firecrawl.dev/blog/best-chunking-strategies-rag).
- **Document-based chunking** (heading-aware) is the optimal strategy for well-structured markdown — exactly the content we have (https://learn.microsoft.com/en-us/azure/search/search-how-to-semantic-chunking).
- **Semantic chunking** (embedding-based boundary detection) adds up to 9% recall improvement, but at LLM-call latency and cost (https://weaviate.io/blog/chunking-strategies-for-rag).
- claude-mem's choice of ~500-token semantic observations validates the same sweet spot from a different angle.

### Why heading-based chunking won for our content

- CLAUDE.md and MEMORY.md are already well-structured markdown with H2/H3 sections.
- Heading boundaries are *semantic* boundaries (the user wrote them that way).
- Heading-based chunking is the highest-recall strategy for structured docs at zero LLM cost.
- The chunks naturally land in the 50–500-token range that matches the Vecta benchmark winner.

### Edge cases the chunker has to handle

1. **Oversized sections** (>2000 chars) — descend to H3 inside that section.
2. **Tiny sections** (<200 chars) — merge with the next sibling to avoid one-liner memories.
3. **Code fences containing `## `** — must not be split mid-fence. The implementation masks heading-like lines inside fences with a length-preserving substitution (so chunk offsets stay aligned with the original text).

---

## 7. The design decision trail — what we considered and why we picked what we picked

This section is the journey, not just the destination. Most decisions had three or four credible options; the choice often turned on "what's the minimum viable surface."

### Q1: What's in v1 scope?

| Option | Choice | Why |
|---|---|---|
| Instructions only (CLAUDE.md + rules) | rejected | misses the meat of "holistic" — Claude's actual learnings |
| Instructions + project auto-memory | rejected | misses subagent memory (rich for power users) |
| **Instructions + ALL auto-memory** | **picked** | the actual "holistic" picture; one heavy user already had 19 meta-reviewer feedback files |
| Everything including transient state | rejected | history.jsonl / sessions / todos are noise |

### Q2: How does the user trigger the import?

| Option | Choice | Why |
|---|---|---|
| Slash command only | rejected | not scriptable; needs an active session |
| CLI subcommand only | rejected | less discoverable inside Claude Code |
| Both + auto-prompt on first run | initially chosen | best discoverability |
| **SessionStart hook nudge + plain Python script (no new CLI subcommand)** | **picked** | the owner's "use existing tools, no new moving parts" pivot. The bash hook does discovery and emits a one-time prompt; the Python script does the work; no Typer subcommand surface needed |

### Q3: Auto-import on install, or always require explicit consent?

| Option | Choice | Why |
|---|---|---|
| Fully automatic on plugin install | rejected | uploads user data to cloud without explicit consent — compliance risk |
| Hook does the import in background | rejected | same consent problem |
| **Hook detects + nudges; user / agent explicitly invokes the script** | **picked** | consent is explicit per run; hook stays cheap (just `[ -f marker ]`) |

### Q4: How do files become mem0 memories?

| Option | Choice | Why |
|---|---|---|
| Raw, one memory per file | rejected | granularity too coarse — 5 KB blobs hurt search |
| Heading-chunked, `infer=False` (initially recommended) | almost picked | preserves wording, cheap |
| **Heading-chunked, `infer=True` default + `--no-infer` opt-out** | **picked** | the owner prioritized server-side dedup + search quality over wording preservation. `--no-infer` preserved for raw-fidelity needs |
| Always LLM-extracted (`infer=True`) without chunking | rejected | mem0's LLM may miss facts in long inputs; chunking improves extraction |
| Hybrid by file size | rejected | branching logic the user can't predict |

The chunker is heading-based regardless; the toggle is purely whether the chunks get LLM extraction on the server.

### Q5: Identity scoping in mem0

| Option | Choice | Why |
|---|---|---|
| **`user_id` only, source info in metadata** | **picked** | matches existing plugin convention; metadata filters give you the same query power |
| `user_id` + `run_id` per project | rejected | diverges from convention for marginal benefit |
| `user_id` + `run_id` always | rejected | synthetic run_ids for things that aren't runs |

### Q6: Architecture — how minimal can the surface be?

| Option | Choice | Why |
|---|---|---|
| Library + CLI subcommand + hook | rejected | three new things |
| Library + hook | rejected | still introduces a new top-level package surface |
| **One new Python script + one new hook block + one marker file** | **picked** | mirrors `on_pre_compact.py` exactly; reuses every existing convention; zero new packages, zero new deps |

### Q7: Dedup model

| Option | Choice | Why |
|---|---|---|
| Server-side via `infer=True` only | rejected (alone) | doesn't help client-side: would re-upload everything every run |
| Content-hash in marker only | rejected (alone) | doesn't help if user runs `--reset` or two machines with same content |
| **Both: marker for client-side idempotency, `infer=True` for server-side dedup** | **picked** | belt-and-suspenders |

### Q8: Re-prompting after first run

| Option | Choice | Why |
|---|---|---|
| Hook nudges every session if any file is newer than marker | rejected | noisy for power users editing CLAUDE.md often |
| **Hook silent after marker exists; users re-run script manually** | **picked v1** | simple. Staleness re-prompting is a v2 enhancement |

---

## 8. Open questions / known unknowns

These are explicit non-decisions — the new owner gets to make these calls when they pick this up.

1. **Continuous sync** — should v2 add a watcher that re-imports when MEMORY.md changes? Or rely on the existing live-capture (`session_state`) to cover ongoing changes? Open.
2. **Slash command `/mem0 import`** — convenience wrapper inside Claude Code. The agent can already invoke the Python script via Bash, but a slash command surfaces it in the `/` discovery panel. Cheap to add later.
3. **Staleness re-prompting** — should the SessionStart hook re-nudge if marker is >N days old or if `find` shows files newer than `last_run_at`? Adds ~50 ms per SessionStart but improves long-term discovery.
4. **Codex / Cursor parity smoke test** — `codex-hooks.json` and `cursor-hooks.json` already reference the same `on_session_start.sh`. The Python script is client-agnostic. The implementation plan suggests verifying via a smoke run on each client — that wasn't done because implementation never happened.
5. **Sensitive content scrubbing** — CLAUDE.md often contains internal URLs, sandbox API keys, sometimes secrets. The current design relies on user judgment (same risk profile as the live-capture hooks already in production). A secrets-detection pre-pass would be a good v2.
6. **Public AGENTRUSH memories interaction** — recent commit `4ca9d13c feat(cli): warn about public AGENTRUSH memories before first add` introduced a confirmation flow for public memories. Imported memories should probably respect that warning if any of the source files end up in a public scope. Out of scope for v1.
7. **What happens when the user changes machines?** — currently the marker file is per-machine. If a user runs the import on laptop A, then later runs it on laptop B, B will re-upload everything (different marker). mem0's server-side dedup with `infer=True` mostly catches this, but the marker doesn't sync. Probably fine. Worth verifying.
8. **What about `.claude/skills` and `.claude/agents` directories?** — these contain skill / agent definitions. They're not really "memory" per se but they're context the user has curated. Out of scope for v1 but worth a thought.

---

## 9. Recommended next steps for new owner

If you're picking this up:

1. **Read the spec first.** `docs/superpowers/specs/2026-05-18-claude-state-holistic-import-design.md` — 330 lines, internally consistent, all decisions justified.
2. **Read the plan.** `docs/superpowers/plans/2026-05-18-claude-state-holistic-import.md` — 14 tasks, TDD-flavored but the test discipline is optional.
3. **Decide if `infer=True` default is still right.** The owner made the call late in design and the implementation never ran against a real fixture. If the LLM cost on a typical user (15 projects × ~5 files × ~10 chunks each = ~750 chunks → ~750 LLM extractions on the platform side) feels too high, revert to `infer=False` default. The chunker, marker, and dispatcher all work either way — only the default value of one CLI flag changes.
4. **Start at Task 1 of the plan.** Scaffold the script + test harness. Then go in order — the dependency chain is genuine (chunker depends on Source, dispatcher depends on chunker + tagger, orchestrator depends on dispatcher + marker).
5. **If you skip the tests** (which is fine — the design isn't TDD-dependent), at minimum write the integration test (Task 12). It's the cheapest insurance against the chunker / tagger / dispatcher mismatching in ways unit tests would catch piecemeal.
6. **Manual smoke before merging.** Run against a throwaway mem0 account with `MEM0_USER_ID=mem0_import_smoke_$DATE`. Confirm chunks appear in the dashboard with the right `metadata.source_type` and `metadata.type` tags. Verify search filters in `mem0-plugin/skills/mem0-mcp/SKILL.md` actually return what you expect.
7. **Consider whether to ship this in `0.2.0`** or **bundle into a bigger plugin release**. The plugin already advanced to 0.2.0 on the `feat/claude-code-plugin` branch with Tier 1/2 features. Decide if holistic import fits that release or warrants 0.3.0.

### Quick-start command sequence

```bash
# Set up
git checkout main && git pull
git checkout -b feat/claude-state-holistic-import

# Read the docs
$EDITOR docs/superpowers/specs/2026-05-18-claude-state-holistic-import-design.md
$EDITOR docs/superpowers/plans/2026-05-18-claude-state-holistic-import.md

# Implement Task 1: scaffold
mkdir -p tests/plugin_scripts
touch tests/plugin_scripts/__init__.py
# ... follow plan ...

# Run tests as you go
pytest tests/plugin_scripts/ -v

# Manual smoke
export MEM0_USER_ID="mem0_import_smoke_$(date +%Y%m%d)"
python3 mem0-plugin/scripts/import_claude_state.py --dry-run

# Commit per task. PR back to main.
```

### Estimated effort

| Phase | Estimate |
|---|---|
| Read spec + plan + this doc | 1 hour |
| Tasks 1–11 (script + tests through CLI) | 1–2 days for a Python engineer comfortable with stdlib |
| Task 12 (integration test) | 2–4 hours |
| Task 13 (hook block) | 30 minutes |
| Task 14 (docs + version bump) | 30 minutes |
| Manual smoke + iteration | 2–4 hours |
| **Total** | **2–3 working days** |

---

## 10. Source materials

### Anthropic docs
- [How Claude remembers your project](https://code.claude.com/docs/en/memory) — CLAUDE.md hierarchy, auto-memory, `.claude/rules/`, `@imports`, settings
- [Claude Code Plugin Marketplace: Complete Guide (2026)](https://www.agensi.io/learn/claude-code-plugin-marketplace-guide)
- [Discover and install prebuilt plugins through marketplaces](https://code.claude.com/docs/en/discover-plugins)
- [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official)

### mem0 docs and source
- [Direct Import — Mem0](https://docs.mem0.ai/platform/features/direct-import) — `infer=False` semantics
- [Mem0 Platform docs](https://docs.mem0.ai)
- `mem0/memory/main.py` — `add()` source, infer kwarg
- `mem0-plugin/skills/mem0-mcp/SKILL.md` — metadata vocab + v2 filter syntax
- `mem0-plugin/scripts/on_pre_compact.py` — the pattern reference for the new script
- `mem0-plugin/scripts/_identity.py` — user_id resolution

### Competitive plugins
- [claude-mem (thedotmack/claude-mem)](https://github.com/thedotmack/claude-mem)
- [Claude-Mem Guide — DataCamp](https://www.datacamp.com/tutorial/claude-mem-guide)
- [Memory Store Plugin (julep-ai/memory-store-plugin)](https://github.com/julep-ai/memory-store-plugin)
- [Serena (oraios/serena)](https://github.com/oraios/serena)
- [Cipher / ByteRover CLI (campfirein/byterover-cli)](https://github.com/campfirein/cipher)
- [OpenCode plugin (kuitos/opencode-claude-memory)](https://github.com/kuitos/opencode-claude-memory)
- [Hands-on: Build a Memory Layer for Claude Code & Gemini CLI](https://aiengineering.beehiiv.com/p/hands-on-make-coding-agents-10x-smarter-1)

### Chunking research
- [Best Chunking Strategies for RAG (2026)](https://www.firecrawl.dev/blog/best-chunking-strategies-rag) — Vecta Feb 2026 benchmark
- [Chunk and Vectorize by Document Layout — Azure AI Search](https://learn.microsoft.com/en-us/azure/search/search-how-to-semantic-chunking)
- [Chunking Strategies to Improve LLM RAG Pipeline Performance — Weaviate](https://weaviate.io/blog/chunking-strategies-for-rag)
- [Text Chunking Strategies for RAG: A Comprehensive Guide (March 2026)](https://atlassc.net/2026/03/30/text-chunking-strategies-for-rag)
- [RAG Chunking Strategies — Latenode](https://latenode.com/blog/ai-frameworks-technical-infrastructure/rag-retrieval-augmented-generation/rag-chunking-strategies-complete-guide-to-document-splitting-for-better-retrieval)

### Related Anthropic features and posts
- [Auto memory in Claude Code (v2.1.59+) — community context](https://www.shareuhack.com/en/posts/claude-memory-feature-guide-2026)
- [Import and export your memory from Claude — Help Center](https://support.claude.com/en/articles/12123587-import-and-export-your-memory-from-claude) — note: this is chat memory, not Claude Code memory
- [Claude Code Memory System Explained — Milvus](https://milvus.io/blog/claude-code-memory-memsearch.md)
- [The Complete Guide to CLAUDE.md — Bijit Ghosh, Medium](https://medium.com/@bijit211987/the-complete-guide-to-claude-md-memory-rules-loading-and-cross-tool-compression-97cc12ed037b)

### Internal references
- `docs/superpowers/specs/2026-05-18-claude-state-holistic-import-design.md` — the spec
- `docs/superpowers/plans/2026-05-18-claude-state-holistic-import.md` — the implementation plan
- `mem0-plugin/README.md` — current plugin docs
- `mem0-plugin/CHANGELOG.md` — release history
- `CLAUDE.md` (this repo's root) — project-level conventions
