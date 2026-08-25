# CI/CD and repository automation (`.github/`)

> **Do not modify any workflow without explicit approval from a maintainer.** Publishing
> credentials are bound to workflow filenames, and the gate workflows decide whether
> contributions are accepted. Read this file before proposing any change here.

## CI: one gate, many pipelines

`ci-gate.yml` (**CI Gate**) is the single entry point. It runs on every PR, detects which packages changed, and calls only the relevant package workflows as reusable workflows (`workflow_call`). Its final `CI Gate` job aggregates the results: skipped pipelines pass, failed or cancelled ones fail. It is the **only CI status check that needs to be required** in branch protection.

Package workflows keep their own push-to-main and manual triggers. Their `pull_request` triggers live in the gate's path filters instead.

| Workflow | File | Standalone triggers | Runs |
|----------|------|---------------------|------|
| CI Gate | `ci-gate.yml` | All PRs | Routes to and aggregates everything below |
| Python SDK | `ci.yml` | Push to main | Ruff + pytest on Python 3.10, 3.11, 3.12 |
| TypeScript SDK | `ts-sdk-ci.yml` | Push to main (`mem0-ts/`) | Prettier + build + jest on Node 20, 22 |
| Python CLI | `cli-python-ci.yml` | Push to main (`cli/python/`), manual | Ruff + pytest + hatch build on Python 3.10, 3.11, 3.12 |
| Node CLI | `cli-node-ci.yml` | Push to main (`cli/node/`), manual | Biome + tsc + vitest + tsup on Node 20, 22 |
| OpenClaw | `openclaw-checks.yml` | Push to main (`integrations/openclaw/`), manual | tsc + vitest (Codecov) + tsup on Node 20, 22 |
| Mem0 Plugin (legacy) | `mem0-plugin-checks.yml` | Push to main (`integrations/mem0-plugin/`, excluding `.opencode-plugin/`), manual | pytest + hook exec bits + JSON manifest validation on Python 3.10, 3.11, 3.12 |
| Claude Code Plugin | `claude-code-plugin-checks.yml` | Push to main (`integrations/claude-code-plugin/`), manual | pytest + ruff + JSON manifest validation on Python 3.10, 3.11, 3.12 |
| OpenCode Plugin | `opencode-plugin-checks.yml` | Push to main (`.opencode-plugin/`), manual | Bun: tsc + build + dist artifact check |
| Pi Agent Plugin | `pi-agent-plugin-checks.yml` | Push to main (`integrations/pi-agent-plugin/`), manual | tsc + vitest + tsup on Node 20, 22 |
| DeepSeek Harness Plugin | `deepseek-plugin-checks.yml` | Push to main (`integrations/deepseek-plugin/`), manual | tsc + vitest + tsup on Node 20, 22 |
| n8n Node | `n8n-nodes-mem0-checks.yml` | Push to main (`integrations/n8n-nodes-mem0/`), manual | ESLint + tsc build on Node 20 |
| Zapier App | `zapier-mem0-checks.yml` | Push to main (`integrations/zapier-mem0/`), manual | tsc + `zapier validate` + offline unit tests on Node 22 |
| mem0-strands | `mem0-strands-checks.yml` | Push to main (`integrations/mem0-strands/`), manual | Ruff + mypy + pytest + hatch build on Python 3.10, 3.11, 3.12 |
| docs llms.txt | `docs-llms-txt-check.yml` | Manual | `docs/llms.txt` coverage |
| GitHub Scripts | inline in `ci-gate.yml` | none | `node` over every `.github/scripts/*.test.js` |

Adding a package CI workflow: give it `workflow_call` plus `push` / `workflow_dispatch` as needed but **no `pull_request` trigger**, then register it in `ci-gate.yml` with a path filter under the `changes` job, a call job, and an entry in the gate job's `needs` list.

`GitHub Scripts` is the one row that is a plain job inside `ci-gate.yml` rather than a called workflow, because a reusable workflow wrapping two `node` invocations would be more file than test. It runs on the `github_scripts` filter, which covers `.github/scripts/**` plus every file those tests read: `pr-gate.yml`, `vouch-check-pr.yml`, `issue-labeler.yml`, and `VOUCHED.td`. Add a new `.github/scripts/*.test.js` and it is picked up with no wiring; make a test read a new file and that file belongs in the filter.

## Branch protection on `main`

A repository ruleset named `Main Branch Rule`, id `11813754`. It enforces squash-only merges, linear history, no deletion, no force-push, and one approving review. Two status checks belong in its `required_status_checks` rule:

| Context | Posted by | Why |
|---------|-----------|-----|
| `CI Gate` | `ci-gate.yml` | Aggregates every package pipeline |
| `license/cla` | CLA Assistant | Proves the CLA is signed, not merely requested |

Editing the ruleset requires repo **admin**. `maintain` is not enough, and the API returns 404 rather than 403 in that case. Until `license/cla` is required, the claim in `CONTRIBUTING.md` that unsigned PRs are blocked from merging holds by convention only.

Requiring `CI Gate` also means fork PRs from first-time contributors cannot merge until a maintainer approves the workflow run. Those sit at `action_required`, which is intended behavior.

## CD: one router, many publishers

`release.yml` (**Release Router**) is the only workflow listening to `release: published`. It matches the tag prefix and dispatches the matching package workflow through `workflow_dispatch`, so one release produces exactly one routed run.

| Workflow | File | Tag prefix | Target |
|----------|------|------------|--------|
| Release Router | `release.yml` | all releases | dispatches the rows below |
| Python SDK | `cd.yml` | `v*` | PyPI (`mem0ai`) |
| TypeScript SDK | `ts-sdk-cd.yml` | `ts-v*` | npm (`mem0ai`) |
| Python CLI | `cli-python-cd.yml` | `cli-v*` | PyPI (`mem0-cli`) |
| Node CLI | `cli-node-cd.yml` | `cli-node-v*` | npm (`@mem0/cli`) |
| Vercel AI SDK | `vercel-ai-cd.yml` | `vercel-ai-v*` | npm (`@mem0/vercel-ai-provider`) |
| OpenClaw | `openclaw-cd.yml` | `openclaw-v*` | npm (`@mem0/openclaw-mem0`) |
| OpenCode Plugin | `opencode-plugin-cd.yml` | `opencode-v*` | npm (`@mem0/opencode-plugin`) |
| Pi Agent Plugin | `pi-agent-plugin-cd.yml` | `pi-agent-v*` | npm (`@mem0/pi-agent-plugin`) |
| DeepSeek Harness Plugin | `deepseek-plugin-cd.yml` | `deepseek-plugin-v*` | npm (`@mem0/deepseek-plugin`) |
| n8n Node | `n8n-nodes-mem0-cd.yml` | `n8n-nodes-mem0-v*` | npm (`@mem0/n8n-nodes-mem0`) |
| mem0-strands | `mem0-strands-cd.yml` | `mem0-strands-v*` | PyPI (`mem0-strands`) |

- Package CD workflows are `workflow_dispatch`-only, with `tag` and `prerelease` inputs. They check out and build the given tag.
- All publishing uses **OIDC trusted publishing**. No tokens, no secrets.
- Registry trusted-publisher settings are pinned to each package's own workflow **filename**. Renaming a CD workflow breaks publishing for that package.
- First publish of a new npm package must be done manually. OIDC works from the second version onward.
- To re-publish a release, do **not** delete and recreate the GitHub release. Dispatch the workflow directly: `gh workflow run <package>-cd.yml --ref refs/tags/<tag> -f tag=<tag>`.
- The Zapier app deploys to Zapier's platform, not npm, so it is not in the router. Deploy with `gh workflow run zapier-mem0-cd.yml --ref main`.
- Adding a package: add its CD workflow, then register its tag prefix in the `case` block in `release.yml`, keeping the bare `v*` arm last.

## Contribution gates

| Workflow | File | Purpose |
|----------|------|---------|
| PR Gate | `pr-gate.yml` | Closes PRs that do not link an issue labeled `accepted`, and reopens them when that label arrives. Exempts members, bots, drafts, and docs-only changes. Never checks out PR code. |
| Vouch (check PR) | `vouch-check-pr.yml` | Closes PRs from authors denounced in `VOUCHED.td`. Comments once on PRs from authors merely absent from it, and blocks nothing in that case. |
| Vouch (manage list) | `vouch-manage-by-issue.yml` | Maintainers edit the trust list by commenting `!vouch @user`, `!denounce @user`, or `!unvouch @user` on any issue. Opens a PR against `VOUCHED.td` through a GitHub App token, for a maintainer to merge. |
| Issue Labeler | `issue-labeler.yml` | Labels issues from the `component` field in the issue forms |
| PR Labeler | `pr-labeler.yml` | Path-based labels, plus propagating labels from linked issues |
| Stale Bot | `stale.yml` | Marks stale issues and PRs |
| llms.txt Check | `docs-llms-txt-check.yml` | Blocks PRs touching `docs/**/*.mdx` when `docs/llms.txt` is out of sync |

`pr-gate.yml` and `vouch-check-pr.yml` use `pull_request_target`, which is required to label and close fork PRs. Neither checks out PR code and neither has a `run:` step, so there is no pwn-request or script-injection surface. Keep it that way: any future `run:` step in these files must never interpolate `github.event.*` text.

Both workflows exempt maintainers twice, and the second guard is the one that holds. `author_association` is rendered for the viewer, and a webhook payload has no privileged viewer: `MEMBER` needs the author's org membership to be **public**, `COLLABORATOR` needs a **direct** repository invite. An org member with private membership whose `maintain` comes through a team matches neither and arrives as `CONTRIBUTOR`, which is how PR #6948 was closed by its own author's gate. So the guard also skips any PR whose head branch lives in this repository (`head.repo.full_name == github.repository`). Pushing a branch here already requires write access and outside contributors always arrive from a fork, so that test means the same thing without depending on who is looking. Keep both: the `author_association` arm still covers members who work from their own fork.

`pr-gate.yml` carries two jobs whose `if:` conditions are deliberately disjoint. `gate` closes, and only ever runs on `opened`, `reopened`, and `ready_for_review`. `reopen` reopens, and only ever runs on `edited` or on `issues: labeled` with the `accepted` label. Nothing can both close and reopen on the same event, which is the property to preserve when editing either guard.

That split exists because the two halves of a gated PR's recovery arrive in either order. A maintainer usually labels the issue `accepted` at triage, before the author has linked it; sometimes the link lands first and the label follows. So `reopen` handles both directions. From `issues: labeled` it walks `closedByPullRequestsReferences` back to the pull requests that link the issue. From `edited` it takes the edited pull request directly. Both paths then apply the same four tests: the author is not denounced in `VOUCHED.td`, the PR is `CLOSED`, it links an issue labeled `accepted`, and it carries the `<!-- pr-gate -->` marker comment. Without the label path, a maintainer's label is inert. Without the `edited` path, an author who links the issue after it was labeled is stuck, since no other event fires.

The denounce test is what keeps the two gates from cancelling each other out. A denounced author whose PR also lacked an accepted issue was closed by both workflows, so it carries the `<!-- pr-gate -->` marker, and labeling the linked issue would otherwise reopen it. Vouch cannot undo that: reopening runs through `GITHUB_TOKEN`, which raises no events, so `vouch-check-pr.yml` never fires a second time. Reading the list here is the only place the check can live. It fails open like vouch does, warning and treating nobody as denounced if the file cannot be read, and it is the one piece of vouch semantics duplicated outside `vouch-check-pr.yml`, because `pr-gate.yml` never checks out the repository and so cannot import a shared parser. `.github/scripts/vouch-decision.test.js` covers the parsing and asserts `pr-gate.yml` still filters the list the same way.

`edited` must never reach the `gate` job. It fires on any title or description change, so when `gate` listened for it the gate re-judged pull requests that had been open for days and closed them the moment their author touched the description, which is what closed #6948. Rescuing on `edited` is safe for the same reason closing on it was not: the job can only move a PR from closed to open.

Reopening runs through `GITHUB_TOKEN`, which by design raises no further workflow events, so `gate` cannot bounce a freshly reopened PR straight back out.

The concurrency group is keyed on `github.event.action` as well as `github.event_name` and the number, and both keys carry weight. Without the event name, a maintainer applying `bug` right after `accepted` cancels the reopen mid-flight, since `cancel-in-progress` is on for `pull_request_target` and both label events would land in the same group. Without the action, `opened` and `edited` share a group on the same pull request, and an author who ticks a template checkbox in the seconds after opening cancels the run that was about to gate them: `gate` skips `edited` and `reopen` skips an open pull request, so the cancelled run is never replaced and the pull request stays ungated forever, since `opened` fires exactly once. Rapid successive edits still cancel each other, which is the dedup that was wanted.

The `edited` arm of `reopen` requires `github.event.pull_request.state == 'closed'`, so ordinary description edits on open pull requests do not start a runner.

Two known gaps, both mild. A PR that the gate closed, that someone reopened, and that a maintainer then closed deliberately still carries the marker, so labeling its issue reopens it again; a maintainer closes it once more. And an author who strips `Closes #<number>` out after passing keeps an open PR, which a reviewer sees anyway.

`GATE_EFFECTIVE_FROM` in `pr-gate.yml` is a `created_at` cutoff. `reopened` and `ready_for_review` still fire on PRs opened long before the gate existed, so without the cutoff part of the open backlog would be closed by a rule that did not exist when those PRs were filed. Set it to the actual merge date in UTC.

The gate's docs-only exemption covers `docs/` plus a named allowlist of four root files: `README.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, and `SECURITY.md`. It is an allowlist rather than a rule about top-level markdown because the repository root also holds `AGENTS.md`, `CLAUDE.md`, and `LLM.md`, which are the instructions coding agents read before touching this codebase. Those are functional files that happen to be written in prose, and rewriting them is a change to behaviour, so they stay gated. Markdown nested anywhere else stays gated for the same reason: `skills/**/*.md` and everything under `.github/` are functional too. Adding a genuinely prose root file means adding it to `rootDocs` in `pr-gate.yml`.

`.github/scripts/pr-gate-docs-exemption.test.js` covers that predicate. It pulls the `rootDocs` and `isDocs` lines out of `pr-gate.yml` and evaluates them, so it exercises the shipped rule rather than a copy that could drift from it, and it pins `AGENTS.md`, `CLAUDE.md`, and `LLM.md` on the gated side along with `skills/**/*.md`, nested `.github/` files, and the empty file list. It only accepts those two declarations in a literal one-line form, so keep `rootDocs` a `Set` of quoted names and `isDocs` a single arrow expression.

The two contribution gates answer different questions and neither covers for the other. `pr-gate.yml` judges the change, and the `accepted` label is how a maintainer says yes to it. `vouch-check-pr.yml` judges the author, and `VOUCHED.td` is how a maintainer says no to one. A vouched author with no accepted issue is still closed by the gate; a denounced author with an accepted issue is still closed by vouch. Read either one as a backstop for the other and both get weakened.

Vouch enforces on the denounce axis only, through `require-vouch: false` with `auto-close: true`. That pair is not the obvious reading of either input, so the decision table from v1.5.0 (`vouch/github.nu` at pinned SHA `d66fa29`) is worth stating outright:

| Author | `status` | Effect |
|---|---|---|
| ends in `[bot]` | `skipped` | nothing |
| collaborator with write or admin | `vouched` | nothing |
| listed in `VOUCHED.td` | `vouched` | nothing |
| listed as `-handle` | `closed` | action comments and closes |
| absent from the file | `allowed` | workflow comments, nothing closed |

`require-vouch: true` would close every first-time contributor, which is the opposite of what a trust list is for: the funnel has to stay open or nobody ever earns a vouch. `auto-close: false` is the setting that looked safe and did nothing at all, since in v1.5.0 both the unvouched and the denounced branch return before posting anything, leaving only a line in the run log. That is why `!denounce` was decorative until this pair landed.

Only the `allowed` arm is ours: a `github-script` step posts the soft comment, keyed on a `<!-- vouch-check -->` marker so a reopen does not comment twice. The `closed` arm belongs to the action, message and all. Keeping the two arms disjoint is what stops a denounced author getting two comments, so if that step is ever re-keyed off `allowed`, check the overlap first.

`.github/scripts/vouch-decision.test.js` holds that table as a `decide()` function and asserts the workflow's `require-vouch`, `auto-close`, and comment-step gating still produce it, comment counts included. Be clear about what that does and does not prove. `decide()` is a **hand transcription** of `gh-check-pr`, read from `vouch/github.nu` at the pinned SHA; the test cannot run the action, so it cannot notice the action changing underneath it. Left alone it would agree with itself forever, which makes bumping the pinned SHA the one edit it would otherwise sail through. So it also asserts `vouch-check-pr.yml` still pins `PINNED_VOUCH_SHA`, and a bump fails it on purpose: re-read `gh-check-pr` at the new revision, correct `decide()` and the table above, then move the constant. CI runs it through the `GitHub Scripts` job on any change to the scripts or the files they read.

Failure is open by design. If the action cannot read `VOUCHED.td` it falls back to an empty list, every author reads as absent, and nobody is closed by an API hiccup.

`vouch-manage-by-issue.yml` runs with `merge-immediately: "false"`. The `Main Branch Rule` ruleset requires one approving review and has no bypass actors, so the action's immediate `PUT /pulls/{n}/merge` would return 405 and leave `VOUCHED.td` unchanged on `main`. The bot opens the PR, a maintainer merges it. Setting `pull-request: "false"` is not an alternative: the same ruleset blocks direct pushes.

That workflow also needs `VOUCH_APP_ID` and `VOUCH_APP_PRIVATE_KEY` repository secrets. Without them it fails at the token step before doing anything. `vouch-check-pr.yml` needs neither.

## Issue forms and templates

`ISSUE_TEMPLATE/*.yml` are GitHub issue **forms**, not markdown templates. Only forms support `required: true` and machine-parseable field ids. Blank issues are disabled in `config.yml`.

`issue-labeler.yml` reads only the `component` field id through `stefanbuck/github-issue-parser` and `redhat-plumbers-in-action/advanced-issue-labeler`, so adding new field ids is safe. Renaming `component` is not.

Current field ids:

| Form | Ids |
|------|-----|
| `bug_report.yml` | `component`, `description`, `verification`, `ai_assistance` |
| `feature_request.yml` | `component`, `description`, `ai_assistance` |
| `documentation_issue.yml` | `description`, `ai_assistance` |

## Trust list

`VOUCHED.td` is one GitHub username per line, `#` for comments. Seeded from every author with at least one merged PR in this repository, then filtered: accounts at or below a 16% merge rate across five or more attempts were dropped, since landing one change out of many is the signature of automated submission rather than contribution.

Vouch's only built-in exemptions are accounts ending in `[bot]` and repo collaborators with `write` or `admin`. **Organization membership alone is not one of them.** So `vouch-check-pr.yml` carries a job-level `if:` that skips the check for `OWNER`, `MEMBER`, and `COLLABORATOR` authors, the same exemption `pr-gate.yml` already applies. Org members are still listed in the file as a fallback, but the workflow guard is what actually holds.
