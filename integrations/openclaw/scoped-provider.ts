import type { Mem0Provider } from "./types.ts";
import { isMemoryIdentitySelector, SenderIsolationError } from "./isolation.ts";

function assertSafeSearchFilters(filters: unknown): void {
  const pending = [filters];
  const visited = new Set<object>();
  while (pending.length > 0) {
    const value = pending.pop();
    if (!value || typeof value !== "object" || visited.has(value)) continue;
    visited.add(value);
    for (const [key, child] of Object.entries(value)) {
      if (key.split(".").some(isMemoryIdentitySelector)) {
        throw new SenderIsolationError(
          "identity fields are not allowed in advanced filters. Remove userId/user_id, " +
            "agentId/agent_id and runId/run_id selectors; the plugin supplies the scope.",
        );
      }
      pending.push(child);
    }
  }
}

/** Bind all provider operations, including ID-only tools, to one trusted scope. */
export function createSenderScopedProvider(
  provider: Mem0Provider,
  getUserId: () => string,
): Mem0Provider {
  const checkUserId = (userId: string) => {
    if (userId !== getUserId()) {
      throw new SenderIsolationError("userId and agentId overrides are not allowed.");
    }
  };
  const getOwnedMemory = async (memoryId: string) => {
    const userId = getUserId();
    const memory = await provider.get(memoryId);
    if (memory.id !== memoryId || memory.user_id !== userId) {
      throw new SenderIsolationError(
        "memory ownership could not be verified. Use an ID returned by this " +
          "sender's memory_search or memory_list; the backend must return user_id.",
      );
    }
    return memory;
  };

  return {
    async add(messages, options) {
      checkUserId(options.user_id);
      return provider.add(messages, options);
    },
    async search(query, options) {
      checkUserId(options.user_id);
      // The OSS SDK flattens AND with Object.assign, so AND alone cannot
      // protect the trusted namespace from a conflicting identity predicate.
      assertSafeSearchFilters(options.filters);
      return provider.search(query, options);
    },
    get: getOwnedMemory,
    async getAll(options) {
      checkUserId(options.user_id);
      return provider.getAll(options);
    },
    async update(memoryId, text) {
      await getOwnedMemory(memoryId);
      return provider.update(memoryId, text);
    },
    async delete(memoryId) {
      await getOwnedMemory(memoryId);
      return provider.delete(memoryId);
    },
    async deleteAll(userId) {
      checkUserId(userId);
      return provider.deleteAll(userId);
    },
    async history(memoryId) {
      await getOwnedMemory(memoryId);
      return provider.history(memoryId);
    },
  };
}
