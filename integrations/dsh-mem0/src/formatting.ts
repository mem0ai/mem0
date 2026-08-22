/**
 * Compact, token-cheap rendering of Mem0 results for the model context.
 *
 * Mirrors the format used by the sibling Mem0 plugins
 * (integrations/pi-agent-plugin/src/memory/formatting.ts) so a memory reads the
 * same way across every harness: `[category] text (age) [mem0:id]`. Dumping the
 * raw search envelope instead would spend most of the tokens on JSON scaffolding.
 */

export interface MemoryLike {
  id: string;
  memory?: string;
  categories?: string[];
  createdAt?: Date | string;
  score?: number;
}

export function formatAge(date: Date | string): string {
  const d = typeof date === "string" ? new Date(date) : date;
  const ms = Date.now() - d.getTime();
  const minutes = Math.floor(ms / 60_000);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function formatMemoryCompact(mem: MemoryLike): string {
  const cat = mem.categories?.[0] ?? "uncategorized";
  const age = mem.createdAt ? ` (${formatAge(mem.createdAt)})` : "";
  return `[${cat}] ${mem.memory ?? "(empty)"}${age} [mem0:${mem.id}]`;
}

export function formatMemoryList(memories: MemoryLike[]): string {
  if (memories.length === 0) return "No memories found.";
  return memories
    .map((m, i) => `${i + 1}. ${formatMemoryCompact(m)}`)
    .join("\n");
}

/**
 * One-line confirmation for a write. `client.add` returns the memories the
 * backend extracted from the turn (often zero when nothing new was learned),
 * so report the count rather than echoing the raw payload.
 */
export function formatAddResult(memories: MemoryLike[]): string {
  if (memories.length === 0) {
    return "Stored. No new distinct memory was extracted from that.";
  }
  const noun = memories.length === 1 ? "memory" : "memories";
  const lines = memories
    .map((m, i) => `${i + 1}. ${formatMemoryCompact(m)}`)
    .join("\n");
  return `Stored ${memories.length} ${noun}:\n${lines}`;
}
