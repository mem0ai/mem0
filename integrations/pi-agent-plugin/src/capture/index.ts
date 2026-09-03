import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import type MemoryClient from "mem0ai";
import type { Mem0Config, ScopeContext } from "../types.ts";
import { DEFAULT_CUSTOM_CATEGORIES } from "../types.ts";
import { resolveAddParams } from "../memory/scoping.ts";
import { captureEvent } from "../telemetry.ts";
import { createMemoryLifecycle } from "../../../agent-plugins/core/typescript/src/lifecycle.ts";

export { extractConversation } from "../../../agent-plugins/core/typescript/src/lifecycle.ts";

export function setupAutoCapture(
  pi: ExtensionAPI,
  mem0: MemoryClient,
  config: Mem0Config,
  getScopeCtx: () => ScopeContext,
  telemetryCtx?: { apiKey?: string },
  lifecycle: ReturnType<typeof createMemoryLifecycle> = createMemoryLifecycle(),
): void {
  if (!config.autoCapture) return;

  pi.on("agent_end", async (event) => {
    const messages = event.messages ?? [];
    const conversation = lifecycle.prepareConversation(messages);
    if (conversation.length === 0) return;

    const scopeCtx = getScopeCtx();
    const addParams = resolveAddParams("project", scopeCtx);

    try {
      await mem0.add(conversation, {
        ...addParams,
        customCategories: DEFAULT_CUSTOM_CATEGORIES,
      });
      captureEvent("pi.capture.auto", { success: true, message_count: conversation.length }, telemetryCtx);
    } catch (err: unknown) {
      captureEvent("pi.capture.auto", {
        success: false,
        error_type: err instanceof Error ? err.name : "unknown",
      }, telemetryCtx);
      console.error("[mem0] auto-capture failed:", err);
    }
  });
}
