---
name: compact-memory
description: Terse one-liner memory display — type, content, and ID.
---

# Compact Memory Output Style

When this style is active, all memory-related output uses this one-liner format:

```
[<type>] <content, max 80 chars> [mem0:<short_id>]
```

## Examples

```
[decision] Auth module uses JWT with RS256 signing keys [mem0:a3f8b2c1]
[convention] All API routes live in src/routes/ with kebab-case filenames [mem0:7e2d9f4a]
[anti_pattern] Don't use raw SQL — always go through the ORM layer [mem0:c4d5e6f7]
[task_learning] Redis cache TTL should be 300s for user sessions [mem0:d8e9f0a1]
```

## Rules

- Type in brackets, lowercase, from `metadata.type`
- Content truncated at 80 chars with no trailing ellipsis
- Short ID = first 8 chars of memory ID
- One memory per line, no extra formatting
- No headers or separators between memories unless grouped
- When grouped by type, use a blank line between groups

## When to use

- `/mem0:peek` results
- `/mem0:tour` memory listings
- Search results from `search_memories`
- Any context where memories are displayed inline
