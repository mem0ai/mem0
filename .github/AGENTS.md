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
| Mem0 Plugin | `mem0-plugin-checks.yml` | Push to main (`integrations/mem0-plugin/`, excluding `.opencode-plugin/`), manual | pytest + hook exec bits + JSON manifest validation on Python 3.10, 3.11, 3.12 |
| OpenCode Plugin | `opencode-plugin-checks.yml` | Push to main (`.opencode-plugin/`), manual | Bun: tsc + build + dist artifact check |
| Pi Agent Plugin | `pi-agent-plugin-checks.yml` | Push to main (`integrations/pi-agent-plugin/`), manual | tsc + vitest + tsup on Node 20, 22 |
| n8n Node | `n8n-nodes-mem0-checks.yml` | Push to main (`integrations/n8n-nodes-mem0/`), manual | ESLint + tsc build on Node 20 |
| Zapier App | `zapier-mem0-checks.yml` | Push to main (`integrations/zapier-mem0/`), manual | tsc + `zapier validate` + offline unit tests on Node 22 |
| docs llms.txt | `docs-llms-txt-check.yml` | Manual | `docs/llms.txt` coverage |

Adding a package CI workflow: give it `workflow_call` plus `push` / `workflow_dispatch` as needed but **no `pull_request` trigger**, then register it in `ci-gate.yml` with a path filter under the `changes` job, a call job, and an entry in the gate job's `needs` list.

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
| n8n Node | `n8n-nodes-mem0-cd.yml` | `n8n-nodes-mem0-v*` | npm (`@mem0/n8n-nodes-mem0`) |

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
| PR Gate | `pr-gate.yml` | Closes PRs that do not link an issue labeled `accepted`, with a reopen path. Exempts members, bots, drafts, and docs-only changes. Never checks out PR code. |
| Vouch (check PR) | `vouch-check-pr.yml` | Comments on PRs from authors absent from `VOUCHED.td`. Comment-only, and the comment comes from this workflow rather than the action. |
| Vouch (manage list) | `vouch-manage-by-issue.yml` | Maintainers edit the trust list by commenting `!vouch @user`, `!denounce @user`, or `!unvouch @user` on any issue. Opens a PR against `VOUCHED.td` through a GitHub App token, for a maintainer to merge. |
| Issue Labeler | `issue-labeler.yml` | Labels issues from the `component` field in the issue forms |
| PR Labeler | `pr-labeler.yml` | Path-based labels, plus propagating labels from linked issues |
| Stale Bot | `stale.yml` | Marks stale issues and PRs |
| llms.txt Check | `docs-llms-txt-check.yml` | Blocks PRs touching `docs/**/*.mdx` when `docs/llms.txt` is out of sync |

`pr-gate.yml` and `vouch-check-pr.yml` use `pull_request_target`, which is required to label and close fork PRs. Neither checks out PR code and neither has a `run:` step, so there is no pwn-request or script-injection surface. Keep it that way: any future `run:` step in these files must never interpolate `github.event.*` text.

Both workflows exempt maintainers twice, and the second guard is the one that holds. `author_association` is rendered for the viewer, and a webhook payload has no privileged viewer: `MEMBER` needs the author's org membership to be **public**, `COLLABORATOR` needs a **direct** repository invite. An org member with private membership whose `maintain` comes through a team matches neither and arrives as `CONTRIBUTOR`, which is how PR #6948 was closed by its own author's gate. So the guard also skips any PR whose head branch lives in this repository (`head.repo.full_name == github.repository`). Pushing a branch here already requires write access and outside contributors always arrive from a fork, so that test means the same thing without depending on who is looking. Keep both: the `author_association` arm still covers members who work from their own fork.

`GATE_EFFECTIVE_FROM` in `pr-gate.yml` is a `created_at` cutoff. `edited`, `reopened`, and `ready_for_review` fire on PRs opened long before the gate existed, so without the cutoff the whole open backlog would be closed by a rule that did not exist when those PRs were filed. Set it to the actual merge date in UTC.

The gate's docs-only exemption covers `docs/` and top-level markdown such as `README.md` and `CONTRIBUTING.md`. Markdown nested anywhere else stays gated on purpose: `skills/**/*.md` and everything under `.github/` are functional files, not prose.

`auto-close: false` on `mitchellh/vouch/action/check-pr` is silent, not comment-only. In v1.5.0 the unvouched and denounced branches both return before posting anything, so the action leaves nothing but a line in the run log. The workflow reads the action's `status` output and posts the comment itself, keyed on a `<!-- vouch-check -->` marker so a reopen does not comment twice. Flipping `auto-close` to `true` later means deleting that step, or the author gets two comments.

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
