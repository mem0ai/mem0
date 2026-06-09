import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import type MemoryClient from "mem0ai";
import type { Mem0Config, ScopeContext, Scope } from "./types.ts";
import { DEFAULT_CUSTOM_CATEGORIES } from "./types.ts";
import { resolveSearchFilters, resolveAddParams } from "./memory/scoping.ts";
import { formatMemoryList, formatMemoryCompact, groupByCategory } from "./memory/formatting.ts";
import { DREAM_PROTOCOL } from "./dream/prompt.ts";
import { acquireDreamLock } from "./dream/index.ts";
import { CONFIG_DIR } from "./config/index.ts";
import { captureCommandEvent } from "./telemetry.ts";

const UUID_PREFIX_PATTERN = /^[0-9a-f]{8}-[0-9a-f]/i;
const SHORT_ID_PATTERN = /^[0-9a-f]{8}$/i;

function looksLikeMemoryId(input: string): boolean {
  return UUID_PREFIX_PATTERN.test(input) || SHORT_ID_PATTERN.test(input);
}

async function expandShortId(
  mem0: MemoryClient,
  input: string,
  filters: Record<string, string>,
): Promise<string | null> {
  if (input.length >= 36) return input;
  const result = await mem0.getAll({ filters });
  const match = (result.results ?? []).find((m) => m.id.startsWith(input));
  return match?.id ?? null;
}

export function registerCommands(
  pi: ExtensionAPI,
  mem0: MemoryClient,
  config: Mem0Config,
  getScopeCtx: () => ScopeContext,
  telemetryCtx?: { apiKey?: string },
): void {
  // ── /mem0-remember ──────────────────────────────────────────────────
  pi.registerCommand("mem0-remember", {
    description: "Store a memory verbatim (no inference)",
    handler: async (args, ctx) => {
      const text = args?.trim();
      if (!text) {
        ctx.ui.notify("Usage: /mem0-remember <text>", "warning");
        return;
      }

      const scopeCtx = getScopeCtx();
      const addParams = resolveAddParams(config.defaultScope, scopeCtx);
      const result = await mem0.add(
        [{ role: "user", content: text }],
        { ...addParams, customCategories: DEFAULT_CUSTOM_CATEGORIES, infer: false },
      );
      const msg = (result as { message?: string }).message ?? "Memory stored.";
      captureCommandEvent("mem0-remember", {}, telemetryCtx);
      ctx.ui.notify(msg, "info");
    },
  });

  // ── /mem0-forget ────────────────────────────────────────────────────
  pi.registerCommand("mem0-forget", {
    description: "Delete memories matching a natural language query",
    handler: async (args, ctx) => {
      const query = args?.trim();
      if (!query) {
        ctx.ui.notify("Usage: /mem0-forget <query>", "warning");
        return;
      }

      const scopeCtx = getScopeCtx();
      const filters = resolveSearchFilters(config.defaultScope, scopeCtx);
      const result = await mem0.search(query, { filters });
      const memories = result.results ?? [];

      if (memories.length === 0) {
        captureCommandEvent("mem0-forget", { result_count: 0 }, telemetryCtx);
        ctx.ui.notify("No matching memories found.", "info");
        return;
      }

      if (memories.length === 1) {
        const target = memories[0];
        const confirmed = await ctx.ui.confirm(
          "Delete this memory?",
          formatMemoryCompact(target),
        );
        if (!confirmed) {
          ctx.ui.notify("Cancelled.", "info");
          return;
        }
        await mem0.delete(target.id);
        captureCommandEvent("mem0-forget", { deleted_count: 1 }, telemetryCtx);
        ctx.ui.notify(`Deleted: ${formatMemoryCompact(target)}`, "info");
        return;
      }

      captureCommandEvent("mem0-forget", { match_count: memories.length }, telemetryCtx);
      const list = formatMemoryList(memories);
      pi.sendMessage({
        customType: "mem0-forget",
        content: `Found ${memories.length} matching memories:\n\n${list}\n\nWhich memory should I delete? Tell me the number or describe which one.`,
        display: true,
      }, { triggerTurn: true });
    },
  });

  // ── /mem0-search ────────────────────────────────────────────────────
  pi.registerCommand("mem0-search", {
    description: "Semantic search across memories",
    handler: async (args, ctx) => {
      const query = args?.trim();
      if (!query) {
        ctx.ui.notify("Usage: /mem0-search <query>", "warning");
        return;
      }

      const scopeCtx = getScopeCtx();
      const filters = resolveSearchFilters(config.defaultScope, scopeCtx);

      if (looksLikeMemoryId(query)) {
        const fullId = await expandShortId(mem0, query, filters);
        if (!fullId) {
          captureCommandEvent("mem0-search", { result_count: 0, lookup: "id" }, telemetryCtx);
          pi.sendMessage({ customType: "mem0-search", content: `No memory found matching ID "${query}".`, display: true });
          return;
        }
        const mem = await mem0.get(fullId);
        captureCommandEvent("mem0-search", { result_count: 1, lookup: "id" }, telemetryCtx);
        pi.sendMessage({
          customType: "mem0-search",
          content: formatMemoryCompact(mem),
          display: true,
        });
        return;
      }

      const result = await mem0.search(query, { filters });
      const memories = result.results ?? [];

      captureCommandEvent("mem0-search", { result_count: memories.length }, telemetryCtx);
      pi.sendMessage({
        customType: "mem0-search",
        content: formatMemoryList(memories),
        display: true,
      });
    },
  });

  // ── /mem0-tour ──────────────────────────────────────────────────────
  pi.registerCommand("mem0-tour", {
    description: "Browse all memories grouped by category",
    handler: async (args, ctx) => {
      const raw = args?.trim().toLowerCase();
      const validScopes: Scope[] = ["project", "session", "global"];
      if (raw && !validScopes.includes(raw as Scope)) {
        ctx.ui.notify(`Invalid scope "${raw}". Must be one of: ${validScopes.join(", ")}`, "warning");
        return;
      }
      const scope: Scope = (raw as Scope) || config.defaultScope;
      const scopeCtx = getScopeCtx();
      const filters = resolveSearchFilters(scope, scopeCtx);
      const result = await mem0.getAll({ filters });
      const memories = result.results ?? [];

      if (memories.length === 0) {
        captureCommandEvent("mem0-tour", { memory_count: 0, scope }, telemetryCtx);
        pi.sendMessage({ customType: "mem0-tour", content: "No memories found.", display: true });
        return;
      }

      const groups = groupByCategory(memories);
      const lines: string[] = [`**Memory Tour** (${memories.length} total, scope: ${scope})`, ""];

      for (const [category, items] of groups) {
        lines.push(`### ${category} (${items.length})`);
        for (const m of items) {
          lines.push(`- ${formatMemoryCompact(m)}`);
        }
        lines.push("");
      }

      captureCommandEvent("mem0-tour", { memory_count: memories.length, scope }, telemetryCtx);
      pi.sendMessage({ customType: "mem0-tour", content: lines.join("\n"), display: true });
    },
  });

  // ── /mem0-dream ─────────────────────────────────────────────────────
  pi.registerCommand("mem0-dream", {
    description: "Consolidate memories — merge duplicates, prune stale entries, resolve contradictions",
    handler: async (_args, ctx) => {
      if (!acquireDreamLock(CONFIG_DIR)) {
        ctx.ui.notify("A dream consolidation is already in progress.", "warning");
        return;
      }

      captureCommandEvent("mem0-dream", {}, telemetryCtx);
      pi.sendMessage({ customType: "mem0-dream", content: DREAM_PROTOCOL, display: true }, { triggerTurn: true });
      ctx.ui.notify("Dream consolidation started.", "info");
    },
  });

  // ── /mem0-pin ───────────────────────────────────────────────────────
  pi.registerCommand("mem0-pin", {
    description: "Pin a memory to protect it from dream pruning",
    handler: async (args, ctx) => {
      const query = args?.trim();
      if (!query) {
        ctx.ui.notify("Usage: /mem0-pin <query>", "warning");
        return;
      }

      const scopeCtx = getScopeCtx();
      const filters = resolveSearchFilters(config.defaultScope, scopeCtx);
      const result = await mem0.search(query, { filters });
      const memories = result.results ?? [];

      if (memories.length === 0) {
        captureCommandEvent("mem0-pin", { result_count: 0 }, telemetryCtx);
        ctx.ui.notify("No matching memories found to pin.", "info");
        return;
      }

      if (memories.length === 1) {
        const target = memories[0];
        const text = target.memory ?? "";
        if (text.startsWith("[PINNED]")) {
          ctx.ui.notify("Already pinned.", "info");
          return;
        }
        const confirmed = await ctx.ui.confirm(
          "Pin this memory?",
          formatMemoryCompact(target),
        );
        if (!confirmed) {
          ctx.ui.notify("Cancelled.", "info");
          return;
        }
        const addParams = resolveAddParams(config.defaultScope, scopeCtx);
        await mem0.add(
          [{ role: "user", content: `[PINNED] ${text}` }],
          { ...addParams, customCategories: DEFAULT_CUSTOM_CATEGORIES, infer: false },
        );
        await mem0.delete(target.id);
        captureCommandEvent("mem0-pin", { pinned: true }, telemetryCtx);
        ctx.ui.notify(`Pinned: ${formatMemoryCompact(target)}`, "info");
        return;
      }

      captureCommandEvent("mem0-pin", { match_count: memories.length }, telemetryCtx);
      const list = formatMemoryList(memories);
      pi.sendMessage({
        customType: "mem0-pin",
        content: `Found ${memories.length} matches:\n\n${list}\n\nWhich memory should I pin? Tell me the number or describe which one.`,
        display: true,
      }, { triggerTurn: true });
    },
  });

  // ── /mem0-scope ─────────────────────────────────────────────────────
  pi.registerCommand("mem0-scope", {
    description: "Change default memory scope for this session (project, session, global)",
    handler: async (args, ctx) => {
      const scope = args?.trim().toLowerCase();
      const valid: Scope[] = ["project", "session", "global"];

      if (!scope) {
        ctx.ui.notify(`Current scope: ${config.defaultScope}. Usage: /mem0-scope <${valid.join("|")}>`, "info");
        return;
      }

      if (!valid.includes(scope as Scope)) {
        ctx.ui.notify(`Invalid scope "${scope}". Must be one of: ${valid.join(", ")}`, "warning");
        return;
      }

      config.defaultScope = scope as Scope;
      captureCommandEvent("mem0-scope", { scope }, telemetryCtx);
      ctx.ui.notify(`Default scope changed to "${scope}" for this session.`, "info");
    },
  });

  // ── /mem0-status ────────────────────────────────────────────────────
  pi.registerCommand("mem0-status", {
    description: "Show connection health, identity, project, and memory count",
    handler: async (_args, _ctx) => {
      const scopeCtx = getScopeCtx();
      const filters = resolveSearchFilters("project", scopeCtx);

      let count = 0;
      let connected = false;
      try {
        const result = await mem0.getAll({ filters });
        count = result.count ?? (result.results ?? []).length;
        connected = true;
      } catch {
        connected = false;
      }

      const lines = [
        "**Mem0 Status**",
        "",
        `- Connection: ${connected ? "connected" : "disconnected"}`,
        `- User: ${scopeCtx.userId}`,
        `- Project: ${scopeCtx.appId}`,
        `- Session: ${scopeCtx.runId}`,
        `- Default scope: ${config.defaultScope}`,
        `- Project memories: ${count}`,
        `- Auto-capture: ${config.autoCapture ? "on" : "off"}`,
        `- Dream: ${config.dream.enabled ? "enabled" : "disabled"}`,
      ];

      captureCommandEvent("mem0-status", { connected, memory_count: count }, telemetryCtx);
      pi.sendMessage({ customType: "mem0-status", content: lines.join("\n"), display: true });
    },
  });


}
