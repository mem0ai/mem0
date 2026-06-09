import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import type MemoryClient from "mem0ai";
import type { Mem0Config, ScopeContext } from "../types.ts";
import { DEFAULT_CUSTOM_CATEGORIES } from "../types.ts";
import { resolveAddParams } from "../memory/scoping.ts";
import { captureEvent } from "../telemetry.ts";

interface MessageLike {
  role: string;
  content?: unknown;
}

function extractText(content: unknown): string | null {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    const texts = content
      .filter((b: any) => b.type === "text" && typeof b.text === "string")
      .map((b: any) => b.text);
    return texts.length > 0 ? texts.join("\n") : null;
  }
  return null;
}

export function extractConversation(
  messages: MessageLike[],
): Array<{ role: "user" | "assistant"; content: string }> {
  const result: Array<{ role: "user" | "assistant"; content: string }> = [];

  for (const msg of messages) {
    if (msg.role !== "user") continue;
    const text = extractText(msg.content);
    if (!text) continue;
    result.push({ role: "user", content: text });
  }

  return result;
}

export function setupAutoCapture(
  pi: ExtensionAPI,
  mem0: MemoryClient,
  config: Mem0Config,
  getScopeCtx: () => ScopeContext,
  telemetryCtx?: { apiKey?: string },
): void {
  if (!config.autoCapture) return;

  pi.on("agent_end", async (event) => {
    const messages = event.messages ?? [];
    const conversation = extractConversation(messages);
    if (conversation.length === 0) return;

    const scopeCtx = getScopeCtx();
    const addParams = resolveAddParams("project", scopeCtx);

    mem0
      .add(conversation, {
        ...addParams,
        customCategories: DEFAULT_CUSTOM_CATEGORIES,
      })
      .then(() => {
        captureEvent("pi.capture.auto", { success: true, message_count: conversation.length }, telemetryCtx);
      })
      .catch((err: unknown) => {
        captureEvent("pi.capture.auto", { success: false, error: String(err) }, telemetryCtx);
        console.error("[mem0] auto-capture failed:", err);
      });
  });
}
