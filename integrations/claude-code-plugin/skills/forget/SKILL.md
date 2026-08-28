---
name: forget
description: Delete the Mem0 memories stored for this repository and this user. Use when the user asks to forget, clear, wipe, or delete memories.
disable-model-invocation: true
---

# Forget this repository's memories

This permanently deletes remote memories. Before running anything, tell the
user exactly what will be deleted: this repository's memory scope for their
user ID only. Teammates' memories are never touched. The repository's
operating notes are shared by everyone who works in it, so they stay unless
the user explicitly asks to delete those too.

After the user confirms, run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/core/memory_cli.py" forget --remote --yes
```

If the user also asked to delete the repository's operating notes, add
`--include-operating-notes` and say that this removes them for every teammate.

Report what the command output says was deleted. If the user only wants local
data cleared (evidence log, pending queue), run the same command without
`--remote`. Never pass `--yes` before the user has confirmed in this
conversation.
