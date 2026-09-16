import { SEARCH_GUIDANCE } from "../../agent-plugin-core/typescript/src/search_guidance.ts";

export const MEMORY_POLICY = `<mem0-memory-policy>
You have persistent semantic memory via the mem0_memory tool, powered by Mem0. Relevant memories may be auto-injected under <mem0-relevant-memories>.

${SEARCH_GUIDANCE}

Be proactive about saving:
- Save important facts, preferences, goals, decisions, lessons learned, identity, relationships, and routines the user shares.

Scope (do not change unless explicitly asked):
- "project" (default): memories for this project — use for all normal queries
- "session": memories from this session only
- "global": all memories across projects — ONLY when the user explicitly asks for cross-project search

Memory persists across sessions and devices via Mem0's cloud.
</mem0-memory-policy>`;
