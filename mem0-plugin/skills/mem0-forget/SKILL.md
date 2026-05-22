---
name: mem0-forget
description: >
  Delete memories by search query or memory ID. Now part of /mem0:dream.
  TRIGGER: user runs /mem0:forget <query>, or says "forget this", "delete memory",
  "remove that memory about X".
---

# Mem0 Forget (→ redirected to Dream)

`/mem0:forget` is now built into `/mem0:dream`. Run:

```
/mem0:dream --forget <query or memory ID>
```

When `/mem0:dream` receives the `--forget` flag, it skips the consolidation
analysis and goes straight to the search-confirm-delete flow.

This skill exists as a redirect for backward compatibility. Follow the
`/mem0:dream` skill with `--forget` and the user's argument.
