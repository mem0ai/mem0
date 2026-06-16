import { Type } from "@sinclair/typebox";
import { isSubagentSession } from "../isolation.ts";
import type { ToolDeps } from "./index.ts";

export function createMemoryUpdateTool(deps: ToolDeps) {
  const { api, provider, getCurrentSessionId } = deps;

  return {
    name: "memory_update",
    label: "Memory Update",
    description: "Update an existing memory's text in place. Atomic and preserves history.",
    parameters: Type.Object({
      memoryId: Type.String({ description: "The memory ID to update" }),
      text: Type.String({ description: "The new text (replaces old)" }),
    }),

    async execute(_toolCallId: string, params: Record<string, unknown>) {
      const { memoryId, text } = params as { memoryId: string; text: string };
      const start = Date.now();
      try {
        if (isSubagentSession(getCurrentSessionId())) {
          return { content: [{ type: "text", text: "Memory update is not available in subagent sessions." }], details: { error: "subagent_blocked" } };
        }
        await provider.update(memoryId, text);
        deps.captureToolEvent("memory_update", { success: true, latency_ms: Date.now() - start });
        return {
          content: [{ type: "text", text: `Updated memory ${memoryId}: "${text.slice(0, 80)}${text.length > 80 ? "..." : ""}"` }],
          details: { action: "updated", id: memoryId },
        };
      } catch (err) {
        deps.captureToolEvent("memory_update", { success: false, latency_ms: Date.now() - start, error: String(err) });
        return { content: [{ type: "text", text: `Memory update failed: ${String(err)}` }], details: { error: String(err) } };
      }
    },
  };
}
