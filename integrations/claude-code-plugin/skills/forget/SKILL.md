---
name: forget
description: Delete the Mem0 memories stored for this repository and this user. Use when the user asks to forget, clear, wipe, or delete memories.
disable-model-invocation: true
---

# Forget this repository's memories

This permanently deletes remote memories. Before running anything, tell the
user exactly what will be deleted: their own memories for this repository
only. The repository's project memory is shared by everyone who works in it,
so it stays unless the user explicitly asks to delete that too.

After the user confirms, run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/core/memory_cli.py" forget --remote --yes
```

If the user also asked to delete the repository's shared project memory, add
`--include-project-memory` and say that this removes it for every teammate.

Report what the command output says was deleted. If the user only wants local
data cleared (evidence log, pending queue), run the same command without
`--remote`. Never pass `--yes` before the user has confirmed in this
conversation.
