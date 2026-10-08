import { completedTurnMessages, type ConversationMessage } from "./messages.js";
import type { MemoryStore, StoreMetadata } from "./store.js";

export async function captureCompletedTurn(input: {
  store: MemoryStore;
  scopeKey: string;
  operationId: string;
  infer: boolean;
  metadata: StoreMetadata;
  messages: readonly ConversationMessage[];
  turnInput: readonly ConversationMessage[];
}): Promise<boolean> {
  // Best-effort deduplication, not a guarantee. This lookup + add is not atomic,
  // and with infer:true the prior write can still be a PENDING event whose
  // memory is not yet visible here. So a restart during that window, or two
  // workers that both clear this check before either write, can capture the
  // same operation twice. The in-process gate in provider.ts narrows the common
  // case; eliminating it would need a backend-supported atomic idempotency key.
  const existing = await input.store.listByMetadata({
    userId: input.scopeKey,
    metadata: { operation_id: input.operationId },
  });
  if (existing.length > 0) {
    return false;
  }

  const messages = completedTurnMessages({
    messages: input.messages,
    turnInput: input.turnInput,
  });
  if (messages.length === 0) {
    return false;
  }

  await input.store.add(messages, {
    userId: input.scopeKey,
    infer: input.infer,
    metadata: input.metadata,
  });
  return true;
}
