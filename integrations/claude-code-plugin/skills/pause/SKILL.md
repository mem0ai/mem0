---
name: pause
description: Pause Mem0 memory capture on this machine. Use when the user wants to stop memories being recorded, for example for private work or experiments.
disable-model-invocation: true
---

# Pause memory capture

To pause (all hooks become no-ops; nothing is captured or sent):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/core/memory_cli.py" pause
```

Confirm the new state back to the user, and remind them that already-created
memories still exist and remain searchable. To turn capture back on, use
`/mem0:resume`.
