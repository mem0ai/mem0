interface MemoryLike {
  id: string;
  memory?: string;
  categories?: string[];
  createdAt?: Date;
}

export function formatAge(date: Date): string {
  const ms = Date.now() - date.getTime();
  const minutes = Math.floor(ms / 60_000);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function shortId(id: string): string {
  return id.slice(0, 8);
}

export function formatMemoryCompact(mem: MemoryLike): string {
  const cat = mem.categories?.[0] ?? "uncategorized";
  const age = mem.createdAt ? ` (${formatAge(mem.createdAt)})` : "";
  return `[${cat}] ${mem.memory ?? "(empty)"}${age} [mem0:${shortId(mem.id)}]`;
}

export function formatMemoryList(memories: MemoryLike[]): string {
  if (memories.length === 0) return "No memories found.";
  return memories
    .map((m, i) => `${i + 1}. ${formatMemoryCompact(m)}`)
    .join("\n");
}

export function groupByCategory(
  memories: MemoryLike[],
): Map<string, MemoryLike[]> {
  const groups = new Map<string, MemoryLike[]>();
  for (const m of memories) {
    const cat = m.categories?.[0] ?? "uncategorized";
    const list = groups.get(cat) ?? [];
    list.push(m);
    groups.set(cat, list);
  }
  return groups;
}
