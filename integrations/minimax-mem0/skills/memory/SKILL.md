---
name: memory
description: Use Mem0 to persist and recall long-term memory across sessions - the user's preferences, decisions, project context, and durable facts.
---

You have access to Mem0 long-term memory through the `mem0` MCP server. Use it so the
user does not have to repeat themselves across sessions.

## When to recall (search memory)

At the start of a task, and whenever the user references something they expect you to
already know ("my project", "like last time", "the usual"), search memory before asking.

- Call the memory search tool with a short natural-language query describing what you
  need (e.g. "preferred language and package manager", "deployment process").
- Use the returned memories as context. Do not announce that you searched; just apply
  what you found.
- If nothing relevant comes back, proceed and ask the user only for what is missing.

## When to save (add memory)

Save durable facts as they come up, without being asked:

- Stated preferences ("I use pnpm", "always use TypeScript", "no comments in code").
- Decisions and conventions ("we deploy on Fridays", "the API base is X").
- Stable facts about the user, their team, or their project (stack, roles, goals).

Do not save transient or trivial details (a one-off value, a temporary path, secrets,
or anything the user would not want remembered). Save one clear fact per memory, phrased
so it makes sense on its own later.

## When to update or delete

If a new statement contradicts something you recalled, update that memory rather than
adding a duplicate. If the user says to forget something, delete it.

## Boundaries

- Never store secrets, credentials, API keys, or sensitive personal data.
- Memory is scoped to the connected Mem0 account; keep one user's memories to that user.
- Prefer recalling silently over interrupting the user to confirm what you already know.
