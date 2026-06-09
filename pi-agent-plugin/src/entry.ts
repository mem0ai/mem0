import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import MemoryClient from "mem0ai";
import { loadConfig, CONFIG_DIR } from "./config/index.ts";
import { detectAppId, detectRunId, resolveSearchFilters } from "./memory/scoping.ts";
import { registerMemoryTool } from "./memory/tools.ts";
import { registerCommands } from "./commands.ts";
import { setupAutoCapture } from "./capture/index.ts";
import { MEMORY_POLICY } from "./prompt.ts";
import { DREAM_PROTOCOL } from "./dream/prompt.ts";
import {
  incrementSessionCount,
  checkCheapGates,
  checkMemoryGate,
  acquireDreamLock,
  releaseDreamLock,
  recordDreamCompletion,
} from "./dream/index.ts";
import { captureEvent } from "./telemetry.ts";
import * as os from "node:os";
import type { ScopeContext } from "./types.ts";

export default function mem0Extension(pi: ExtensionAPI): void {
  const config = loadConfig();

  if (!config.apiKey) {
    console.warn("[mem0] No API key found. Set MEM0_API_KEY or add apiKey to ~/.pi/agent/mem0-config.json. Extension disabled.");
    return;
  }

  const mem0 = new MemoryClient({ apiKey: config.apiKey });

  const scopeCtx: ScopeContext = {
    userId: config.userId || process.env.USER || process.env.USERNAME || (() => { try { return os.userInfo().username; } catch { return "default"; } })(),
    appId: detectAppId(process.cwd()),
    runId: "unknown",
  };

  function getScopeCtx(): ScopeContext {
    return scopeCtx;
  }

  const telemetryCtx = { apiKey: config.apiKey };

  // ── Register tool + commands + auto-capture ─────────────────────────
  registerMemoryTool(pi, mem0, config, getScopeCtx, telemetryCtx);
  registerCommands(pi, mem0, config, getScopeCtx, telemetryCtx);
  setupAutoCapture(pi, mem0, config, getScopeCtx, telemetryCtx);

  captureEvent("pi.plugin.registered", {
    auto_capture: config.autoCapture,
    dream_enabled: config.dream.enabled,
    default_scope: config.defaultScope,
  }, telemetryCtx);

  // ── session_start: detect project + session, reconstruct scope ──────
  pi.on("session_start", async (_event, ctx) => {
    scopeCtx.appId = detectAppId(ctx.cwd);

    const sessionFile = ctx.sessionManager?.getSessionFile?.();
    scopeCtx.runId = detectRunId(sessionFile);

    if (config.userId) {
      scopeCtx.userId = config.userId;
    }

    if (config.dream.enabled) {
      incrementSessionCount(CONFIG_DIR, scopeCtx.runId);
    }

    captureEvent("pi.session.start", {}, telemetryCtx);
  });

  // ── before_agent_start: append memory policy + auto-dream trigger ───
  let dreamTriggered = false;

  pi.on("before_agent_start", async (event, _ctx) => {
    let extra = MEMORY_POLICY;

    if (config.dream.enabled && config.dream.auto && !dreamTriggered) {
      const gates = checkCheapGates(CONFIG_DIR, config.dream);
      if (gates.proceed) {
        try {
          const filters = resolveSearchFilters("project", scopeCtx);
          const result = await mem0.getAll({ filters });
          const count = result.count ?? (result.results ?? []).length;
          const memGate = checkMemoryGate(count, config.dream);

          if (memGate.pass && acquireDreamLock(CONFIG_DIR)) {
            dreamTriggered = true;
            extra += "\n\n" + DREAM_PROTOCOL;
            captureEvent("pi.dream.triggered", { memory_count: count }, telemetryCtx);
          }
        } catch {
          // Memory count check failed — skip dream this turn
        }
      }
    }

    return {
      systemPrompt: (event.systemPrompt ?? "") + "\n\n" + extra,
    };
  });

  // ── agent_end: dream completion check ───────────────────────────────
  pi.on("agent_end", async (event) => {
    if (!dreamTriggered) return;

    const messages = event.messages ?? [];
    const hadWriteAction = messages.some((m) => {
      if (m.role !== "assistant") return false;
      const content = Array.isArray(m.content) ? m.content : [];
      return content.some(
        (block: any) =>
          block.type === "tool_use" &&
          block.name === "mem0_memory" &&
          ["add", "delete", "delete_all"].includes(block.input?.action),
      );
    });

    if (hadWriteAction) {
      recordDreamCompletion(CONFIG_DIR);
      captureEvent("pi.dream.completed", {}, telemetryCtx);
    }

    releaseDreamLock(CONFIG_DIR);
    dreamTriggered = false;
  });

  // ── session_shutdown: release dream lock if still held ──────────────
  pi.on("session_shutdown", async () => {
    captureEvent("pi.session.stop", {}, telemetryCtx);
    if (dreamTriggered) {
      releaseDreamLock(CONFIG_DIR);
      dreamTriggered = false;
    }
  });
}
