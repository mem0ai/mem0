// Why an embed failed: retry on "provider", fix config/input on "validation".
export type EmbeddingErrorClass = "provider" | "validation" | "unknown";

// Thrown by add() when some texts fail to embed; the rest are still persisted.
export class EmbeddingError extends Error {
  public readonly failedTexts: string[];
  // Memories persisted by this add() call (after dedup), before the throw.
  public readonly persistedCount: number;
  public readonly errorClass: EmbeddingErrorClass;

  constructor(
    failedTexts: string[],
    persistedCount: number,
    errorClass: EmbeddingErrorClass = "unknown",
  ) {
    super(
      `Failed to embed ${failedTexts.length} memory text(s); ` +
        `${persistedCount} memory(ies) were persisted (errorClass=${errorClass}). ` +
        `Inspect 'failedTexts' to retry the dropped memories.`,
    );
    this.name = "EmbeddingError";
    this.failedTexts = failedTexts;
    this.persistedCount = persistedCount;
    this.errorClass = errorClass;
    Object.setPrototypeOf(this, EmbeddingError.prototype);
  }
}

// When several embeds fail, keep the most actionable class: provider (retryable)
// beats validation beats unknown.
export function mergeEmbeddingErrorClass(
  a: EmbeddingErrorClass,
  b: EmbeddingErrorClass,
): EmbeddingErrorClass {
  const rank = { provider: 2, validation: 1, unknown: 0 };
  return rank[b] > rank[a] ? b : a;
}

// Guess why an embed() call failed from its message/status.
export function classifyEmbeddingError(err: unknown): EmbeddingErrorClass {
  const msg = (
    err instanceof Error ? err.message : String(err ?? "")
  ).toLowerCase();
  const status = (err as any)?.status ?? (err as any)?.statusCode;

  if (
    status === 429 ||
    (typeof status === "number" && status >= 500) ||
    /rate.?limit|too many requests|timeout|timed out|econnreset|etimedout|socket hang up|network|503|502|504|429|temporarily unavailable/.test(
      msg,
    )
  ) {
    return "provider";
  }
  if (
    /dimension|nan|invalid|malformed|empty|length|shape|expected .* got|validation/.test(
      msg,
    )
  ) {
    return "validation";
  }
  return "unknown";
}
