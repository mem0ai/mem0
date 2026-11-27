import { defineMemoryProvider, type MemoryProvider } from "eve/memory";
import { captureCompletedTurn } from "./capture.js";
import { isSetupError, logProviderError } from "./errors.js";
import { createIdempotencyGate } from "./idempotency.js";
import { lastUserText, type ConversationMessage } from "./messages.js";
import { resolveOptions, type Mem0ProviderOptions } from "./options.js";
import { recallMemories } from "./recall.js";
import { createLazyStore, createMem0Store, type MemoryStore } from "./store.js";
import { createMem0Tools } from "./tools.js";

function asConversation(messages: readonly unknown[]): ConversationMessage[] {
  return messages.filter((message): message is ConversationMessage => {
    if (message === null || typeof message !== "object") {
      return false;
    }
    return (
      "role" in message &&
      typeof (message as { role: unknown }).role === "string" &&
      "content" in message
    );
  });
}

export function mem0Provider(options: Mem0ProviderOptions): MemoryProvider {
  const config = resolveOptions(options);
  const once = createIdempotencyGate();
  const loadRemoteStore = createLazyStore(async () => {
    if (!config.apiKey) {
      throw new Error("Mem0 API key cannot be empty");
    }
    return createMem0Store({
      apiKey: config.apiKey,
      host: config.host,
    });
  });

  const getStore = async (): Promise<MemoryStore> => {
    if (config.store) {
      return config.store;
    }
    return loadRemoteStore();
  };

  const recall = async (context: {
    abortSignal: AbortSignal;
    messages: readonly unknown[];
    session: { id: string };
    memory: { scope: { key: string } };
    turn?: { input: readonly unknown[] } | null;
  }) => {
    if (!config.autoSearch.enabled) {
      return null;
    }

    const querySource = context.turn?.input ?? context.messages;
    const conversation = asConversation(querySource);
    if (querySource.length > 0 && conversation.length === 0) {
      console.error("[@mem0/eve] dropped all recall messages; no searchable user text", {
        sessionId: context.session.id,
      });
    }
    const query = lastUserText(conversation);

    try {
      const store = await getStore();
      return await recallMemories({
        store,
        scopeKey: context.memory.scope.key,
        query,
        topK: config.topK,
        threshold: config.threshold,
        rerank: config.rerank,
      });
    } catch (error) {
      if (context.abortSignal.aborted || isSetupError(error)) {
        throw error;
      }
      logProviderError("recall failed", error, {
        sessionId: context.session.id,
      });
      throw error;
    }
  };

  return defineMemoryProvider({
    recall: {
      "turn.started": recall,
      "compaction.completed": recall,
    },
    ...(config.capture.enabled
      ? {
          capture: {
            async "turn.completed"(context) {
              const store = await getStore();
              await once(context.operationId, async () => {
                await captureCompletedTurn({
                  store,
                  scopeKey: context.memory.scope.key,
                  operationId: context.operationId,
                  infer: config.infer,
                  metadata: {
                    ...config.metadata,
                    source: "eve",
                    operation_id: context.operationId,
                    session_id: context.session.id,
                    slot: context.memory.slot,
                  },
                  messages: asConversation(context.messages),
                  turnInput: asConversation(context.turn.input),
                });
              });
            },
          },
        }
      : {}),
    async tools(context) {
      const store = await getStore();
      return createMem0Tools(store, context.memory.scope.key, {
        topK: config.topK,
        threshold: config.threshold,
        rerank: config.rerank,
        infer: config.infer,
      });
    },
  });
}
