---
name: mem0-digest
description: >
  Weekly memory activity summary. Now part of /mem0:stats.
  TRIGGER: user runs /mem0:digest, or asks "weekly summary", "what's new in memory",
  "mem0 digest", "memory recap".
---

# Mem0 Digest (→ redirected to Stats)

`/mem0:digest` is now built into `/mem0:stats`. Run:

```
/mem0:stats --weekly
```

When `/mem0:stats` receives the `--weekly` flag, it includes a weekly activity
digest section: new memories this week grouped by category, activity pattern,
growth trends, and highlights.

This skill exists as a redirect for backward compatibility. Follow the
`/mem0:stats` skill with `--weekly`.
