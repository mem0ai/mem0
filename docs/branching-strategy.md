# Branching and Upstream Sync Strategy

This repository is a fork of `mem0ai/mem0`. We maintain a set of private/custom patches that are not intended to be merged upstream yet, but we actively sync upstream changes. If a patch has value and is deemed ready, we create a pull request to upstream.

Goals:

- Keep a clean mirror of upstream.
- Develop and ship on top of upstream with our customizations.
- Make upstream syncs predictable and low-risk.

## Branch Roles

- `main`: Upstream mirror. Do not commit directly here. Updated only by fast-forwarding to `upstream/main`.
- `custom`: Long-lived branch that carries our private/custom patches. Daily development happens here.
- `{topic-branch}/*`: Short-lived topic branches created from `custom` for individual changes.

## Remotes

- `origin`: Our fork (this repository).
- `upstream`: The upstream `https://github.com/mem0ai/mem0.git`.

Add upstream once (only if not present):

```bash
git remote add upstream https://github.com/mem0ai/mem0.git
git fetch upstream --tags
```

## Initial Setup

1) Ensure `main` mirrors upstream:

```bash
git checkout main
git reset --hard upstream/main
git push -f origin main
```

2) Ensure `custom` is based on `main`:

```bash
git checkout -B custom main
git push -u origin custom
```

## Daily Development

- Create topic branches from `custom`:

```bash
git checkout custom
git switch -c feature/<short-topic>
# ...commit work...
git push -u origin feature/<short-topic>
```

- Merge back to `custom` via PR (preferred) or locally, then delete the topic branch.

## Syncing With Upstream

We keep `main` as an upstream mirror, and periodically rebase (or merge) `custom` onto it.

1) Fetch upstream:

```bash
git fetch upstream --tags
```

2) Update the mirror:

```bash
git checkout main
git pull --ff-only upstream main
git push origin main
```

3) Re-apply our custom patches on top of the new upstream (default: rebase):

```bash
git checkout custom
git rebase main
# Resolve conflicts if any, then continue
git rebase --continue
git push -f origin custom
```

If you prefer to preserve merge history instead of a linear history, replace the rebase step with:

```bash
git checkout custom
git merge --no-ff main
git push origin custom
```

## Conflict Handling Tips

- Minimize edits to upstream files; prefer adding new files/directories for custom code and using extension points/adapters.
- Enable Git rerere to auto-remember resolved conflicts:

```bash
git config --global rerere.enabled true
```

- When conflicts occur during rebase, resolve file-by-file, stage with `git add`, and continue the rebase.

## Versioning and Tags

- Tag upstream sync points on `main` as `upstream-vX.Y.Z` (optional, use upstream releases).
- Tag shipped custom builds on `custom` as `custom-vX.Y.Z-n`.

Examples:

```bash
git checkout main
git tag upstream-v1.2.3
git push origin upstream-v1.2.3

git checkout custom
git tag custom-v1.2.3-1
git push origin custom-v1.2.3-1
```

## Optional: Patch Queue Workflow

If you prefer to manage customizations explicitly as a patch queue:

1) Export patches from `custom` relative to `main`:

```bash
git format-patch main..custom -o patches/
```

2) After updating `main` to the latest upstream, recreate `custom` and apply patches:

```bash
git checkout -B custom main
git am patches/*.patch
```

This approach makes each change explicit but adds some overhead. For most cases, a `rebase` workflow is sufficient.

## Policy Summary

- Never commit directly to `main`.
- All development happens on `feature/*` branches from `custom`.
- Regularly sync `main` with `upstream/main` using fast-forward only.
- Rebase `custom` onto `main` (default) and force-push as needed.
- Keep custom changes isolated to reduce conflicts.
