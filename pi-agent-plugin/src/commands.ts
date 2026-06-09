import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import type MemoryClient from "mem0ai";
import type { Mem0Config, ScopeContext, Scope } from "./types.ts";
import { DEFAULT_CUSTOM_CATEGORIES } from "./types.ts";
import { resolveSearchFilters, resolveAddParams } from "./memory/scoping.ts";
import { formatMemoryList, formatMemoryCompact, groupByCategory } from "./memory/formatting.ts";
import { DREAM_PROTOCOL } from "./dream/prompt.ts";
import { acquireDreamLock } from "./dream/index.ts";
import { CONFIG_DIR } from "./config/index.ts";

const ID_PATTERN = /^[0-9a-f-]{8,}$/i;

async function resolveMemoryId(
  mem0: MemoryClient,
  input: string,
  filters: Record<string, string>,
): Promise<string | null> {
  if (input.length >= 20) return input;
  const result = await mem0.getAll({ filters });
  const match = (result.results ?? []).find((m) => m.id.startsWith(input));
  return match?.id ?? null;
}

export function registerCommands(
  pi: ExtensionAPI,
  mem0: MemoryClient,
  config: Mem0Config,
  getScopeCtx: () => ScopeContext,
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
      const msg = (result as any).message ?? "Memory stored.";
      ctx.ui.notify(msg, "info");
    },
  });

  // ── /mem0-forget ────────────────────────────────────────────────────
  pi.registerCommand("mem0-forget", {
    description: "Search and delete memories by query or ID",
    handler: async (args, ctx) => {
      const query = args?.trim();
      if (!query) {
        ctx.ui.notify("Usage: /mem0-forget <query|id>", "warning");
        return;
      }

      const scopeCtx = getScopeCtx();
      const filters = resolveSearchFilters(config.defaultScope, scopeCtx);

      if (query.match(ID_PATTERN)) {
        const fullId = await resolveMemoryId(mem0, query, filters);
        if (!fullId) {
          ctx.ui.notify(`No memory found matching ID "${query}".`, "warning");
          return;
        }
        const result = await mem0.delete(fullId);
        ctx.ui.notify(result.message ?? `Deleted memory ${fullId.slice(0, 8)}.`, "info");
        return;
      }

      const result = await mem0.search(query, { filters });
      const memories = result.results ?? [];

      if (memories.length === 0) {
        ctx.ui.notify("No matching memories found.", "info");
        return;
      }

      const list = formatMemoryList(memories);
      pi.sendMessage({
        customType: "mem0-forget",
        content: `Found ${memories.length} matching memory(s):\n\n${list}\n\nUse /mem0-forget <memory_id> to delete a specific entry.`,
        display: true,
      });
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

      if (query.match(ID_PATTERN)) {
        const fullId = await resolveMemoryId(mem0, query, filters);
        if (!fullId) {
          pi.sendMessage({ customType: "mem0-search", content: `No memory found matching ID "${query}".`, display: true });
          return;
        }
        const mem = await mem0.get(fullId);
        pi.sendMessage({
          customType: "mem0-search",
          content: formatMemoryCompact(mem),
          display: true,
        });
        return;
      }

      const result = await mem0.search(query, { filters });
      const memories = result.results ?? [];

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
        ctx.ui.notify("Usage: /mem0-pin <query|id>", "warning");
        return;
      }

      const scopeCtx = getScopeCtx();
      const filters = resolveSearchFilters(config.defaultScope, scopeCtx);

      if (query.match(ID_PATTERN)) {
        const fullId = await resolveMemoryId(mem0, query, filters);
        if (!fullId) {
          ctx.ui.notify(`No memory found matching ID "${query}".`, "warning");
          return;
        }
        const mem = await mem0.get(fullId);
        const text = mem?.memory ?? "";
        if (!text.startsWith("[PINNED]")) {
          const addParams = resolveAddParams(config.defaultScope, scopeCtx);
          await mem0.add(
            [{ role: "user", content: `[PINNED] ${text}` }],
            { ...addParams, customCategories: DEFAULT_CUSTOM_CATEGORIES, infer: false },
          );
          await mem0.delete(fullId);
        }
        ctx.ui.notify(`Pinned memory ${fullId.slice(0, 8)}.`, "info");
        return;
      }

      const result = await mem0.search(query, { filters });
      const memories = result.results ?? [];

      if (memories.length === 0) {
        ctx.ui.notify("No matching memories found to pin.", "info");
        return;
      }

      const list = formatMemoryList(memories);
      pi.sendMessage({
        customType: "mem0-pin",
        content: `Found ${memories.length} match(es):\n\n${list}\n\nUse /mem0-pin <memory_id> to pin a specific memory.`,
        display: true,
      });
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

      pi.sendMessage({ customType: "mem0-status", content: lines.join("\n"), display: true });
    },
  });


}
