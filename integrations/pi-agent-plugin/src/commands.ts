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

const SEARCH_TOP_K = 10;

export function registerCommands(
  pi: ExtensionAPI,
  mem0: MemoryClient,
  config: Mem0Config,
  getScopeCtx: () => ScopeContext,
  telemetryCtx?: { apiKey?: string },
): void {
  const sendFeedback = (customType: string, content: string): void => {
    pi.sendMessage({ customType, content, display: true });
  };

  const pluralize = (n: number, one: string, many: string): string =>
    `${n} ${n === 1 ? one : many}`;

  const searchMemories = async (query: string, scope: Scope) => {
    const filters = resolveSearchFilters(scope, getScopeCtx());
    const result = await mem0.search(query, {
      filters,
      threshold: config.searchThreshold,
      topK: SEARCH_TOP_K,
      rerank: true,
    });
    return result.results ?? [];
  };

  pi.registerCommand("mem0-remember", {
    description: "Store a memory verbatim (no inference)",
    handler: async (args, ctx) => {
      const text = args?.trim();
      if (!text) {
        ctx.ui.notify("Usage: /mem0-remember <text>", "warning");
        return;
      }

      const addParams = resolveAddParams(config.defaultScope, getScopeCtx());
      const result = await mem0.add(
        [{ role: "user", content: text }],
        { ...addParams, customCategories: DEFAULT_CUSTOM_CATEGORIES, infer: false },
      );
      captureCommandEvent("mem0-remember", {}, telemetryCtx);

      const storedItems = (Array.isArray(result) ? result : [])
        .map((m) => (m as { memory?: string }).memory)
        .filter((m): m is string => Boolean(m));
      const items = storedItems.length > 0 ? storedItems : [text];
      sendFeedback(
        "mem0-remember",
        [`**Stored to ${config.defaultScope} memory**`, ...items.map((m) => `- ${m}`)].join("\n"),
      );
    },
  });

  pi.registerCommand("mem0-forget", {
    description: "Delete memories matching a natural language query",
    handler: async (args, ctx) => {
      const query = args?.trim();
      if (!query) {
        ctx.ui.notify("Usage: /mem0-forget <query>", "warning");
        return;
      }

      const memories = await searchMemories(query, config.defaultScope);

      if (memories.length === 0) {
        captureCommandEvent("mem0-forget", { result_count: 0 }, telemetryCtx);
        sendFeedback("mem0-forget", `**No matches for "${query}"** — nothing to forget.`);
        return;
      }

      const forgotten = (mem: Parameters<typeof formatMemoryCompact>[0]) => {
        captureCommandEvent("mem0-forget", { deleted_count: 1 }, telemetryCtx);
        sendFeedback(
          "mem0-forget",
          [`**Forgotten from ${config.defaultScope} memory**`, `- ${formatMemoryCompact(mem)}`].join("\n"),
        );
      };

      if (memories.length === 1) {
        const target = memories[0];
        const confirmed = await ctx.ui.confirm("Delete this memory?", formatMemoryCompact(target));
        if (!confirmed) {
          sendFeedback("mem0-forget", "**Cancelled** — no memories deleted.");
          return;
        }
        await mem0.delete(target.id);
        forgotten(target);
        return;
      }

      const labels = memories.map((m) => formatMemoryCompact(m));
      const selected = await ctx.ui.select(
        `Found ${pluralize(memories.length, "match", "matches")} for "${query}" — which should I delete?`,
        labels,
      );
      if (!selected) {
        sendFeedback("mem0-forget", "**Cancelled** — no memories deleted.");
        return;
      }
      const idx = labels.indexOf(selected);
      if (idx < 0) return;
      const target = memories[idx];
      await mem0.delete(target.id);
      forgotten(target);
    },
  });

  pi.registerCommand("mem0-search", {
    description: "Semantic search across memories",
    handler: async (args, ctx) => {
      const query = args?.trim();
      if (!query) {
        ctx.ui.notify("Usage: /mem0-search <query>", "warning");
        return;
      }

      const memories = await searchMemories(query, config.defaultScope);
      captureCommandEvent("mem0-search", { result_count: memories.length }, telemetryCtx);

      if (memories.length === 0) {
        sendFeedback("mem0-search", `**No matches for "${query}"** · ${config.defaultScope} scope`);
        return;
      }

      sendFeedback(
        "mem0-search",
        [
          `**${pluralize(memories.length, "match", "matches")} for "${query}"** · ${config.defaultScope} scope`,
          "",
          formatMemoryList(memories),
        ].join("\n"),
      );
    },
  });

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
      const filters = resolveSearchFilters(scope, getScopeCtx());
      const result = await mem0.getAll({ filters });
      const memories = result.results ?? [];

      if (memories.length === 0) {
        captureCommandEvent("mem0-tour", { memory_count: 0, scope }, telemetryCtx);
        sendFeedback("mem0-tour", `**No memories in ${scope} scope yet** — store one with \`/mem0-remember\`.`);
        return;
      }

      const groups = groupByCategory(memories);
      const lines: string[] = [
        `**Memory tour** · ${pluralize(memories.length, "memory", "memories")} · ${scope} scope`,
        "",
      ];

      for (const [category, items] of groups) {
        lines.push(`### ${category} (${items.length})`);
        for (const m of items) {
          lines.push(`- ${formatMemoryCompact(m)}`);
        }
        lines.push("");
      }

      captureCommandEvent("mem0-tour", { memory_count: memories.length, scope }, telemetryCtx);
      sendFeedback("mem0-tour", lines.join("\n"));
    },
  });

  pi.registerCommand("mem0-dream", {
    description: "Consolidate memories — merge duplicates, prune stale entries, resolve contradictions",
    handler: async (_args, ctx) => {
      if (!acquireDreamLock(CONFIG_DIR)) {
        ctx.ui.notify("A dream consolidation is already in progress.", "warning");
        return;
      }

      captureCommandEvent("mem0-dream", {}, telemetryCtx);
      pi.sendMessage({ customType: "mem0-dream", content: DREAM_PROTOCOL, display: false }, { triggerTurn: true });
      sendFeedback(
        "mem0-dream",
        "**Dreaming** — reviewing your memories to merge duplicates, resolve contradictions, and prune stale entries. I'll report what changed.",
      );
    },
  });

  pi.registerCommand("mem0-pin", {
    description: "Pin a memory to protect it from dream pruning",
    handler: async (args, ctx) => {
      const query = args?.trim();
      if (!query) {
        ctx.ui.notify("Usage: /mem0-pin <query>", "warning");
        return;
      }

      const memories = await searchMemories(query, config.defaultScope);

      if (memories.length === 0) {
        captureCommandEvent("mem0-pin", { result_count: 0 }, telemetryCtx);
        sendFeedback("mem0-pin", `**No matches for "${query}"** — nothing to pin.`);
        return;
      }

      const pinned = (mem: Parameters<typeof formatMemoryCompact>[0]) => {
        captureCommandEvent("mem0-pin", { pinned: true }, telemetryCtx);
        sendFeedback(
          "mem0-pin",
          ["**Pinned** — protected from dream pruning", `- ${formatMemoryCompact(mem)}`].join("\n"),
        );
      };
      const alreadyPinned = (mem: Parameters<typeof formatMemoryCompact>[0]) => {
        sendFeedback("mem0-pin", ["**Already pinned**", `- ${formatMemoryCompact(mem)}`].join("\n"));
      };

      if (memories.length === 1) {
        const target = memories[0];
        const text = target.memory ?? "";
        if (text.startsWith("[PINNED]")) {
          alreadyPinned(target);
          return;
        }
        const confirmed = await ctx.ui.confirm("Pin this memory?", formatMemoryCompact(target));
        if (!confirmed) {
          sendFeedback("mem0-pin", "**Cancelled** — nothing was pinned.");
          return;
        }
        await mem0.update(target.id, { text: `[PINNED] ${text}` });
        pinned(target);
        return;
      }

      const labels = memories.map((m) => formatMemoryCompact(m));
      const selected = await ctx.ui.select(
        `Found ${pluralize(memories.length, "match", "matches")} for "${query}" — which should I pin?`,
        labels,
      );
      if (!selected) {
        sendFeedback("mem0-pin", "**Cancelled** — nothing was pinned.");
        return;
      }
      const idx = labels.indexOf(selected);
      if (idx < 0) return;
      const target = memories[idx];
      const selectedText = target.memory ?? "";
      if (selectedText.startsWith("[PINNED]")) {
        alreadyPinned(target);
        return;
      }
      await mem0.update(target.id, { text: `[PINNED] ${selectedText}` });
      pinned(target);
    },
  });

  pi.registerCommand("mem0-scope", {
    description: "Change default memory scope for this session (project, session, global)",
    handler: async (args, ctx) => {
      const scope = args?.trim().toLowerCase();
      const valid: Scope[] = ["project", "session", "global"];

      if (!scope) {
        sendFeedback(
          "mem0-scope",
          [
            `**Current scope: ${config.defaultScope}**`,
            `New memories save to the **${config.defaultScope}** pool. Switch with \`/mem0-scope <${valid.join(" | ")}>\`.`,
          ].join("\n"),
        );
        return;
      }

      if (!valid.includes(scope as Scope)) {
        ctx.ui.notify(`Invalid scope "${scope}". Must be one of: ${valid.join(", ")}`, "warning");
        return;
      }

      config.defaultScope = scope as Scope;
      captureCommandEvent("mem0-scope", { scope }, telemetryCtx);
      sendFeedback(
        "mem0-scope",
        [
          `**Scope changed to ${scope}**`,
          `New memories now save to the **${scope}** pool for this session.`,
        ].join("\n"),
      );
    },
  });

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
        "**Mem0 status**",
        "",
        `- Connection: ${connected ? "connected" : "disconnected"}`,
        `- User: ${scopeCtx.userId}`,
        `- Project: ${scopeCtx.appId}`,
        `- Session: ${scopeCtx.runId}`,
        `- Default scope: ${config.defaultScope}`,
        `- Search relevance threshold: ${config.searchThreshold}`,
        `- Project memories: ${count}`,
        `- Auto-capture: ${config.autoCapture ? "on" : "off"}`,
        `- Dream: ${config.dream.enabled ? "enabled" : "disabled"}`,
      ];

      captureCommandEvent("mem0-status", { connected, memory_count: count }, telemetryCtx);
      sendFeedback("mem0-status", lines.join("\n"));
    },
  });
}
