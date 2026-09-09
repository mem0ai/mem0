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
