/** Conservative ceiling for OpenAI embedding models (8192 hard cap). */
export const DEFAULT_EMBED_TOKEN_LIMIT = 8000;

/**
 * Truncate text so it stays under an embedding model's token budget.
 * Uses a conservative ~4 chars/token heuristic (no tiktoken dependency in TS).
 */
export function truncateTextToTokenLimit(
  text: string,
  maxTokens: number = DEFAULT_EMBED_TOKEN_LIMIT,
): string {
  if (!text) {
    return text;
  }

  const charBudget = maxTokens * 4;
  if (text.length <= charBudget) {
    return text;
  }
  return text.slice(0, charBudget);
}
