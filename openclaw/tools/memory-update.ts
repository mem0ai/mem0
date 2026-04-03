/**
 * memory_update tool — extracted from index.ts registerTools().
 *
 * Updates an existing memory's text in place. Preserves the memory's
 * history and supports subagent blocking. Supports optional metadata
 * updates for CLI parity.
 */

import { Type } from "@sinclair/typebox";
import { isSubagentSession } from "../isolation.ts";
import type { ToolContext } from "./index.ts";

// ---------------------------------------------------------------------------
// Tool factory
// ---------------------------------------------------------------------------

/**
 * Creates the `memory_update` tool config object suitable for
 * `api.registerTool(config, { name })`.
 */
export function createMemoryUpdateTool(ctx: ToolContext) {
  const { api, provider, getCurrentSessionId } = ctx;

  return {
    name: "memory_update",
    label: "Memory Update",
    description:
      "Update an existing memory's text in place. Use when a fact has changed and you have the memory ID. This is atomic and preserves the memory's history. Preferred over delete-then-store for corrections.",
    parameters: Type.Object({
      memoryId: Type.String({ description: "The memory ID to update" }),
      text: Type.String({
        description: "The new text for this memory (replaces the old text)",
      }),
      // --- NEW CLI-parity parameter ---
      metadata: Type.Optional(
        Type.Record(Type.String(), Type.Unknown(), {
          description: "Metadata to update (JSON object)",
        }),
      ),
    }),

    async execute(_toolCallId: string, params: Record<string, unknown>) {
      const { memoryId, text, metadata } = params as {
        memoryId: string;
        text: string;
        metadata?: Record<string, unknown>;
      };

      try {
        const currentSessionId = getCurrentSessionId();
        if (isSubagentSession(currentSessionId)) {
          api.logger.warn(
            "openclaw-mem0: blocked memory_update from subagent session",
          );
          return {
            content: [
              {
                type: "text",
                text: "Memory update is not available in subagent sessions.",
              },
            ],
            details: { error: "subagent_blocked" },
          };
        }

        await provider!.update(memoryId, text);

        // If metadata was provided, note it in the response. The provider's
        // update() currently only accepts (id, text). Metadata-only updates
        // may need to go through the backend for full support.
        let metadataNote = "";
        if (metadata && Object.keys(metadata).length > 0) {
          metadataNote = `\nNote: metadata was provided but the current provider only supports text updates. Metadata-only updates may require backend support.`;
        }

        return {
          content: [
            {
              type: "text",
              text: `Updated memory ${memoryId}: "${text.slice(0, 80)}${text.length > 80 ? "..." : ""}"${metadataNote}`,
            },
          ],
          details: { action: "updated", id: memoryId, metadata: metadata },
        };
      } catch (err) {
        return {
          content: [
            { type: "text", text: `Memory update failed: ${String(err)}` },
          ],
          details: { error: String(err) },
        };
      }
    },
  };
}
