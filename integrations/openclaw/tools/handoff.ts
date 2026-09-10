import type { OpenClawPluginApi } from "openclaw/plugin-sdk";
import { runNativeSession } from "../../agent-plugin-core/typescript/src/handoff.ts";

/** Native commands receive the trusted active transcript path from OpenClaw. */
export function registerHandoffCommand(api: OpenClawPluginApi): void {
  api.registerCommand?.({
    name: "mem0-handoff",
    description: "Continue this OpenClaw session in a new Codex task",
    acceptsArgs: true,
    requireAuth: true,
    async handler(ctx: { args?: string; sessionFile?: string }) {
      if (ctx.args?.trim() !== "codex") return { text: "Usage: /mem0-handoff codex" };
      if (!ctx.sessionFile) return { text: "The active OpenClaw transcript is unavailable. Run this command inside a session." };
      try {
        return { text: await runNativeSession(new URL("./session_handoff.py", import.meta.url), "openclaw", ctx.sessionFile) };
      } catch (error) {
        return { text: `Session handoff failed: ${error instanceof Error ? error.message : String(error)}` };
      }
    },
  });
}
