# GitHub Setup

## Secrets

Add in **Settings > Secrets > Actions**:

| Secret | How to Get |
|--------|------------|
| `FLY_API_TOKEN` | `flyctl tokens create deploy` |
| `ANTHROPIC_API_KEY` | console.anthropic.com |

## Branch Protection: deploy

**Settings > Branches > Add rule:**

| Setting | Value |
|---------|-------|
| Branch pattern | `deploy` |
| Require PR | ✓ |
| Require approvals | 1 |
| Require status checks | ✓ |
| Required checks | `Security Gate` |
| Require up to date | ✓ |

The `Security Gate` blocks merge if Claude flags SUSPICIOUS or DANGEROUS code.

## Workflows

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `pr-security-check.yml` | PR to deploy | Claude reviews code, blocks if unsafe |
| `deploy-test.yml` | Push to deploy | Deploys to test environment |
| `deploy-prod.yml` | `latest-release` tag | Deploys to production |

## Deploy Flow

```
PR to deploy → Claude review → Merge → Auto-deploy TEST

Create tag → Move latest-release → Auto-deploy PROD
```

## Rollback

Move `latest-release` to previous version:

```bash
git tag -f latest-release v0.9.0
git push origin latest-release --force
```
