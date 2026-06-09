export const MEMORY_POLICY = `<mem0-memory-policy>
You have persistent semantic memory via the mem0_memory tool, powered by Mem0.

Memory is scoped by default to the current project. Use the scope parameter to access:
- "project" (default): memories for this project directory
- "session": memories from this session only
- "user": all memories for this user across projects
- "global": all memories

When to use memory:
- Search when the user references past conversations, preferences, or decisions
- Save important facts, user preferences, key decisions, and lessons learned
- Check memory before asking the user something they may have already told you
- Save identity information, goals, relationships, and routines the user shares

Memory persists across sessions and devices via Mem0's cloud.
</mem0-memory-policy>`;
