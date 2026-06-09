import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import type MemoryClient from "mem0ai";
import type { Mem0Config, ScopeContext, Scope } from "./types.ts";
import { DEFAULT_CUSTOM_CATEGORIES } from "./types.ts";
import { resolveSearchFilters, resolveAddParams } from "./memory/scoping.ts";
import { formatMemoryList, formatMemoryCompact, groupByCategory } from "./memory/formatting.ts";
import { DREAM_PROTOCOL } from "./dream/prompt.ts";
import { acquireDreamLock } from "./dream/index.ts";
import { CONFIG_DIR } from "./config/index.ts";

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
      const stored = Array.isArray(result) ? result.length : 0;
      ctx.ui.notify(`Remembered (verbatim): stored ${stored} memory(s).`, "info");
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

      if (query.match(/^[0-9a-f-]{20,}$/i)) {
        const result = await mem0.delete(query);
        ctx.ui.notify(result.message ?? `Deleted memory ${query}.`, "info");
        return;
      }

      const filters = resolveSearchFilters(config.defaultScope, scopeCtx);
      const result = await mem0.search(query, { filters });
      const memories = result.results ?? [];

      if (memories.length === 0) {
        ctx.ui.notify("No matching memories found.", "info");
        return;
      }

      const list = formatMemoryList(memories);
      pi.sendMessage({
        customType: "mem0-forget",
        content: `Found ${memories.length} matching memory(s):\n\n${list}\n\nUse mem0_memory with action "delete" and a memory_id to remove specific entries.`,
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
    handler: async (args, _ctx) => {
      const scope = (args?.trim() as Scope) || config.defaultScope;
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

      if (query.match(/^[0-9a-f-]{20,}$/i)) {
        const mem = await mem0.get(query);
        const text = mem?.memory ?? "";
        if (!text.startsWith("[PINNED]")) {
          const addParams = resolveAddParams(config.defaultScope, scopeCtx);
          await mem0.add(
            [{ role: "user", content: `[PINNED] ${text}` }],
            { ...addParams, customCategories: DEFAULT_CUSTOM_CATEGORIES, infer: false },
          );
          await mem0.delete(query);
        }
        ctx.ui.notify(`Pinned memory ${query.slice(0, 8)}.`, "info");
        return;
      }

      const filters = resolveSearchFilters(config.defaultScope, scopeCtx);
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
        `- Project memories: ${count}`,
        `- Auto-capture: ${config.autoCapture ? "on" : "off"}`,
        `- Dream: ${config.dream.enabled ? "enabled" : "disabled"}`,
      ];

      pi.sendMessage({ customType: "mem0-status", content: lines.join("\n"), display: true });
    },
  });

  // ── /mem0-stats ─────────────────────────────────────────────────────
  pi.registerCommand("mem0-stats", {
    description: "Memory dashboard — counts by category and age distribution",
    handler: async (args, _ctx) => {
      const scope = (args?.trim() as Scope) || config.defaultScope;
      const scopeCtx = getScopeCtx();
      const filters = resolveSearchFilters(scope, scopeCtx);
      const result = await mem0.getAll({ filters });
      const memories = result.results ?? [];

      if (memories.length === 0) {
        pi.sendMessage({ customType: "mem0-stats", content: "No memories found.", display: true });
        return;
      }

      const groups = groupByCategory(memories);
      const lines = [
        `**Memory Stats** (${memories.length} total, scope: ${scope})`,
        "",
        "**By Category:**",
      ];

      for (const [category, items] of groups) {
        lines.push(`  ${category}: ${items.length}`);
      }

      const now = Date.now();
      let today = 0, thisWeek = 0, older = 0;
      for (const m of memories) {
        if (!m.createdAt) { older++; continue; }
        const age = now - new Date(m.createdAt).getTime();
        if (age < 86_400_000) today++;
        else if (age < 604_800_000) thisWeek++;
        else older++;
      }

      lines.push("", "**By Age:**");
      lines.push(`  Today: ${today}`);
      lines.push(`  This week: ${thisWeek}`);
      lines.push(`  Older: ${older}`);

      pi.sendMessage({ customType: "mem0-stats", content: lines.join("\n"), display: true });
    },
  });

  // ── /mem0-review ────────────────────────────────────────────────────
  pi.registerCommand("mem0-review", {
    description: "Read-only quality audit — find duplicates, stale entries, and contradictions",
    handler: async (_args, ctx) => {
      const scopeCtx = getScopeCtx();
      const filters = resolveSearchFilters(config.defaultScope, scopeCtx);
      const result = await mem0.getAll({ filters });
      const memories = result.results ?? [];

      if (memories.length === 0) {
        ctx.ui.notify("No memories to review.", "info");
        return;
      }

      const prompt = [
        `Review these ${memories.length} memories for quality issues. This is a READ-ONLY audit — do NOT delete or modify anything.`,
        "",
        "Look for:",
        "1. Near-duplicates (same fact stated differently)",
        "2. Stale or outdated entries",
        "3. Contradictions between memories",
        "4. Vague or poorly worded entries",
        "5. Sensitive data that shouldn't be stored (API keys, passwords)",
        "",
        "Report findings as a numbered list with the memory ID and issue.",
        "",
        "Memories:",
        formatMemoryList(memories),
      ].join("\n");

      pi.sendMessage({ customType: "mem0-review", content: prompt, display: true }, { triggerTurn: true });
      ctx.ui.notify(`Reviewing ${memories.length} memories for quality issues...`, "info");
    },
  });

  // ── /mem0-export ────────────────────────────────────────────────────
  pi.registerCommand("mem0-export", {
    description: "Export all project memories to markdown",
    handler: async (args, _ctx) => {
      const scope = (args?.trim() as Scope) || config.defaultScope;
      const scopeCtx = getScopeCtx();
      const filters = resolveSearchFilters(scope, scopeCtx);
      const result = await mem0.getAll({ filters });
      const memories = result.results ?? [];

      if (memories.length === 0) {
        pi.sendMessage({ customType: "mem0-export", content: "No memories to export.", display: true });
        return;
      }

      const groups = groupByCategory(memories);
      const lines = [
        `# Mem0 Export — ${scopeCtx.appId} (${scope} scope)`,
        `> ${memories.length} memories exported`,
        "",
      ];

      for (const [category, items] of groups) {
        lines.push(`## ${category}`);
        lines.push("");
        for (const m of items) {
          const age = m.createdAt ? new Date(m.createdAt).toISOString().split("T")[0] : "unknown";
          lines.push(`- ${m.memory ?? "(empty)"} _(${age})_ \`${m.id}\``);
        }
        lines.push("");
      }

      pi.sendMessage({ customType: "mem0-export", content: lines.join("\n"), display: true });
    },
  });

  // ── /mem0-import ────────────────────────────────────────────────────
  pi.registerCommand("mem0-import", {
    description: "Import memories from a markdown export file",
    handler: async (args, ctx) => {
      const file = args?.trim();
      const prompt = file
        ? `Read the file at "${file}" and import each memory entry using mem0_memory with action "add". Each line starting with "- " under a category heading is a memory. Store each one preserving its original text.`
        : "Paste or describe the memories you'd like to import, and I'll store each one using mem0_memory.";

      pi.sendMessage({ customType: "mem0-import", content: prompt, display: true }, { triggerTurn: true });
      ctx.ui.notify("Import started. The agent will process memories from the source.", "info");
    },
  });

  // ── /mem0-projects ──────────────────────────────────────────────────
  pi.registerCommand("mem0-projects", {
    description: "List all projects with memory counts",
    handler: async (_args, _ctx) => {
      const scopeCtx = getScopeCtx();
      const filters = resolveSearchFilters("user", scopeCtx);
      const result = await mem0.getAll({ filters });
      const memories = result.results ?? [];

      if (memories.length === 0) {
        pi.sendMessage({ customType: "mem0-projects", content: "No memories found across any project.", display: true });
        return;
      }

      const projects = new Map<string, number>();
      for (const m of memories) {
        const app = (m as any).app_id ?? "unknown";
        projects.set(app, (projects.get(app) ?? 0) + 1);
      }

      const lines = ["**Projects with Memories**", ""];
      const sorted = [...projects.entries()].sort((a, b) => b[1] - a[1]);
      for (const [project, count] of sorted) {
        const marker = project === scopeCtx.appId ? " (current)" : "";
        lines.push(`- **${project}**${marker}: ${count} memories`);
      }

      pi.sendMessage({ customType: "mem0-projects", content: lines.join("\n"), display: true });
    },
  });

  // ── /mem0-switch ────────────────────────────────────────────────────
  pi.registerCommand("mem0-switch", {
    description: "Override the auto-detected project scope",
    handler: async (args, ctx) => {
      const name = args?.trim();
      if (!name) {
        ctx.ui.notify("Usage: /mem0-switch <project-name>", "warning");
        return;
      }

      const scopeCtx = getScopeCtx();
      scopeCtx.appId = name;

      ctx.ui.notify(`Switched project scope to ${name}. All memory operations now target this project.`, "info");
    },
  });

}
