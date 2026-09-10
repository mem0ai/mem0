import { buildSessionContext, convertToLlm, type ExtensionAPI } from "@earendil-works/pi-coding-agent";
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
