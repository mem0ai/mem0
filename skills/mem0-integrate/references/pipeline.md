# Pipeline mechanics

Full step-by-step for `mem0-integrate`. Read this when you are executing a
step. The one-line-per-step overview and every non-negotiable rule live in
`../SKILL.md`, which is loaded on every run; this file is loaded on demand.

Verbatim subagent system prompts for steps 8 and 10 are in
[`subagent-prompts.md`](subagent-prompts.md).

## 1. Language detection

| Signal | Track |
|---|---|
| `package.json` + TypeScript config | Node / TypeScript |
| `package.json` (no TS config) | Node / JavaScript |
| `pyproject.toml` or `requirements.txt` | Python |

Monorepo with both, ask which subdirectory to operate in, then recurse.

## 2. Repo comprehension: what does this repo do, and where is the backend?

Before any decision (product, goal, plan), understand the repo enough to
locate *where in the backend* the integration belongs. This is not
fit-surveying, the user already decided Mem0 fits. This is mechanics: you
cannot write a plan without knowing what files matter.

Read, in order, with a token budget. Do not scan the whole tree.

1. `README.md` (root) plus the first page of any `README_*.md` variants.
2. `CONTRIBUTING.md` / `AGENTS.md` / `CLAUDE.md` at root if present. These
   often spell out architecture and entry points.
3. `package.json` / `pyproject.toml` scripts and entry points.
4. The layout of the top two directory levels, not recursive.
5. Key config files: `docker-compose.yml`, `Dockerfile`, `Makefile`,
   `langgraph.json`, `next.config.*`, `nuxt.config.*`.

Produce `.mem0-integration/repo-summary.md`:

    # Repo comprehension

    **What this repo does:** <one paragraph in plain English. Who is
    the end user? What does the app do for them? What LLM / agent
    behavior is central? Do not list dependencies, describe behavior.>

    **Architecture at a glance:**
      - Backend: <path(s), framework, primary entry point>
      - Frontend: <path(s) if any, framework, for context only; no
        integration here>
      - Agent loop / orchestration: <LangGraph? custom? none?>
      - Existing memory/session/state systems: <name them, these are
        what step 6 Coexistence must preserve>

    **Candidate backend integration surfaces** (ranked, best first):
      1. `<backend-file>:<line_range>` <function> <one-sentence
         reason this is where write/read could slot in without
         replacing anything existing>
      2. ...
      3. ...

    **Not a fit here:** <list anything the skill considered but ruled
    out, e.g. "frontend chat component: client-side, excluded by
    backend-only rule"; "existing memory subsystem X: would require
    replacement, excluded by additive principle">

    **Sources read:** <list the files actually opened, with line counts,
    so reviewers can verify coverage.>

Show the user the rendered summary and ask: *"Is this understanding correct?
Which of the candidate surfaces (1, 2, 3 ...) should step 3 forward target?"*

Gate rules:

- No backend surface found, exit code 1. Preconditions should already have
  caught frontend-only repos; reaching this point means a subtler miss (for
  example the "backend" is actually just a static build). Do not force a fit.
- Every candidate surface would require replacing an existing memory or
  session system, exit code 1 with the additive-principle rationale. The user
  can point at a non-conflicting location manually and re-run.
- User corrections update `repo-summary.md` and re-confirm. Max 3 rounds,
  beyond that exit code 1.

The user's chosen surface index is baked into `product.json` as
`preferred_site` and referenced by steps 5 and 6.

## 3. Product selection: Platform vs OSS

Read the `## Identify the User's Setup` block in
`https://docs.mem0.ai/llms.txt` for the Platform-first routing rules, then
apply the heuristics below. Ask, but never blank.

- Other managed-service SDKs present (`@clerk/*`, `stripe`, `@supabase/*`,
  `openai`, `@upstash/*`, `posthog-*`), 3 or more, recommend **Platform**.
- Local-infra signals (`docker-compose.yml` with postgres / redis / qdrant /
  neo4j, ollama configs, self-hosted auth), 2 or more, recommend **OSS**.
- No strong signal, default recommendation **Platform**: lower integration
  cost, and migration later is supported.

Example:

> I see `stripe`, `@clerk/nextjs`, and `@supabase/supabase-js`, managed
> services throughout. I recommend **Mem0 Platform** (4-line integration).
> Override and use open source?

Bake the choice into the goal doc in step 5. Do not re-decide later.

## 4. API key check (env first, then ask)

| Track | Key | Where to find |
|---|---|---|
| Platform | `MEM0_API_KEY` | https://app.mem0.ai |
| OSS (default LLM) | `OPENAI_API_KEY` | https://platform.openai.com/api-keys |

Present in env, continue.

`MEM0_API_KEY` missing and the track is **Platform**, **default to Agent
Mode**: run `mem0 init --agent --agent-caller <your-name> --json` (after
`pip install mem0-cli` or `npm install -g @mem0/cli`), substituting your agent
identity such as `claude-code`, `cursor`, `codex`. If you forgot
`--agent-caller`, run `mem0 identify <your-name>` after init. Cache the key to
`.env` with user consent and continue. Tell the user to claim it later with
`mem0 init --email <their-email>`: same key, no agent disruption.

Missing and **CI mode** (`MEM0_INTEGRATE_CI=1`), exit code 2 with the name of
the missing key.

Never echo key values into `trace.jsonl`. Persist to `.env` only with explicit
user consent, and append `.env` to `.gitignore` if it is not there already.

If the user is on OSS and wants a non-OpenAI LLM, route them to the
`components/llms/*` docs and re-run this step with the chosen provider's key.

## 5. Goal doc, the hard gate

Write `.mem0-integration/goal.md` and **require user approval before step 6**.

    # Mem0 Integration Goal

    **What gets stored:** <one sentence. User utterances? Extracted
    preferences? A specific domain fact like "dietary restrictions"?>

    **When it gets retrieved:** <one sentence. On each user turn? Before a
    specific tool call? At session start?>

    **Why:** <one sentence, the user-visible behavior change. "Assistant
    remembers previous orders across sessions," not "we added memory.">

    **Product:** Platform | OSS  (locked from step 3, do not change)

    **Delegated skill:** <raw URL of the published skill being used
    from the delegation table in SKILL.md, or "none, custom integration
    against `skills/mem0`">.

    **Out of scope:** <anything explicitly excluded: "no graph memory,"
    "no multimodal," "no migration from existing store">

Rules:

- The user must approve explicitly. If they edit the doc, reload and
  re-confirm.
- `goal.md` is the contract the test suite is written against. Never rewrite
  it after step 6 starts.
- Max 3 rejection rounds. On the 4th, exit code 3 with the rejection notes:
  the integration is not well-specified enough to proceed.

## 6. Integration plan, where and how (hard gate)

`goal.md` is what and why. This step produces where and how, and gets explicit
sign-off before any code is written.

Do a **scoped** read of the repo, no wide survey:

- Grep for the LLM call sites that match the goal (`openai.chat.`,
  `anthropic.messages.`, `model.generateContent`, `ChatOpenAI`, `createLLM`).
- Grep for the user-identity source (`req.user`, `session.user`, `auth()`,
  `ctx.userId`, cookies).
- Check `package.json` / `pyproject.toml` / `requirements.txt` for conflicts,
  for example an existing `mem0ai` at a different version.

Then write `.mem0-integration/plan.md`:

    # Mem0 Integration Plan

    **Write pattern:** <one sentence, e.g. "After each assistant reply,
    call client.add([user_msg, assistant_msg], user_id=<source>).">

    **Read pattern:** <one sentence, e.g. "Before building the LLM prompt,
    call client.search(query=latest_user_msg, user_id=<source>, limit=5)
    and inject results as a system message.">

    **User identifier source:** <code path, e.g. `req.auth.userId`,
    `session.user.email`, `ctx.params.user_id`. If none, ask the user.>

    **Session scoping:**
      - user_id: <source>
      - agent_id: <static slug | null>
      - run_id:   <source | null>

    **Write call site:** `<file:line_range>` inside `<function>`
    **Read call site:**  `<file:line_range>` inside `<function>`

    **Dependencies to add:**
      - `<package>@<version pinned in frontmatter>`

    **Preserved behavior:** <list the existing repo behaviors that must
    keep working after this edit, e.g. "existing OpenAI streaming still
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

    **Sources consulted:** <minimum 2 URLs from "Canonical sources" in
    SKILL.md that informed this plan. At least one `docs.mem0.ai` URL and
    one delegated-skill URL. Cite the specific section or heading.>

    **E2E recipe:** <how the verification skill should drive the app
    end-to-end. Omit only if the repo is a pure library with no runnable
    entry point, in which case the E2E step skips with a warning.>

        start:               <shell command to launch the app locally,
                              using $PORT for any network port>
        ready_probe:         <one of: url=<URL> status=<code>  /
                              log="<substring to wait for>"  /
                              sleep=<seconds, last resort>>
        compose_services:    <optional: whitespace-separated service
                              names in docker-compose.yml to start first;
                              use label mem0-e2e: "true" to mark them>
        write_call:          <command that triggers the Mem0 write path
                              exactly once; 60s runtime or less>
        write_async_wait_ms: <milliseconds to wait after write_call for
                              async memory flush; default 0>
        read_call:           <command that triggers the Mem0 read path,
                              typically a fresh session / new request>
        read_assert:         <substring, regex, or jsonpath=<expr>=<value>
                              that MUST appear in read_call's output for
                              the E2E to pass. Derived from goal.md's
                              "What gets stored.">

    **Rejected alternatives:** <briefly, 1 or 2 bullets. Patterns the skill
    considered but did not pick, and why. Helps the user decide.>

Rules:

- Show the user the proposed call sites with 10 lines of context around each
  before asking for approval.
- If no plausible call site exists for either write or read, exit code 5 and
  ask the user to name the files manually. That is the "no fit here" signal,
  do not guess.
- Max 3 rejection rounds on the plan. On the 4th, exit code 5 with the last
  plan and the user's notes.
- If the user edits `plan.md` by hand, reload and re-confirm.

`plan.md`, not `goal.md`, is the contract the subagent implements against in
step 8.

## 7. Tests first (TDD)

The main agent writes failing tests against `goal.md` in the repo's native
test framework:

| Track | Default framework |
|---|---|
| Python | `pytest` |
| TypeScript | `vitest` if detected, else `jest` |
| JavaScript | same |

Test assertion shapes must match the **canonical signatures**:

- Platform method signatures: `https://docs.mem0.ai/openapi.json`, the request
  body schemas for `/v1/memories/` and `/v1/memories/search/`.
- OSS method signatures: the delegated skill named in `plan.md` (fetched from
  its raw URL), or `skills/mem0/SKILL.md` as the default.
- Do not hand-roll request shapes. If the delegated skill has an example
  block, lift it verbatim.

Minimum two test files, paths taken from `plan.md` call sites:

- `test_mem0_write.<ext>` asserts `add()` is called at the write call site
  with the right payload shape (Platform messages-array vs OSS string) and the
  right `user_id` source.
- `test_mem0_read.<ext>` asserts `search()` runs before the read call site and
  the result is wired into the LLM prompt or response path.

Tests MUST be importable with `MEM0_API_KEY` unset. This is the design
pressure that forces step 8's lazy `MemoryClient()` / `Memory()` construction:
eager module-level init hits the API on import and breaks pre-existing test
collection when the key is missing.

Run the tests. They **must fail**. If they pass before any implementation, the
tests are wrong. Rewrite them.

## 8. Implementation (subagent, fresh context)

Spawn a subagent with:

- **Inputs**: the repo, `goal.md`, `plan.md`, the two test files, and direct
  URLs to the delegated skill (from `plan.md`), the SDK source (pinned per
  `mem0_tested_versions`), `https://docs.mem0.ai/llms.txt`, and
  `https://docs.mem0.ai/openapi.json`.
- **No access** to the main agent's reasoning trace or scratchpad.
- **System prompt**: use the implementation prompt in
  [`subagent-prompts.md`](subagent-prompts.md) verbatim.

The subagent returns a diff. The main agent reviews it against `plan.md` (the
mechanical contract) and `goal.md` (the intent):

- Approved, apply the diff and commit.
- Rejected, return with specific actionable feedback, not "try again."
- Max 3 review loops. Beyond that, exit code 4 with the last diff and the
  reviewer feedback.

## 9. Commit and handoff

Create branch `mem0-integrate/<short-goal-slug>` and commit in **separate
commits** so reviewers can cherry-pick:

1. `mem0: add gated dependency`, just the `pyproject.toml` / `package.json`
   change.
2. `mem0: add integration module`, the new files.
3. `mem0: wire into <call site>`, the call-site edits, still gated.
4. `mem0: add tests`, the new test files.

With `--no-heal`, print `Run /mem0-test-integration to verify.` and exit.
Otherwise proceed to step 10.

## 10. Self-healing loop (default ON, disable with `--no-heal`)

Run `/mem0-test-integration --ci` in a subprocess. If `scorecard.json` reports
`overall: pass`, done, exit 0.

Otherwise loop:

1. **Categorize the failing check** from `scorecard.json` and route:
   - `install` / `static_checks`, dependency or import fix.
   - `unit_tests`, wiring or assertion fix.
   - `smoke_test`, API key or SDK call-shape fix.
   - `e2e_test`, recipe, flag-wiring, or integration-point fix.
   - **Pre-existing test failure** (test skill exit code 7,
     `non_invasive: false` in the scorecard), **STOP**. This is a
     non-invasiveness violation. Do NOT attempt to fix it, that breaks
     principle 3. Exit code 6 with a rationale.

2. **Spawn a remediation subagent** with fresh context. Inputs: `plan.md`,
   `goal.md`, `scorecard.md`, `scorecard.json`, the last committed diff, and
   the relevant log for the failing category (`test-stdout.log` /
   `smoke-stdout.log` / `e2e-app.log` / `e2e-calls.log`). Use the remediation
   prompt in [`subagent-prompts.md`](subagent-prompts.md) verbatim.

3. **Apply the diff** and commit on the same branch as
   `mem0-heal: <category> attempt <N>`. Do NOT amend earlier commits,
   reviewers need the heal trail.

4. **Re-run `/mem0-test-integration --ci`**:
   - `overall: pass`, done, exit 0.
   - Same check still failing, increment the attempt counter and loop.
   - A *different* check now failing, that is a regression. Revert the heal
     commit (`git revert HEAD --no-edit`), record it in
     `.mem0-integration/heal-trace.md`, exit code 6.

5. **Bounded iterations.** Default 3 attempts per failing category, override
   with `--heal-max N` (hard cap 10). On exhaustion, exit code 6 with the full
   attempt trace: each diff, each scorecard, final log tail.

6. **Post-loop summary** written to `.mem0-integration/heal-trace.md`: which
   category failed, how many attempts, each diff's intent, final status, and
   on success the delta from the initial scorecard to the final one.
