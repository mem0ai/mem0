---
name: mem0-test-integration
description: >
  Verify a Mem0 integration produced by /mem0-integrate. Runs in the same
  workspace on the same branch (loose coupling) — installs dependencies,
  runs the repo's native test suite, then exercises a real end-to-end
  smoke flow against the user's API key. Produces a scorecard.
  TRIGGER when: user has just run /mem0-integrate and says "verify",
  "test the integration", "run /mem0-test-integration", or when a
  .mem0-integration/ directory exists and tests have not been run yet
  on the current branch.
  DO NOT TRIGGER when: the user wants to run general project tests
  (defer to the repo's native test command), or when no prior /mem0-integrate
  run exists in the current branch (ask them to run /mem0-integrate first).
  This skill ONLY catches compile and runtime bugs by design. Logical
  integration errors — wrong data stored, wrong time retrieved, wrong
  user scoping — are on the human reviewer.
license: Apache-2.0
metadata:
  author: mem0ai
  version: "0.1.0"
  category: ai-memory
  tags: "memory, integration, testing, tdd, platform, oss"
  coupling: loose
  mem0_tested_versions: "mem0ai (PyPI) >=2.0.0,<3.0.0; mem0ai (npm) >=3.0.0,<4.0.0"
---

# mem0-test-integration

Verifies what `/mem0-integrate` produced. Runs in the same workspace,
on the same feature branch. Loose coupling — fast, catches compile and
runtime bugs, does not catch logical errors.

## Canonical sources (use these, not ambient knowledge)

All static checks and smoke-test shapes validate against these URLs.
`WebFetch` each before running step 3.

- Scope-tagged docs index: https://docs.mem0.ai/llms.txt
- OpenAPI (Platform REST): https://docs.mem0.ai/openapi.json
- Published SDK skill (canonical call patterns): https://raw.githubusercontent.com/mem0ai/mem0/main/skills/mem0/SKILL.md
- Vercel AI SDK skill (if the target repo uses `@ai-sdk/*`): https://raw.githubusercontent.com/mem0ai/mem0/main/skills/mem0-vercel-ai-sdk/SKILL.md
- SDK source (cross-check version against frontmatter `mem0_tested_versions`):
  - Repo root: https://github.com/mem0ai/mem0
  - Python: https://github.com/mem0ai/mem0/tree/main/mem0
  - TypeScript: https://github.com/mem0ai/mem0/tree/main/mem0-ts

Read the `Delegated skill:` field in `.mem0-integration/plan.md` — if it
names a skill URL, fetch that skill and use its example blocks as the
reference for both static checks (step 3) and the smoke test (step 5).

## Non-invasiveness contract

Every check in this skill assumes the integration is **additive and
feature-flagged** (see `/mem0-integrate` "Integration principles").
Specifically:

- `product.json` must contain a `feature_flag` field.
- Steps 4–6 run in two passes:
  - **Pass A — flag unset.** All pre-existing tests must pass, smoke/E2E
    skip. The repo must behave like `main`. Any failure here is a
    **hard fail** — do not let the self-heal loop attempt a patch.
  - **Pass B — flag set.** New tests must pass, smoke and E2E run.
- If Pass A fails, the scorecard marks `non_invasive: false` and sets
  `overall: fail` with a distinct reason code the integrator's heal
  loop refuses to touch.

## Preconditions

Refuse to start unless ALL of the following are true:

- `.mem0-integration/` directory exists in the repo root.
- `.mem0-integration/product.json`, `goal.md`, and `plan.md` are readable
  and internally consistent (JSON parses, docs non-empty).
- Current branch name begins with `mem0-integrate/` (set by the companion
  skill). Prevents accidental runs on unrelated branches.
- Working tree is clean. The skill never modifies source files; any dirty
  state means the integration is mid-edit and not ready to verify.
- The same API key the integration used is available in the environment
  (`MEM0_API_KEY` for Platform, `OPENAI_API_KEY` for OSS — read which from
  `product.json`). Interactive mode asks if missing; CI mode exits 2.

Exit with a written rationale on any precondition failure. Never attempt
to "fix up" state.

## Pipeline

### 1. Read the contract

Load:

- `product.json` → which language, which product (Platform vs OSS), which
  mem0 version, `write_site`, `read_site`.
- `plan.md` → the mechanical contract (write pattern, read pattern,
  preserved behavior).
- `goal.md` → the intent (displayed in the scorecard only; not tested).

### 2. Install dependencies

Route by language from `product.json`:

| Language | Command |
|---|---|
| Python | `pip install -e .` if editable, else `pip install -r requirements.txt`. Then `pip install mem0ai` if not already present at the pinned version. |
| TypeScript / JavaScript | `npm install` (or `pnpm install` / `yarn install` if detected by lockfile). |

If install fails → exit code 2 with stderr tail. Never move to testing
if dependencies don't resolve.

### 3. Static sanity checks (fast, local, no API calls)

- **Import check**: does the write-site file import the expected Mem0
  surface? Authoritative list comes from `## Identify the User's Setup`
  in `https://docs.mem0.ai/llms.txt`:
  - Platform Python → `from mem0 import MemoryClient`
  - Platform TS → `import MemoryClient from "mem0ai"`
  - OSS Python → `from mem0 import Memory`
  - OSS TS → `import { Memory } from "mem0ai/oss"`

  If `plan.md` names a delegated skill (e.g., Vercel AI), use *that*
  skill's import signature instead of the list above. Mismatch → fail
  with line number.
- **Version check**: installed `mem0ai` version falls in the range from
  this skill's `mem0_tested_versions`. Out of range → warn but continue.
- **Type check** (TS tracks only): run `tsc --noEmit` or `tsup --dts`.
  Non-zero → fail.
- **Lint** (if the repo has a linter configured): run the repo's own
  lint command. Lint failures from this skill's changes → fail; pre-existing
  lint failures → surface as a warning.

### 4. Run the repo's native test suite (two passes)

| Language | Test command (in priority order) |
|---|---|
| Python | `pytest` with the test files from step 5 of the companion skill, else `python -m unittest discover`. |
| TypeScript / JavaScript | `npm test` if defined in package.json; else auto-detect `vitest` or `jest`. |

**Pass A — `feature_flag` unset.** Run the *entire* pre-existing suite
(excluding the new `test_mem0_*` files). **Must be 100% green.** Any
failure here marks `non_invasive: false` in the scorecard and is
a **hard fail** — the integrator's self-heal loop refuses to touch it.

**Pass B — `feature_flag` set** (value from `product.json`). Run the
full suite including the new tests. All must pass.

Isolate integration-introduced failures using `git diff main..HEAD
--name-only`. A test file that exists on `main` and fails only under
the integration branch (flag set *or* unset) counts against the
scorecard regardless of pass. A test file that already failed on `main`
is surfaced as `pre_existing_unrelated` and does not count — but is
still reported so the user can clean it up.

Capture output to `.mem0-integration/test-stdout-flag-off.log` and
`.mem0-integration/test-stdout-flag-on.log`. Scorecard reports pass/fail
per pass.

### 5. Smoke test (real API call, shortest round-trip)

Scripted end-to-end flow tailored to `product.json`. The call shapes
below are the minimal ones; if `plan.md` names a delegated skill, use
*that skill's* minimal example verbatim instead — it is the canonical
shape for the detected stack.

**Platform (Python):**

    from mem0 import MemoryClient
    c = MemoryClient()                               # uses MEM0_API_KEY
    uid = f"mem0-test-integration-{os.urandom(4).hex()}"
    c.add([{"role": "user", "content": "I prefer aisle seats"}], user_id=uid)
    hits = c.search("seat preference", user_id=uid)
    assert any("aisle" in h.get("memory", "") for h in hits), hits
    c.delete_all(user_id=uid)                        # clean up

**Platform (TS):** same shape with `MemoryClient` from `"mem0ai"`.

**OSS (Python / TS):** uses `Memory()` / `new Memory()` with default config
(OpenAI LLM via `OPENAI_API_KEY`, local Qdrant). If the repo ships a
`docker-compose.yml` with a Qdrant service, the skill starts it first and
tears it down after. If no backing store is reachable → fail with a
clear message naming the fix.

The smoke test always uses a **disposable random user_id** prefixed with
`mem0-test-integration-` so a failed cleanup doesn't pollute the user's
real data. A background tidy step deletes any prefix-matching entries
older than 24 hours on the next run.

Capture output to `.mem0-integration/smoke-stdout.log`.

### 6. E2E integration test (run the app, exercise the flow)

Unit tests + smoke prove the SDK works in isolation. This step is the
real signal: **does memory actually appear in the app's user-visible
output when the integration runs end-to-end?**

Requires `plan.md` to contain an `E2E recipe:` section (authored by
`/mem0-integrate` step 5). If absent → status `skipped` (not `fail`),
note in scorecard that the repo has no runnable entry point.

Recipe fields the skill reads:

- `start` — shell command to launch the app using `$PORT` for any network
  port. Run in background with stdout/stderr teed to
  `.mem0-integration/e2e-app.log`.
- `ready_probe` — how to detect readiness. `url=... status=...` polls an
  HTTP endpoint; `log="..."` waits for a substring in `e2e-app.log`;
  `sleep=N` waits N seconds (last resort). 60-second hard timeout.
- `compose_services` — optional. If set, bring them up via
  `docker compose up -d <services>` before `start`, tear them down with
  `docker compose down` at the end.
- `write_call` — triggers the Mem0 write path exactly once. Output is
  captured and surfaced on failure. 60-second hard timeout.
- `write_async_wait_ms` — pause after `write_call` to let async memory
  flushes land. Default 0.
- `read_call` — triggers the Mem0 read path. Typically a fresh session
  or new request that should surface the stored memory.
- `read_assert` — substring, `regex=...`, or `jsonpath=<expr>=<value>`
  that must appear in `read_call`'s stdout. This is the E2E pass gate.

Execution order:

1. Allocate an ephemeral TCP port; export as `PORT`.
2. Set `MEM0_USER_ID` to a disposable `mem0-test-integration-<rand>` value
   and export it, so the app can use the same scoping the smoke test does
   if the recipe wants cleanup.
3. Bring up `compose_services` if named.
4. Run `start` in the background.
5. Poll `ready_probe` until success or 60s timeout. Timeout → fail.
6. Run `write_call`. Non-zero exit → fail (but continue to cleanup).
7. Sleep `write_async_wait_ms`.
8. Run `read_call`.
9. Evaluate `read_assert` against `read_call`'s stdout. Miss → fail.
10. Cleanup (always, even on failure): SIGTERM the app, SIGKILL after
    5s, `docker compose down` if services were started, `delete_all`
    memories matching `mem0-test-integration-*` on Platform scenarios.

On any failure, the scorecard includes:

- Last 40 lines of `e2e-app.log`
- Full `write_call` output
- Full `read_call` output
- The expected vs actual for `read_assert`

### 7. Scorecard

Write `.mem0-integration/scorecard.md` and `.mem0-integration/scorecard.json`:

    {
      "timestamp": "2026-04-20T14:03:11Z",
      "branch": "mem0-integrate/remember-user-preferences",
      "product": "platform",
      "language": "python",
      "mem0_version": "2.0.0",
      "non_invasive": true,
      "feature_flag": "MEM0_ENABLED",
      "results": {
        "install":      {"status": "pass", "duration_ms": 12043},
        "static_checks":{"status": "pass", "duration_ms": 812},
        "unit_tests_flag_off": {"status": "pass", "duration_ms": 3920, "count": 47,
                                "reason": "all pre-existing tests green with flag unset"},
        "unit_tests_flag_on":  {"status": "pass", "duration_ms": 4321, "count": 49},
        "smoke_test":   {"status": "pass", "duration_ms": 2890, "memory_id": "mem_..."},
        "e2e_test":     {"status": "pass", "duration_ms": 14200,
                         "ready_probe_ms": 3100, "write_exit": 0,
                         "read_assert_matched": true}
      },
      "friction": {
        "dependency_install_retries": 0,
        "pre_existing_test_failures": 0,
        "warnings": ["mem0ai 2.0.0 pinned; consider 2.0.1 for fix X"]
      },
      "overall": "pass"
    }

The markdown version is human-readable and includes:

- Goal doc + plan doc reprinted at top (so reviewers don't have to hunt).
- Each check with pass/fail + log excerpt.
- Friction summary.
- Verbatim warnings from mem0 SDK (if any — e.g., deprecated field usage).
- **Explicit "NOT checked" section** listing what loose coupling misses:
  "Whether the stored data is what the user wants stored. Whether search
  runs at the right moment. Whether user_id matches the actual session
  scope. Human review required."

### 8. Report + exit

- Print the scorecard path + overall pass/fail to stdout.
- **Do not commit the scorecard files.** They live in `.mem0-integration/`,
  which is gitignored. The user can inspect and optionally pin.
- On fail: print the first failing step's log tail (last 40 lines) and
  stop. Do not attempt to fix anything.

## Artifacts (all under `.mem0-integration/`)

| File | Purpose | Retention |
|---|---|---|
| `scorecard.md` | Human-readable verdict. | Overwritten per run. |
| `scorecard.json` | Machine-readable verdict. Consumed by the CI scorecard workflow later. | Overwritten per run. |
| `test-stdout-flag-off.log` | Step 4 Pass A (pre-existing suite, flag unset). | Overwritten per run. |
| `test-stdout-flag-on.log` | Step 4 Pass B (full suite, flag set). | Overwritten per run. |
| `smoke-stdout.log` | Full output from step 5. | Overwritten per run. |
| `e2e-app.log` | Background app stdout/stderr from step 6. | Overwritten per run. |
| `e2e-calls.log` | write_call + read_call invocations and outputs. | Overwritten per run. |

## Modes

| Mode | Trigger | Behavior |
|---|---|---|
| Interactive (default) | TTY present, `MEM0_TEST_CI` unset | Asks for missing keys, prints friendly summaries. |
| CI | `MEM0_TEST_CI=1` | Keys must be in env, no prompts, non-zero exit on any fail. JSON scorecard goes to stdout's tail for workflow parsing. |

## Invocation

    /mem0-test-integration                       # interactive, all steps
    /mem0-test-integration --ci                  # non-interactive
    /mem0-test-integration --skip-smoke          # no API calls, no E2E
    /mem0-test-integration --skip-e2e            # unit + smoke only (faster CI)
    /mem0-test-integration --only-smoke          # just smoke
    /mem0-test-integration --only-e2e            # just E2E (assumes deps installed)

Composition: `--skip-*` can stack (`--skip-smoke --skip-e2e` = static +
unit only, zero API cost). `--only-*` is mutually exclusive with all
other flags.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | All checks passed. |
| 1 | Precondition failed (no `.mem0-integration/`, wrong branch, dirty tree). |
| 2 | Missing env key (CI mode) or dependency install failure. |
| 3 | Static sanity check failed (wrong import, type error). |
| 4 | Unit tests failed (Pass B — integration itself broken). |
| 5 | Smoke test failed. |
| 6 | E2E test failed (ready_probe timeout, write/read call failed, or read_assert miss). |
| 7 | Non-invasiveness violation: Pass A failed (pre-existing tests broke). Integrator's heal loop refuses to touch this. |
| 8 | Internal error (skill bug — report it). |

## Explicitly out of scope

- **Modifying source files.** The skill is read-only against the repo.
  If verification exposes a bug, re-run `/mem0-integrate` on the same
  goal + plan; do not hand-patch.
- **Fixing broken tests.** Failing unit tests are a signal that the
  integration is wrong, not that the tests are wrong. The skill does
  not "try a different test."
- **Deep logical correctness.** The E2E step proves "something the user
  said earlier comes back later," which is a useful but shallow signal.
  It does NOT prove the integration picks the *right* facts to store,
  scopes `user_id` correctly across real users, or handles conflict
  resolution well. That's human review territory.
- **Self-healing.** This skill never modifies source files. The paired
  `/mem0-integrate` skill in its default `--heal` mode consumes the
  scorecard produced here and drives its own remediation loop. Exit
  code 7 (non-invasiveness violation) is the explicit signal the heal
  loop must stop and surface to the user.
- **Cross-branch comparisons.** No `main` baseline diffing. The
  scorecard reflects this branch only.
- **Running against production data.** Every smoke test uses a disposable
  random user_id and cleans up after. Never touches any other user's data.
