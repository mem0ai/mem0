import { completedTurnMessages, type ConversationMessage } from "./messages.js";
import type { MemoryStore } from "./store.js";

export async function captureCompletedTurn(input: {
  store: MemoryStore;
  scopeKey: string;
  infer: boolean;
  metadata: Readonly<Record<string, unknown>>;
  messages: readonly ConversationMessage[];
  turnInput: readonly ConversationMessage[];
}): Promise<boolean> {
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
