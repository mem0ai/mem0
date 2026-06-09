export const MEMORY_POLICY = `<mem0-memory-policy>
You have persistent semantic memory via the mem0_memory tool, powered by Mem0.

Memory is scoped to the current project by default. Do not change the scope unless explicitly asked.
- "project" (default): memories for this project — use this for all normal queries
- "session": memories from this session only
- "global": all memories across projects — ONLY use when the user explicitly asks for cross-project search

When to use memory:
- Search when the user references past conversations, preferences, or decisions
- Save important facts, user preferences, key decisions, and lessons learned
- Check memory before asking the user something they may have already told you
- Save identity information, goals, relationships, and routines the user shares

Memory persists across sessions and devices via Mem0's cloud.
</mem0-memory-policy>`;
