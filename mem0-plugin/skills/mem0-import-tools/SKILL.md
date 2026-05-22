---
name: mem0-import-tools
description: >
  Import from competing AI tool config files. Now part of /mem0:import.
  TRIGGER: user runs /mem0:import-tools, or asks "import from cursor",
  "import cursorrules", "import from cline", "import from copilot",
  "import from continue", "migrate from cursor", "migrate memories".
---

# Mem0 Import Tools (→ redirected to Import)

`/mem0:import-tools` is now built into `/mem0:import`. Run:

```
/mem0:import --tools
```

When `/mem0:import` receives the `--tools` flag, it detects and imports from
competing AI tool configuration files (Cursor, Copilot, Cline, Continue)
using the same `import_competing_tools.py` script.

This skill exists as a redirect for backward compatibility. Follow the
`/mem0:import` skill with `--tools`.
