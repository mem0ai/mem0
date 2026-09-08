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
 * One-line confirmation for a write.
 *
 * `client.add` hits the async `/v3/memories/add/` endpoint, which returns
 * `{ event_id, status: "PENDING" }` — extraction runs server-side *after* the
 * call returns, so the extracted memories are not in this response. Report the
 * write as queued in that case; only render a list when the backend actually
 * returns memories (older / OSS shapes).
 */
export function formatAddResult(result: unknown): string {
  const items: MemoryLike[] = Array.isArray(result)
    ? (result as MemoryLike[])
    : ((result as { results?: MemoryLike[] } | null)?.results ??
      (result ? [result as MemoryLike] : []));

  const pending = items.find(
    (r) => (r as { status?: string }).status === "PENDING",
  ) as { eventId?: string; event_id?: string } | undefined;
  if (pending) {
    // The SDK camel-cases response keys (event_id -> eventId); accept either.
    const id = pending.eventId ?? pending.event_id;
    const evt = id ? ` (event ${id})` : "";
    return `Memory queued for background extraction${evt}; it will be searchable shortly.`;
  }

  if (items.length === 0) return "Memory stored.";
  const noun = items.length === 1 ? "memory" : "memories";
  return `Stored ${items.length} ${noun}:\n${formatMemoryList(items)}`;
}
