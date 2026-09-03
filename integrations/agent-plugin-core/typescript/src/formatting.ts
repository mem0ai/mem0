export interface MemoryLike {
  id: string;
  memory?: string;
  categories?: string[];
  createdAt?: Date | string;
}

export const MAX_OUTPUT_LINES = 200;
export const MAX_OUTPUT_CHARS = 50_000;
export const MAX_OUTPUT_BYTES = MAX_OUTPUT_CHARS;

export function formatAge(date: Date | string): string {
  const minutes = Math.floor((Date.now() - new Date(date).getTime()) / 60_000);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return hours < 24 ? `${hours}h ago` : `${Math.floor(hours / 24)}d ago`;
}

export function formatMemoryCompact(memory: MemoryLike): string {
  const category = memory.categories?.[0] ?? "uncategorized";
  const age = memory.createdAt ? ` (${formatAge(memory.createdAt)})` : "";
  return `[${category}] ${memory.memory ?? "(empty)"}${age} [mem0:${memory.id}]`;
}

export function formatMemoryList(memories: MemoryLike[]): string {
  return memories.length
    ? memories.map((memory, index) => `${index + 1}. ${formatMemoryCompact(memory)}`).join("\n")
    : "No memories found.";
}

export function formatAddResult(result: unknown): string {
  const items: MemoryLike[] = Array.isArray(result)
    ? result
    : ((result as { results?: MemoryLike[] } | null)?.results ?? (result ? [result as MemoryLike] : []));
  const pending = items.find((item) => (item as { status?: string }).status === "PENDING") as
    | { eventId?: string; event_id?: string }
    | undefined;
  if (pending) {
    const id = pending.eventId ?? pending.event_id;
    return `Memory queued for background extraction${id ? ` (event ${id})` : ""}; it will be searchable shortly.`;
  }
  if (!items.length) return "Memory stored.";
  return `Stored ${items.length} ${items.length === 1 ? "memory" : "memories"}:\n${formatMemoryList(items)}`;
}

export function groupByCategory(memories: MemoryLike[]): Map<string, MemoryLike[]> {
  const groups = new Map<string, MemoryLike[]>();
  for (const memory of memories) {
    const category = memory.categories?.[0] ?? "uncategorized";
    groups.set(category, [...(groups.get(category) ?? []), memory]);
  }
  return groups;
}

export function truncateOutput(
  text: string,
  maxChars = MAX_OUTPUT_CHARS,
  maxLines = MAX_OUTPUT_LINES,
): string {
  const lines = text.split("\n");
  if (lines.length <= maxLines && text.length <= maxChars) return text;
  const kept = lines.slice(0, maxLines);
  let result = kept.join("\n");
  const charCapped = result.length > maxChars;
  if (charCapped) result = result.slice(0, maxChars);
  const reasons = [];
  if (kept.length < lines.length) reasons.push(`showing ${kept.length} of ${lines.length} lines`);
  if (charCapped) reasons.push(`cut at ${Math.floor(maxChars / 1000)}KB`);
  return `${result}\n\n[Output truncated: ${reasons.join(", ")}]`;
}
