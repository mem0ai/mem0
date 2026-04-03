/**
 * memory_get tool — extracted from index.ts registerTools().
 *
 * Retrieves a specific memory by its ID from Mem0.
 */

import { Type } from "@sinclair/typebox";
import type { ToolContext } from "./index.ts";

// ---------------------------------------------------------------------------
// Tool factory
// ---------------------------------------------------------------------------

/**
 * Creates the `memory_get` tool config object suitable for
 * `api.registerTool(config, { name })`.
 */
export function createMemoryGetTool(ctx: ToolContext) {
  const { provider } = ctx;

  return {
    name: "memory_get",
    label: "Memory Get",
    description: "Retrieve a specific memory by its ID from Mem0.",
    parameters: Type.Object({
      memoryId: Type.String({ description: "The memory ID to retrieve" }),
    }),

    async execute(_toolCallId: string, params: Record<string, unknown>) {
      const { memoryId } = params as { memoryId: string };

      try {
        const memory = await provider!.get(memoryId);

        return {
          content: [
            {
              type: "text",
              text: `Memory ${memory.id}:\n${memory.memory}\n\nCreated: ${memory.created_at ?? "unknown"}\nUpdated: ${memory.updated_at ?? "unknown"}`,
            },
          ],
          details: { memory },
        };
      } catch (err) {
        return {
          content: [
            {
              type: "text",
              text: `Memory get failed: ${String(err)}`,
            },
          ],
          details: { error: String(err) },
        };
      }
    },
  };
}
