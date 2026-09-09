const DEFAULT_LIMIT = 256;

export function createIdempotencyGate(limit = DEFAULT_LIMIT) {
  const seen = new Map<string, Promise<void>>();

  return function once(operationId: string, work: () => Promise<void>): Promise<void> {
    const existing = seen.get(operationId);
    if (existing) {
      return existing;
    }

    const pending = work().catch((error: unknown) => {
      seen.delete(operationId);
      throw error;
    });

    seen.set(operationId, pending);
    if (seen.size > limit) {
      const oldest = seen.keys().next().value;
      if (oldest && oldest !== operationId) {
        seen.delete(oldest);
      }
    }
    return pending;
  };
}
