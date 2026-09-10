import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { buildHandoffBundle, runHandoff } from "../../agent-plugin-core/typescript/src/handoff.ts";

export function registerHandoffCommand(pi: ExtensionAPI): void {
  pi.registerCommand("mem0-handoff", {
    description: "Continue this Pi session in a new Codex task",
    handler: async (args, ctx) => {
      if (args.trim() !== "codex") {
        ctx.ui.notify("Usage: /mem0-handoff codex", "warning");
        return;
      }
      try {
        if (!ctx.isIdle()) throw new Error("Finish the current response before handing off this session.");
        const [major, minor] = process.versions.node.split(".").map(Number);
        if (major < 22 || (major === 22 && minor < 19)) {
          throw new Error("Pi session handoff requires Node.js 22.19+ (the native Pi SDK requirement). Memory features remain available.");
        }
        const { buildSessionContext, convertToLlm } = await import("@earendil-works/pi-coding-agent");
        const session = ctx.sessionManager;
        const context = buildSessionContext(session.getEntries(), session.getLeafId());
        const bundle = await buildHandoffBundle({
          host: "pi-agent", session_id: session.getSessionId(),
          title: session.getSessionName() || `Pi session ${session.getSessionId()}`,
          cwd: session.getCwd(), path: session.getSessionFile(),
        }, convertToLlm(context.messages));
        const content = await runHandoff(new URL("./session_handoff.py", import.meta.url), bundle);
        pi.sendMessage({ customType: "mem0-handoff", content, display: true });
      } catch (error) {
        ctx.ui.notify(error instanceof Error ? error.message : String(error), "error");
      }
    },
  });
}
