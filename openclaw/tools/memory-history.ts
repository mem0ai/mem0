import { Type } from "@sinclair/typebox";
import type { ToolDeps } from "./index.ts";

export function createMemoryHistoryTool(deps: ToolDeps) {
  const { provider } = deps;

  return {
    name: "memory_history",
    label: "Memory History",
    description: "View the edit history of a specific memory.",
    parameters: Type.Object({
      memoryId: Type.String({ description: "The memory ID to view history for" }),
    }),

    async execute(_toolCallId: string, params: Record<string, unknown>) {
      const { memoryId } = params as { memoryId: string };
      try {
        const history = await provider.history(memoryId);
        if (!history || history.length === 0) {
          return { content: [{ type: "text", text: `No history found for memory ${memoryId}.` }], details: { count: 0 } };
        }
        const text = history.map((h, i) =>
          `${i + 1}. [${h.event}] ${h.created_at}\n   Old: ${h.old_memory || "(none)"}\n   New: ${h.new_memory || "(none)"}`
        ).join("\n\n");
        return {
          content: [{ type: "text", text: `History for memory ${memoryId} (${history.length} entries):\n\n${text}` }],
          details: { count: history.length, history },
        };
      } catch (err) {
        return { content: [{ type: "text", text: `Memory history failed: ${String(err)}` }], details: { error: String(err) } };
      }
    },
  };
}
