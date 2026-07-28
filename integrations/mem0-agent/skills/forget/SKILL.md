---
name: forget
description: Delete memories the user no longer wants kept, by search or by id, with confirmation. Use when the user says forget that, delete that memory, that's wrong, or wants to remove outdated or sensitive stored information.
---

# Forget

Deleting is the one irreversible-feeling operation here, so it always goes: find → show →
confirm → delete.

## How

```bash
mem0-agent forget --query "<what they described>"   # find candidates
mem0-agent forget --id <memory_id> --confirm        # delete a specific one
```

1. Find the candidates and show them numbered, with their type and full text.
2. Ask which to remove. Never guess when more than one matches.
3. Delete the confirmed ids with `--confirm`.
4. Send negative feedback at the same time (the CLI does this) so the extraction pipeline
   learns from the rejection.

## Judgment

- If the memory is **wrong** rather than unwanted, prefer correcting it: store the correct
  fact with `/mem0:remember` and let the newer memory supersede the old one. Deletion loses
  the history; superseding keeps it.
- If the user is deleting something because it is **stale**, ask whether the replacement
  should be stored before you remove it.
- If they want to protect a memory instead of removing it, that's `/mem0:pin`.
- Deletes are soft on the platform: the record is hidden from all reads but not scrubbed
  from storage. Say so if the user is deleting for privacy reasons rather than tidiness.
