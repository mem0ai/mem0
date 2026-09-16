import { createReadStream } from "node:fs";
import { isAbsolute } from "node:path";
import { createInterface } from "node:readline";
import { Type } from "@sinclair/typebox";
import type { OpenClawPluginApi } from "openclaw/plugin-sdk";
import { parseHandoffArgs, runHandoffAction, runNativeSession } from "../../agent-plugin-core/typescript/src/handoff.ts";

async function sessionCwd(sessionFile: string): Promise<string> {
  const stream = createReadStream(sessionFile, {encoding: "utf8"});
  const lines = createInterface({input: stream, crlfDelay: Infinity});
  try {
    for await (const line of lines) {
      const header = JSON.parse(line);
      if (header.type !== "session" || typeof header.cwd !== "string" || !isAbsolute(header.cwd)) break;
      return header.cwd;
    }
    throw new Error("The active session's project directory is unavailable.");
  } finally { lines.close(); stream.destroy(); }
}

/** Commands use the native transcript; tools receive the native workspace. */
export function registerHandoffCommand(api: OpenClawPluginApi): void {
  const pending = new Map<string, string>();
  const script = new URL("./session_handoff.py", import.meta.url);
  api.on("before_prompt_build", (_event, ctx) => {
    const content = pending.get(ctx.sessionId);
    if (!content) return;
    pending.delete(ctx.sessionId);
    return {prependContext: content};
  });
  api.on("session_end", (event) => { pending.delete(event.sessionId); });
  api.registerTool((ctx) => ({
    name: "mem0_handoff",
    description: "List shared session resources for this project or resume one into this conversation as historical context. Use only when the user requests a handoff. To save this session use /mem0-handoff save.",
    parameters: Type.Object({
      action: Type.Union([Type.Literal("list"), Type.Literal("resume")]),
      resource: Type.Optional(Type.String({description: "Shared resource path required for resume"})),
    }),
    async execute(_id, params) {
      try {
        if (!ctx.workspaceDir) throw new Error("The active project directory is unavailable.");
        if (params.action !== "list" && params.action !== "resume") throw new Error("Choose list or resume.");
        const text = await runHandoffAction(script, params.action, ctx.workspaceDir, typeof params.resource === "string" ? params.resource : undefined);
        return {content: [{type: "text", text}]};
      } catch (error) {
        return {isError: true, content: [{type: "text", text: `Session handoff failed: ${error instanceof Error ? error.message : String(error)}`}]};
      }
    },
  }), {name: "mem0_handoff", optional: false});
  api.registerCommand?.({
    name: "mem0-handoff",
    description: "Save, list, or resume shared session handoff resources",
    acceptsArgs: true,
    requireAuth: true,
    async handler(ctx: {args?: string; sessionFile?: string; sessionId?: string}) {
      try {
        const {action, resource} = parseHandoffArgs(ctx.args);
        if (!ctx.sessionFile) throw new Error("The active OpenClaw transcript is unavailable. Run this command inside a session.");
        if (action === "save") return {text: await runNativeSession(script, "openclaw", ctx.sessionFile)};
        if (action === "resume" && !ctx.sessionId) throw new Error("The active session identity is unavailable; use the mem0_handoff tool to resume.");
        const content = await runHandoffAction(script, action, await sessionCwd(ctx.sessionFile), resource);
        if (action === "list") return {text: content};
        pending.set(ctx.sessionId!, content);
        return {text: "Shared session context loaded. Send your next message to continue from it in this session."};
      } catch (error) {
        return {text: `Session handoff failed: ${error instanceof Error ? error.message : String(error)}`};
      }
    },
  });
}
