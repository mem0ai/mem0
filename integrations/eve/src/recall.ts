import type { SearchHit, MemoryStore } from "./store.js";

export interface RecallMessage {
  readonly id: string;
  readonly content: string;
}

export function formatRecallMessages(hits: readonly SearchHit[]): RecallMessage[] {
  return hits.flatMap((hit) => {
    const content = hit.memory.trim();
    return content.length > 0 ? [{ id: hit.id, content }] : [];
  });
}

export async function recallMemories(input: {
  store: MemoryStore;
  scopeKey: string;
  query: string;
  topK: number;
  threshold: number;
  rerank: boolean;
}): Promise<{ messages: RecallMessage[] } | null> {
  const query = input.query.trim();
  if (query.length === 0) {
    return null;
  }

  const { results } = await input.store.search(query, {
    filters: { user_id: input.scopeKey },
    topK: input.topK,
    threshold: input.threshold,
    rerank: input.rerank,
  });
  const messages = formatRecallMessages(results);
  return messages.length > 0 ? { messages } : null;
}
