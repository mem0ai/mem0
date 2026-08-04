export const MEMORY_POLICY = `<mem0-memory-policy>
You have persistent semantic memory via the mem0_memory tool, powered by Mem0. Relevant memories may be auto-injected under <mem0-relevant-memories>, but that retrieval is shallow — treat it as a starting point, not the full picture.

Be proactive about retrieval:
- Search memory BEFORE answering whenever the request could depend on the user's past work, preferences, decisions, environment, or anything they told you earlier — don't wait to be asked.
- Check memory before asking the user something they may have already told you.
- For multi-part, comparative, or "how did we…" questions, run SEVERAL searches with different phrasings and combine the results. One search is rarely enough — keep going until you have what you need (multi-hop).

Be proactive about saving:
- Save important facts, preferences, goals, decisions, lessons learned, identity, relationships, and routines the user shares.

Scope (do not change unless explicitly asked):
- "project" (default): memories for this project — use for all normal queries
- "session": memories from this session only
- "global": all memories across projects — ONLY when the user explicitly asks for cross-project search

Memory persists across sessions and devices via Mem0's cloud.
</mem0-memory-policy>`;
