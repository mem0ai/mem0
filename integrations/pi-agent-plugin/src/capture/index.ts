import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import type MemoryClient from "mem0ai";
import type { Mem0Config, ScopeContext } from "../types.ts";
import { PLATFORM_SOURCE } from "../attribution.ts";
import { captureEvent } from "../telemetry.ts";
import {
  createMemoryLifecycle,
  repoCaptureOptions,
  type ConversationMessage,
} from "../../../agent-plugin-core/typescript/src/lifecycle.ts";
import { resolveRepoContext } from "../../../agent-plugin-core/typescript/src/identity.ts";

export { extractConversation } from "../../../agent-plugin-core/typescript/src/lifecycle.ts";

export function setupAutoCapture(
  pi: ExtensionAPI,
  mem0: MemoryClient,
  config: Mem0Config,
  getScopeCtx: () => ScopeContext,
  telemetryCtx?: { apiKey?: string },
  lifecycle: ReturnType<typeof createMemoryLifecycle> = createMemoryLifecycle(),
): void {
  if (!config.autoCapture) return;

  function sender(cwd: string) {
    return async (messages: ConversationMessage[], reason: string) => {
      const { userId, runId } = getScopeCtx();
      try {
        await mem0.add(messages, {
          ...repoCaptureOptions(resolveRepoContext(cwd), userId, runId, "pi"),
          source: PLATFORM_SOURCE,
        } as any);
        captureEvent("pi.capture.auto", { success: true, reason, message_count: messages.length }, telemetryCtx);
      } catch (err: unknown) {
        captureEvent("pi.capture.auto", {
          success: false,
          reason,
          error_type: err instanceof Error ? err.name : "unknown",
        }, telemetryCtx);
        console.error("[mem0] auto-capture failed:", err);
      }
    };
  }

  pi.on("agent_end", async (event, ctx) => {
    const conversation = lifecycle.prepareConversation(event.messages ?? []);
    for (const message of conversation) {
      if (message.role === "user") lifecycle.recordUserPrompt(message.content);
    }
    const reply = conversation.filter((message) => message.role === "assistant").at(-1);
    if (reply) lifecycle.recordAssistantResponse(reply.content);
    await lifecycle.afterResponse(sender(ctx.cwd));
  });

  pi.on("session_before_compact", async (_event, ctx) => {
    await lifecycle.flush("pre-compact", sender(ctx.cwd));
  });

  pi.on("session_shutdown", async (_event, ctx) => {
    await lifecycle.end("session-end", sender(ctx.cwd));
  });
}
