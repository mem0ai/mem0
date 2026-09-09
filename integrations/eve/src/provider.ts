import { defineMemoryProvider, type MemoryProvider } from "eve/memory";
import { captureCompletedTurn } from "./capture.js";
import { errorMessage } from "./errors.js";
import { createIdempotencyGate } from "./idempotency.js";
import { lastUserText, type ConversationMessage } from "./messages.js";
import { resolveOptions, type Mem0ProviderOptions } from "./options.js";
import { recallMemories } from "./recall.js";
import { createMem0Store, type MemoryStore } from "./store.js";
import { createMem0Tools } from "./tools.js";

function asConversation(messages: readonly unknown[]): ConversationMessage[] {
  return messages.filter((message): message is ConversationMessage => {
    if (message === null || typeof message !== "object") {
      return false;
    }
    return (
      "role" in message && typeof (message as { role: unknown }).role === "string"
    );
  });
}

export function mem0Provider(options: Mem0ProviderOptions): MemoryProvider {
  const config = resolveOptions(options);
  const once = createIdempotencyGate();
  let storePromise: Promise<MemoryStore> | undefined;

  const getStore = async (): Promise<MemoryStore> => {
    if (config.store) {
      return config.store;
    }
    storePromise ??= createMem0Store({
      apiKey: config.apiKey,
      host: config.host,
    });
    return storePromise;
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
    const query = lastUserText(asConversation(querySource));

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
      if (context.abortSignal.aborted) {
        throw error;
      }
      console.error("[@mem0/eve] recall failed", {
        error: errorMessage(error),
        sessionId: context.session.id,
      });
      return null;
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
              try {
                const store = await getStore();
                await once(context.operationId, async () => {
                  await captureCompletedTurn({
                    store,
                    scopeKey: context.memory.scope.key,
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
              } catch (error) {
                if (context.abortSignal.aborted) {
                  throw error;
                }
                console.error("[@mem0/eve] capture failed", {
                  error: errorMessage(error),
                  sessionId: context.session.id,
                  turnId: context.turn.id,
                });
              }
            },
          },
        }
      : {}),
    async tools(context) {
      const store = await getStore();
      return createMem0Tools(store, context.memory.scope.key);
    },
  });
}
