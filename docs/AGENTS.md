# Documentation (`docs/`)

Mintlify site published at https://docs.mem0.ai.

## Commands

```bash
make docs          # from repo root
cd docs && mintlify dev
```

## Structure

| Path | Contents |
|------|----------|
| `api-reference/` | Platform REST endpoints |
| `open-source/` | Self-hosted SDK guides |
| `platform/` | Hosted platform guides |
| `integrations/` | One page per integration |
| `core-concepts/` | Memory model, graph memory, scoping |
| `cookbooks/` | End-to-end recipes |
| `contributing/` | Contributor guides |
| `docs.json` | Navigation tree |
| `openapi.json` | Platform API spec |
| `llms.txt` | Scope-tagged index for agents |

## Adding a page

Every new `.mdx` page needs three things, or CI fails:

1. The page itself under the right section.
2. A navigation entry in `docs.json`.
3. A line in `llms.txt` with a scope tag (`[Platform]`, `[OSS]`, or `[Both]`) and a description that starts with `Use when ...`.

`docs-llms-txt-check.yml` runs on every PR touching `docs/**/*.mdx` and **blocks the merge** when `llms.txt` is out of sync. To fix:

```bash
python scripts/check-llms-txt-coverage.py --write
```

That scaffolds placeholders under `## Unclassified - needs triage`. Then replace each `[TODO: ...]` tag, rewrite the descriptions as `Use when ...`, move entries into the correct section, and delete the triage heading once it is empty.

## Conventions

- Frontmatter needs `title`, `description`, and usually `icon`.
- Mintlify components (`<Note>`, `<Card>`, `<Tabs>`, `<CodeGroup>`) are available; prefer them over raw HTML.
- Code samples must be runnable. If a sample calls a public SDK method, it has to match the real signature.
- Documentation-only PRs are exempt from the `accepted`-issue requirement in the PR gate, but not from the CLA.
- Any change to a public SDK signature has to update the matching page here in the same PR.
