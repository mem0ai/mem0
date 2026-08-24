---
name: forget
description: Delete the Mem0 memories stored for this repository (and this user). Use when the user asks to forget, clear, wipe, or delete memories.
disable-model-invocation: true
---

# Forget this repository's memories

This permanently deletes remote memories. Before running anything, tell the
user exactly what will be deleted (this repository's memory scope for their
user ID) and ask them to confirm.

After the user confirms, run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/core/memory_cli.py" forget --remote --yes
```

Report what the command output says was deleted. If the user only wants local
data cleared (evidence log, pending queue), run the same command without
`--remote`. Never pass `--yes` before the user has confirmed in this
conversation.
