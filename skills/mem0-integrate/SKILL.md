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
- Editor/MCP plugin glue (9 MCP tools): https://github.com/mem0ai/mem0/tree/main/mem0-plugin

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
| Target is an MCP client / editor config (Claude Code, Cursor, Codex settings) | `mem0-plugin` | Wire via MCP server URL + hooks; no SDK code usually needed. |
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

### 1. Language detection

| Signal | Track |
|---|---|
| `package.json` + TypeScript config | Node / TypeScript |
| `package.json` (no TS config) | Node / JavaScript |
| `pyproject.toml` or `requirements.txt` | Python |

Monorepo with both → ask which subdirectory to operate in, then recurse.

### 2. Repo comprehension — what does this repo do, and where is the backend?

Before any decision (product, goal, plan), understand the repo enough
to locate *where in the backend* the integration belongs. This is not
fit-surveying — the user already decided Mem0 fits. This is mechanics:
you cannot write a plan without knowing what files matter.

Read, in order, with a token budget — do not scan the whole tree:

1. `README.md` (root) + first-page of any `README_*.md` variants.
2. `CONTRIBUTING.md` / `AGENTS.md` / `CLAUDE.md` at root if present —
   these often spell out architecture and entry points.
3. `package.json` / `pyproject.toml` scripts + entry points.
4. The layout of the top two directory levels (not recursive).
5. Key config files: `docker-compose.yml`, `Dockerfile`, `Makefile`,
   `langgraph.json`, `next.config.*`, `nuxt.config.*`.

Produce `.mem0-integration/repo-summary.md`:

    # Repo comprehension

    **What this repo does:** <one paragraph in plain English. Who is
    the end user? What does the app do for them? What LLM / agent
    behavior is central? Do not list dependencies — describe behavior.>

    **Architecture at a glance:**
      - Backend: <path(s), framework, primary entry point>
      - Frontend: <path(s) if any, framework — for context only; no
        integration here>
      - Agent loop / orchestration: <LangGraph? custom? none?>
      - Existing memory/session/state systems: <name them — these are
        what step 6 Coexistence must preserve>

    **Candidate backend integration surfaces** (ranked, best first):
      1. `<backend-file>:<line_range>` — <function> — <one-sentence
         reason this is where write/read could slot in without
         replacing anything existing>
      2. ...
      3. ...

    **Not a fit here:** <list anything the skill considered but ruled
    out — e.g., "frontend chat component: client-side, excluded by
    backend-only rule"; "existing memory subsystem X: would require
    replacement, excluded by additive principle">

    **Sources read:** <list the files actually opened, with line counts,
    so reviewers can verify coverage.>

Show the user the rendered summary and ask: *"Is this understanding
correct? Which of the candidate surfaces (1, 2, 3 ...) should step 3
forward target?"*

Gate rules:

- If no backend surface is found → exit code 1. The preconditions
  should already have caught frontend-only repos; reaching this point
  means a more subtle miss (e.g., the "backend" is actually just a
  static build). Do not force a fit.
- If every candidate surface would require replacing an existing
  memory/session system → exit code 1 with the "additive principle"
  rationale. The user can manually point at a non-conflicting location
  and re-run.
- User corrections update `repo-summary.md` and re-confirm. Max 3
  rounds; beyond that, exit code 1.

The user's chosen surface index is baked into `product.json` as
`preferred_site` and referenced by steps 5 and 6.

### 3. Product selection — Platform vs OSS (ask with a recommendation)

Read the `## Identify the User's Setup` block in
`https://docs.mem0.ai/llms.txt` for the Platform-first routing rules, then
apply the heuristics below. Ask, but never blank:

- Other managed-service SDKs present (`@clerk/*`, `stripe`, `@supabase/*`,
  `openai`, `@upstash/*`, `posthog-*`) — 3+ → recommend **Platform**.
- Local-infra signals (`docker-compose.yml` with postgres / redis / qdrant /
  neo4j, ollama configs, self-hosted auth) — 2+ → recommend **OSS**.
- No strong signal → default recommendation: **Platform** (lower integration
  cost; migration later is supported).

Example:

> I see `stripe`, `@clerk/nextjs`, and `@supabase/supabase-js` — managed
> services throughout. I recommend **Mem0 Platform** (4-line integration).
> Override and use open source?

Bake the choice into the goal doc in step 5. Do not re-decide later.

### 4. API key check (env-first, then ask)

| Track | Key | Where to find |
|---|---|---|
| Platform | `MEM0_API_KEY` | https://app.mem0.ai |
| OSS (default LLM) | `OPENAI_API_KEY` | https://platform.openai.com/api-keys |

If present in env → continue.
If `MEM0_API_KEY` is missing AND the track is **Platform** → **default to Agent Mode**: run `mem0 init --agent --agent-caller <your-name> --json` (after `pip install mem0-cli` or `npm install -g @mem0/cli`), substituting your agent identity (e.g. `claude-code`, `cursor`, `codex`). If you forgot to pass `--agent-caller`, run `mem0 identify <your-name>` after init. Cache the key to `.env` (with user consent) and continue. Tell the user to claim later with `mem0 init --email <their-email>` — same key, no agent disruption.
If missing AND **CI mode** (`MEM0_INTEGRATE_CI=1`) → exit with code 2 and the name of the missing key.

Never echo key values into `trace.jsonl`. Persist to `.env` only with
explicit user consent, and append `.env` to `.gitignore` if not already there.

If the user is on OSS and wants a non-OpenAI LLM, route them to the
`components/llms/*` docs and re-run this step with the chosen provider's key.

### 5. Goal doc — the hard gate

Write `.mem0-integration/goal.md` and **require user approval before step 6**.

Template:

    # Mem0 Integration Goal

    **What gets stored:** <one sentence — user utterances? extracted
    preferences? a specific domain fact like "dietary restrictions"?>

    **When it gets retrieved:** <one sentence — on each user turn? before a
    specific tool call? at session start?>

    **Why:** <one sentence — the user-visible behavior change. "Assistant
    remembers previous orders across sessions," not "we added memory.">

    **Product:** Platform | OSS  (locked from step 3, do not change)

    **Delegated skill:** <raw URL of the published skill being used
    from "Skill delegation rules" above, or "none — custom integration
    against `skills/mem0`">.

    **Out of scope:** <anything explicitly excluded: "no graph memory,"
    "no multimodal," "no migration from existing store">

Rules:

- User must approve explicitly. If they edit the doc, reload and re-confirm.
- `goal.md` is the contract the test suite is written against. Never
  rewrite it after step 6 starts.
- Max 3 rejection rounds. On the 4th, exit with code 3 and the rejection
  notes — the integration is not well-specified enough to proceed.

### 6. Integration plan — how and where (hard gate)

Given `goal.md` is "what and why," this step produces "where and how" and
gets explicit user sign-off before any code is written.

The skill does a **scoped** read of the repo (no wide survey):

- Grep for the LLM call sites that match the goal (e.g., `openai.chat.`,
  `anthropic.messages.`, `model.generateContent`, `ChatOpenAI`, `createLLM`).
- Grep for the user-identity source (`req.user`, `session.user`, `auth()`,
  `ctx.userId`, cookies).
- Check `package.json` / `pyproject.toml` / `requirements.txt` for
  conflicts (e.g., existing `mem0ai` at a different version).

Then write `.mem0-integration/plan.md`:

    # Mem0 Integration Plan

    **Write pattern:** <one sentence — e.g., "After each assistant reply,
    call client.add([user_msg, assistant_msg], user_id=<source>).">

    **Read pattern:** <one sentence — e.g., "Before building the LLM prompt,
    call client.search(query=latest_user_msg, user_id=<source>, limit=5)
    and inject results as a system message.">

    **User identifier source:** <code path — e.g., `req.auth.userId`,
    `session.user.email`, `ctx.params.user_id`. If none, ask the user.>

    **Session scoping:**
      - user_id: <source>
      - agent_id: <static slug | null>
      - run_id:   <source | null>

    **Write call site:** `<file:line_range>` — inside `<function>`
    **Read call site:**  `<file:line_range>` — inside `<function>`

    **Dependencies to add:**
      - `<package>@<version pinned in frontmatter>`

    **Preserved behavior:** <list the existing repo behaviors that must
    keep working after this edit — e.g., "existing OpenAI streaming still
    works," "existing Redis session store still used," "existing tests
    still pass unchanged.">

    **Coexistence:** <one bullet per existing system the integration sits
    alongside. Name the files/classes. Example: "The existing
    `agents/memory/storage.py` MemoryStorage class remains untouched and
    keeps its LangGraph SummarizationEvent flow. Mem0 is added as a
    parallel long-term-facts store, in a new file, invoked only when
    MEM0_ENABLED=1 is set.">

    **Feature flag:** <the exact mechanism and the default. Required.
    Example: `env MEM0_ENABLED=1`, default unset / off; `config.mem0.enabled`,
    default false. With the flag in its default state, the repo must
    behave exactly like `main`.>

    **Sources consulted:** <minimum 2 URLs from "Canonical sources" above
    that informed this plan. At least one `docs.mem0.ai` URL and one
    delegated-skill URL. Cite the specific section or heading.>

    **E2E recipe:** <how the verification skill should drive the app
    end-to-end. Omit only if the repo is a pure library with no runnable
    entry point — in which case the E2E step will skip with a warning.>

        start:               <shell command to launch the app locally,
                              using $PORT for any network port>
        ready_probe:         <one of: url=<URL> status=<code>  /
                              log="<substring to wait for>"  /
                              sleep=<seconds, last resort>>
        compose_services:    <optional: whitespace-separated service
                              names in docker-compose.yml to start first;
                              use label mem0-e2e: "true" to mark them>
        write_call:          <command that triggers the Mem0 write path
                              exactly once; ≤ 60s runtime>
        write_async_wait_ms: <milliseconds to wait after write_call for
                              async memory flush; default 0>
        read_call:           <command that triggers the Mem0 read path,
                              typically a fresh session / new request>
        read_assert:         <substring, regex, or jsonpath=<expr>=<value>
                              that MUST appear in read_call's output for
                              the E2E to pass. Derived from goal.md's
                              "What gets stored.">

    **Rejected alternatives:** <briefly, 1–2 bullets — patterns the skill
    considered but did not pick, and why. Helps the user decide.>

Rules:

- Show the user the proposed call sites with 10 lines of context around
  each before asking for approval.
- If the skill can't find a plausible call site for either write or read,
  it exits with code 5 and asks the user to name the file(s) manually
  (this is the "no fit here" signal — don't guess).
- Max 3 rejection rounds on the plan. On the 4th, exit code 5 with the
  last plan and the user's notes.
- If the user edits `plan.md` by hand, reload and re-confirm.

`plan.md` (not `goal.md`) is the contract the subagent implements against
in step 8.

### 7. Tests first (TDD)

Main agent writes failing tests against `goal.md` in the repo's native
test framework:

| Track | Default framework |
|---|---|
| Python | `pytest` |
| TypeScript | `vitest` if detected, else `jest` |
| JavaScript | same |

Test assertion shapes must match the **canonical signatures**:

- Platform method signatures: `https://docs.mem0.ai/openapi.json`
  (request body schemas for `/v1/memories/` and `/v1/memories/search/`).
- OSS method signatures: the delegated skill named in `plan.md`
  (fetched from its raw URL) or `skills/mem0/SKILL.md` as the default.
- Do not hand-roll request shapes. If the delegated skill has an
  example block, lift it verbatim.

Minimum two test files (paths taken from `plan.md` call sites):

- `test_mem0_write.<ext>` — asserts `add()` is called at the Write call
  site with the right payload shape (Platform messages-array vs OSS string)
  and the right `user_id` source.
- `test_mem0_read.<ext>` — asserts `search()` runs before the Read call
  site and the result is wired into the LLM prompt / response path.

Tests MUST be importable with `MEM0_API_KEY` unset. This is the design
pressure that forces step 8's lazy `MemoryClient()` / `Memory()`
construction — eager module-level init hits the API on import and
breaks pre-existing test collection when the key is missing.

Run the tests. They **must fail**. If they pass before any implementation,
the tests are wrong — rewrite them.

### 8. Implementation (subagent, fresh context)

Spawn a subagent with:

- **Inputs**: the repo, `goal.md`, `plan.md`, the two test files, and
  direct URLs to: the delegated skill (from `plan.md`), the SDK source
  (pinned per `mem0_tested_versions`), `https://docs.mem0.ai/llms.txt`,
  and `https://docs.mem0.ai/openapi.json`.
- **No access** to main agent's reasoning trace or scratchpad.
- **System prompt** (verbatim):

      You are implementing a Mem0 integration for an existing repo.

      Read these first:
      - plan.md           (the mechanical contract)
      - goal.md           (the intent — do not change it)
      - the test files    (do not change them either)
      - <delegated skill raw URL from plan.md>
      - https://docs.mem0.ai/llms.txt
      - https://docs.mem0.ai/openapi.json  (Platform only)

      Constraints — all required, all enforced at review:

      1. Touch only the files named in plan.md's call sites, or add
         strictly new files.
      2. Do not remove or rename any existing symbol. Do not change
         any public signature.
      3. Do not modify any existing test.
      4. Gate every line of new Mem0 code behind the feature flag from
         plan.md. With the flag in its default state, the repo must
         behave exactly like `main` — byte-for-byte, including stdout
         and return values.
      5. Use only the <Platform | OSS> SDK surface. No new dependencies
         beyond those listed under plan.md's "Dependencies to add."
      6. Preserve everything listed under plan.md's "Preserved behavior"
         and "Coexistence."
      7. Lazy client construction. `MemoryClient()` validates the API
         key in `__init__` (it makes a network call). Never instantiate
         it at module-import time — construct on first use inside the
         request / handler path. The same rule applies to OSS `Memory()`,
         which can eagerly initialize embedding and LLM providers. Use
         a function-local singleton (`functools.lru_cache`, a module-level
         `_client = None` + getter, or DI scope) — never a top-level
         global. Eager init breaks the pre-existing test suite at
         collection time whenever the key is missing or invalid, which
         is a non-invasiveness violation.

      Implement the plan to make the new tests pass while all
      pre-existing tests continue to pass unchanged.

Subagent returns a diff. Main agent reviews against `plan.md` (the
mechanical contract) and `goal.md` (the intent):

- Approved → apply the diff, commit.
- Rejected → return with specific, actionable feedback (not "try again").
- Max 3 review loops. Beyond that → exit code 4 with the last diff and
  reviewer feedback.

### 9. Commit + handoff

Create branch `mem0-integrate/<short-goal-slug>` and commit in
**separate commits** so reviewers can cherry-pick:

1. `mem0: add gated dependency` — just the `pyproject.toml` / `package.json`
   change.
2. `mem0: add integration module` — the new file(s).
3. `mem0: wire into <call site>` — the call-site edit(s), still gated.
4. `mem0: add tests` — the new test files.

If `--no-heal` is set → print `Run /mem0-test-integration to verify.`
and exit. Otherwise proceed to step 10.

### 10. Self-healing loop (default ON; disable with `--no-heal`)

Run `/mem0-test-integration --ci` in a subprocess. If `scorecard.json`
reports `overall: pass` → done, exit 0.

Otherwise loop:

1. **Categorize the failing check** from `scorecard.json`. Route per
   category:
   - `install` / `static_checks` → dependency or import fix.
   - `unit_tests` → wiring or assertion fix.
   - `smoke_test` → API key or SDK call-shape fix.
   - `e2e_test` → recipe, flag-wiring, or integration-point fix.
   - **Pre-existing test failure (test skill exit code 7,
     `non_invasive: false` in scorecard) → STOP.** This is a
     non-invasiveness violation. Do NOT attempt to "fix" it (that
     breaks principle 3). Exit code 6 with rationale.

2. **Spawn a remediation subagent**, fresh context. Inputs:
   `plan.md`, `goal.md`, `scorecard.md`, `scorecard.json`, the last
   committed diff, and the relevant log file for the failing category
   (`test-stdout.log` / `smoke-stdout.log` / `e2e-app.log` /
   `e2e-calls.log`).

   System prompt (verbatim):

       You are fixing a failing Mem0 integration test.

       Non-negotiable constraints:
       - Do not modify test files.
       - Do not remove or rename any existing symbol or signature.
       - Do not change pre-existing behavior. The feature flag from
         plan.md must still default to OFF, and with the flag in its
         default state the repo must behave exactly like main.
       - Touch only the files named in plan.md's call sites, or add
         strictly new files.
       - Return the smallest possible diff that fixes the single
         failing check listed in scorecard.md. No drive-by cleanup.

3. **Apply the diff**; commit on the same branch with message
   `mem0-heal: <category> attempt <N>`. Do NOT amend earlier commits
   (reviewers need the heal trail).

4. **Re-run `/mem0-test-integration --ci`**. Outcomes:
   - `overall: pass` → done, exit 0.
   - Same check still failing → increment attempt counter; loop.
   - A *different* check now failing → regression. Revert the heal
     commit (`git revert HEAD --no-edit`), record the regression in
     `.mem0-integration/heal-trace.md`, exit code 6.

5. **Bounded iterations.** Default 3 attempts per failing category.
   Override with `--heal-max N` (hard cap 10). On exhaustion, exit 6
   with the full attempt trace: each diff, each scorecard, final log
   tail.

6. **Post-loop summary** written to `.mem0-integration/heal-trace.md`:
   which category failed, how many attempts, each diff's intent, final
   status, and — on success — the delta from initial scorecard to final.

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
