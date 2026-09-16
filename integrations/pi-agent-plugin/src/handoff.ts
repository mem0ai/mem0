import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { buildHandoffBundle, runHandoff, parseHandoffArgs, runHandoffAction } from "../../agent-plugin-core/typescript/src/handoff.ts";

export function registerHandoffCommand(pi: ExtensionAPI): void {
  pi.registerCommand("mem0-handoff", {
    description: "Save, list, or resume shared session handoff resources",
    handler: async (args, ctx) => {
      try {
        const {action, resource} = parseHandoffArgs(args);
        if (!ctx.isIdle()) throw new Error("Finish the current response before handing off this session.");
        const session = ctx.sessionManager;
        if (action !== "save") {
          const content = await runHandoffAction(new URL("./session_handoff.py", import.meta.url), action, session.getCwd(), resource);
          pi.sendMessage({customType: "mem0-handoff", content, display: true}, {triggerTurn: action === "resume"});
          return;
        }
        const [major, minor] = process.versions.node.split(".").map(Number);
        if (major < 22 || (major === 22 && minor < 19)) {
          throw new Error("Pi session handoff requires Node.js 22.19+ (the native Pi SDK requirement). Memory features remain available.");
        }
        const { buildSessionContext, convertToLlm } = await import("@earendil-works/pi-coding-agent");
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
