---
name: mem0-integrate
description: >
  Integrate Mem0 into an existing repository using a goal-driven, TDD pipeline.
  Detects the repo's language automatically and asks the user to pick between
  Mem0 Platform (managed) and Mem0 Open Source (self-hosted). Writes failing
  tests before any implementation. Produces a local feature branch plus
  `.mem0-integration/` artifacts consumed by the paired verification skill.
  TRIGGER when: user says "integrate mem0", "add mem0 to this repo", "wire
  mem0 into <repo>", or asks how to add memory to an existing project.
  DO NOT TRIGGER when: the user wants general SDK usage (use skill:mem0),
  CLI usage (use skill:mem0-cli), or Vercel AI SDK (use skill:mem0-vercel-ai-sdk).
  After success, invoke skill:mem0-test-integration to verify in the same
  workspace (loose coupling).
license: Apache-2.0
metadata:
  author: mem0ai
  version: "0.1.0"
  category: ai-memory
  tags: "memory, integration, tdd, platform, oss"
  mem0_tested_versions: "mem0ai (PyPI) >=2.0.0,<3.0.0; mem0ai (npm) >=3.0.0,<4.0.0"
---

# mem0-integrate

Wire Mem0 into an existing repo with a goal-driven, test-first pipeline.
Pairs with `mem0-test-integration` for verification.

## Canonical sources (fetch before deciding anything)

The skill MUST `WebFetch` these URLs before step 3 and cite them in
`plan.md`. They are the ground truth — do not rely on ambient knowledge
of the Mem0 API.

### Agent-ready docs
- Scope-tagged docs index: https://docs.mem0.ai/llms.txt
- Full docs (single file, deep dives): https://docs.mem0.ai/llms-full.txt
- OpenAPI spec (Platform REST, machine-readable): https://docs.mem0.ai/openapi.json
- Hosted MCP server: https://mcp.mem0.ai (requires Platform API key)
- Integrations index: https://docs.mem0.ai/integrations

### Published Mem0 skills — delegate; do not reimplement
Prefer these over writing your own call-site patterns. Each is a
standalone `SKILL.md` with triggers, examples, and version-pinned code.

- SDK (Python + TS, Platform + OSS): https://raw.githubusercontent.com/mem0ai/mem0/main/skills/mem0/SKILL.md
- CLI: https://raw.githubusercontent.com/mem0ai/mem0/main/skills/mem0-cli/SKILL.md
- Vercel AI SDK: https://raw.githubusercontent.com/mem0ai/mem0/main/skills/mem0-vercel-ai-sdk/SKILL.md
- Editor/MCP plugin glue (9 MCP tools): https://github.com/mem0ai/mem0/tree/main/integrations/mem0-plugin

### SDK source (read when docs are ambiguous)
Public repo. Cross-check against the `mem0_tested_versions` range in this
skill's frontmatter if the `main` branch has moved past a major.

- Repo root: https://github.com/mem0ai/mem0
- Python SDK: https://github.com/mem0ai/mem0/tree/main/mem0
- TypeScript SDK: https://github.com/mem0ai/mem0/tree/main/mem0-ts

### Quickstarts (for bootstrapping unfamiliar stacks)
- Platform: https://docs.mem0.ai/platform/quickstart
- OSS Python: https://docs.mem0.ai/open-source/python-quickstart
- OSS Node: https://docs.mem0.ai/open-source/node-quickstart
- Platform vs OSS comparison: https://docs.mem0.ai/platform/platform-vs-oss

## Integration principles (non-negotiable)

The true goal of this skill is to produce a **PR the maintainers can accept
without argument**. That rules out anything invasive.

1. **Additive, not replacing.** If the target repo already has a memory
   system, a session store, a user-context layer, or anything named
   `Memory` / `memory_*`, Mem0 sits **alongside** it, not in place of it.
   The existing system keeps working unchanged.
2. **Opt-in by default.** Gate all new Mem0 code behind a feature flag
   (env var like `MEM0_ENABLED=1`, a config key, or a strategy selector).
   With the flag unset, behavior is the repo's original behavior,
   byte-for-byte.
3. **No breakage.** No removed exports, no renamed public functions,
   no changed method signatures, no modified existing tests, no changed
   behavior of existing tests. All pre-existing tests must pass unchanged
   both with the flag set and unset.
4. **Minimal dependency surface.** Add `mem0ai` (plus any deps the
   delegated skill requires) and nothing else. No new vector stores, no
   graph databases, no provider SDKs the repo does not already use.
5. **Separable commits.** Code, tests, and config/docs land in separate
   commits so reviewers can cherry-pick.
6. **The null hypothesis wins.** If no additive, gated fit exists after
   step 6 (plan), exit with code 1 and a rationale. A bad PR is worse
   than no PR.
7. **Backend only.** Mem0 integration lives in server-side code. API keys,
   memory scope, and user-identity resolution are not safe client-side.
   If the repo has both backend and frontend, the call sites live in
   backend files. Frontend-only repos are rejected at preconditions.

Enforced at four gates: **preconditions** (reject frontend-only repos
and repos where additive fit is impossible), **step 2 comprehension**
(confirm a backend exists and name candidate surfaces), **step 6 plan
review** (reject plans that mutate existing exports or name client-side
call sites), and **step 10 self-healing loop** (refuse to "fix" principle
violations — surface them instead).

## Skill delegation rules

Before writing any code, check whether a published skill already covers
the target stack. If yes, delegate — copy its call-site pattern into
`plan.md` and into the tests; do not paraphrase.

| Detected in target repo | Delegate to | Why |
|---|---|---|
| `@ai-sdk/*` + `ai` in `package.json` | `skills/mem0-vercel-ai-sdk` | Integration is via `createMem0` provider wrapper, not raw `MemoryClient`. |
| CLI-only repo (Typer, Commander, Click, Cobra) with no LLM call sites | `skills/mem0-cli` | Call sites are command handlers, not model wrappers. Consider whether mem0 actually fits first. |
| Target is an MCP client / editor config (Claude Code, Cursor, Codex settings) | `integrations/mem0-plugin` | Wire via MCP server URL + hooks; no SDK code usually needed. |
| Any other Python or TS repo with an LLM call site | `skills/mem0` | Default SDK integration path. |

Record the delegated skill's raw URL in `plan.md` under a
**"Delegated skill:"** field. The test writer in step 7 and the
implementation subagent in step 8 both read this field.

## Preconditions

Refuse to start unless ALL of the following are true:

- Current working directory is inside a git repository with a clean index
  (no uncommitted changes). Protects the user's work — every edit lands on
  a feature branch, not on top of in-progress changes.
- Repo has a detectable language (`package.json` / `pyproject.toml` /
  `requirements.txt`). No language → exit cleanly with a written rationale.
- Repo has a **backend**. Detected by: a `backend/` or `server/` or `api/`
  directory; a Python package with FastAPI/Flask/Django/Starlette; a Node
  package with Express/Fastify/Koa/NestJS/Next-API-routes; an agent-loop
  framework (LangGraph, LangChain, LlamaIndex, Agno). Frontend-only repos
  (pure React/Vue/Svelte SPAs, static sites, mobile-only) → exit with
  code 1 and a rationale. Mem0 is not installed client-side.
- The user has already decided Mem0 fits this repo. This skill does NOT
  survey the codebase to justify fit — bring a concrete goal. (Step 2
  *does* read the repo to understand what it does and locate backend
  integration surfaces; that is mechanics, not fit-justification.)

Exit with a written rationale if any precondition fails. Do not try to
"make it work anyway."

## Pipeline

Ten steps. Full mechanics, document templates, and gate rules are in
[`references/pipeline.md`](references/pipeline.md). Read that file when you
start executing a step; the summary below is only for routing.

| # | Step | Gate |
|---|---|---|
| 1 | **Language detection.** `package.json` / `pyproject.toml` / `requirements.txt`. Monorepo, ask which subdirectory. | |
| 2 | **Repo comprehension.** Budgeted read of README, contributor docs, entry points, top two directory levels. Produces `repo-summary.md` with ranked backend surfaces. | User confirms the summary and picks a surface. No backend surface, exit 1. |
| 3 | **Product selection.** Platform vs OSS, recommended from dependency signals, never asked blank. | Locked into `goal.md`, never re-decided. |
| 4 | **API key check.** `MEM0_API_KEY` (Platform) or `OPENAI_API_KEY` (OSS). Missing on Platform, default to Agent Mode via `mem0 init --agent`. | CI mode with a missing key, exit 2. |
| 5 | **Goal doc.** `goal.md`: what gets stored, when it is retrieved, why, product, delegated skill, out of scope. | **Hard gate.** Explicit approval required. 3 rejections, exit 3. |
| 6 | **Integration plan.** Scoped grep for call sites and identity source. `plan.md`: write/read patterns, scoping, call sites, dependencies, preserved behavior, coexistence, feature flag, sources, E2E recipe. | **Hard gate.** No plausible additive call site or 3 rejections, exit 5. |
| 7 | **Tests first.** Failing write and read tests in the repo's native framework, assertion shapes lifted from the canonical signatures. Must be importable with `MEM0_API_KEY` unset. | Tests must fail. If they pass, they are wrong. |
| 8 | **Implementation.** Fresh-context subagent, prompt in [`references/subagent-prompts.md`](references/subagent-prompts.md), returns a diff reviewed against `plan.md` and `goal.md`. | 3 review loops, then exit 4. |
| 9 | **Commit and handoff.** Branch `mem0-integrate/<slug>`, four separable commits: dependency, module, wiring, tests. | `--no-heal` stops here. |
| 10 | **Self-healing loop.** Runs `/mem0-test-integration --ci`, categorizes the failure, spawns a bounded remediation subagent, reverts on regression. | Pre-existing test failure, **stop**, exit 6. Never "fix" it. |

## Artifacts (all under `.mem0-integration/`)

| File | Purpose | Retention |
|---|---|---|
| `repo-summary.md` | Repo comprehension + candidate backend surfaces (step 2). | Keep across runs. |
| `goal.md` | Approved intent. Never rewritten after step 6. | Keep across runs. |
| `plan.md` | Approved mechanics (where, how, call sites, preserved behavior). | Keep across runs. |
| `trace.jsonl` | Every tool call, decision, and subagent exchange this run. | Overwritten per run. |
| `diff.patch` | The committed integration as a reviewable patch. | Overwritten per run. |
| `heal-trace.md` | Per-attempt record of the self-healing loop (step 10). | Overwritten per run. |
| `product.json` | `{"product": "platform"\|"oss", "language": "...", "mem0_version": "...", "write_site": "file:line", "read_site": "file:line", "feature_flag": "MEM0_ENABLED"}` — consumed by the verification skill. | Overwritten per run. |

`.mem0-integration/` is added to `.gitignore` on first run. Nothing is
written outside this directory and the repo's source tree.

## Modes

| Mode | Trigger | Behavior |
|---|---|---|
| Interactive (default) | TTY present, `MEM0_INTEGRATE_CI` unset | Asks for keys, confirms goal doc, shows recommendations. |
| CI | `MEM0_INTEGRATE_CI=1` | Requires keys in env, requires `--product`, auto-approves goal doc from `goal.md` if present, fails fast otherwise. |

## Invocation

    /mem0-integrate                            # interactive, heal ON
    /mem0-integrate --no-heal                  # stop after commit; manual verify
    /mem0-integrate --heal-max 5               # cap heal attempts per category (default 3)
    /mem0-integrate --product platform         # skip the product ask
    /mem0-integrate --product oss
    /mem0-integrate --ci                       # non-interactive (for test harness)

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success. Feature branch committed; verification skill ready to run. |
| 1 | Precondition failed (dirty repo, no detectable language, etc.). |
| 2 | Missing env key in CI mode. |
| 3 | Goal doc rejected 3+ times — integration is not well-specified. |
| 4 | Subagent review loop did not converge in 3 rounds. |
| 5 | Integration plan rejected 3+ times, or no plausible additive call site found. |
| 6 | Self-healing loop did not converge, detected a non-invasiveness violation, or a pre-existing test failed. |

## Explicitly out of scope

- Surveying the repo for fit points. Humans decide where Mem0 helps before
  invoking this skill.
- Replacing any existing memory / session / state system. Always additive
  and feature-flagged; see "Integration principles."
- Modifying pre-existing tests, even to "fix" them under self-heal. Tests
  that fail after integration with the flag unset are a non-invasiveness
  violation, not a bug to patch.
- Deciding Platform vs OSS silently. Always ask with a recommendation.
- Switching branches, pushing, or opening PRs. Commits locally and stops
  (or enters the heal loop, still local).
- Data migration between stores. Point user at `migration/oss-to-platform`
  docs if they ask.
- Provider selection beyond the default LLM for OSS. If they need a custom
  LLM / embedder / vector store, route to `components/*` docs and re-run
  step 4 with the new key.
