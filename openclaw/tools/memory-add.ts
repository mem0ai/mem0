import { Type } from "@sinclair/typebox";
import type { AddOptions } from "../types.ts";
import { isSubagentSession } from "../isolation.ts";
import { resolveCategories, ttlToExpirationDate } from "../skill-loader.ts";
import type { ToolDeps } from "./index.ts";

export function createMemoryAddTool(deps: ToolDeps) {
  const { api, cfg, provider, resolveUserId, getCurrentSessionId, buildAddOptions, buildSearchOptions, skillsActive } = deps;

  return {
    name: "memory_add",
    label: "Memory Add",
    description: "Save important information in long-term memory via Mem0. Use for preferences, facts, decisions, and anything worth remembering.",
    parameters: Type.Object({
      text: Type.Optional(Type.String({ description: "Single fact to remember" })),
      facts: Type.Optional(Type.Array(Type.String(), { description: "Array of facts to store. ALL must share the same category." })),
      category: Type.Optional(Type.String({ description: 'Category: "identity", "preference", "decision", "rule", "project", "configuration", "technical", "relationship"' })),
      importance: Type.Optional(Type.Number({ description: "Importance (0.0-1.0), omit for category default" })),
      userId: Type.Optional(Type.String({ description: "User ID to scope this memory" })),
      agentId: Type.Optional(Type.String({ description: "Agent ID namespace" })),
      metadata: Type.Optional(Type.Record(Type.String(), Type.Unknown(), { description: "Additional metadata" })),
      longTerm: Type.Optional(Type.Boolean({ description: "Long-term (default: true). Set false for session-scoped." })),
    }),

    async execute(_toolCallId: string, params: Record<string, unknown>) {
      const p = params as {
        text?: string; facts?: string[]; category?: string; importance?: number;
        userId?: string; agentId?: string; metadata?: Record<string, unknown>; longTerm?: boolean;
      };

      const allFacts: string[] = p.facts?.length ? p.facts : (p.text ? [p.text] : []);
      if (allFacts.length === 0) {
        return { content: [{ type: "text", text: "No facts provided. Pass 'text' or 'facts' array." }], details: { error: "missing_facts" } };
      }

      try {
        const currentSessionId = getCurrentSessionId();

        if (isSubagentSession(currentSessionId)) {
          return { content: [{ type: "text", text: "Memory storage is not available in subagent sessions." }], details: { error: "subagent_blocked" } };
        }

        const uid = resolveUserId({ agentId: p.agentId, userId: p.userId });
        const runId = !(p.longTerm ?? true) && currentSessionId ? currentSessionId : undefined;

        if (skillsActive) {
          const rawMetadata = p.metadata;
          const category = p.category ?? rawMetadata?.category as string | undefined;
          const importance = p.importance ?? rawMetadata?.importance as number | undefined;
          const parsedMetadata: Record<string, unknown> = {
            ...(rawMetadata ?? {}),
            ...(category && { category }),
            ...(importance !== undefined && { importance }),
          };
          const categories = resolveCategories(cfg.skills);
          const catConfig = category ? categories[category] : undefined;
          const expirationDate = catConfig ? ttlToExpirationDate(catConfig.ttl) : undefined;
          const isImmutable = catConfig?.immutable ?? false;

          const addOpts: AddOptions = {
            user_id: uid, infer: false,
            deduced_memories: allFacts, metadata: parsedMetadata ?? {},
            ...(expirationDate && { expiration_date: expirationDate }),
            ...(isImmutable && { immutable: true }),
          };
          if (runId) addOpts.run_id = runId;
          if (cfg.mode === "platform") {
            addOpts.output_format = "v1.1";
            if (cfg.enableGraph || cfg.skills?.triage?.enableGraph) addOpts.enable_graph = true;
          }

          const result = await provider.add([{ role: "user", content: allFacts.join("\n") }], addOpts);
          const count = result.results?.length ?? 0;
          api.logger.info(`openclaw-mem0: stored ${count} memor${count === 1 ? "y" : "ies"} (infer=false, category=${category ?? "none"})`);

          return {
            content: [{ type: "text", text: `Stored ${allFacts.length} fact(s) [${category ?? "uncategorized"}]: ${allFacts.map(f => `"${f.slice(0, 60)}${f.length > 60 ? "..." : ""}"`).join(", ")}` }],
            details: { action: "stored", mode: "skills", category, factCount: allFacts.length, results: result.results },
          };
        }

        const combinedText = allFacts.join("\n");
        const dedupOpts = buildSearchOptions(uid, 3);
        dedupOpts.threshold = 0.85;
        await provider.search(combinedText.slice(0, 200), dedupOpts);

        const result = await provider.add([{ role: "user", content: combinedText }], buildAddOptions(uid, runId, currentSessionId));
        const added = result.results?.filter((r) => r.event === "ADD") ?? [];
        const updated = result.results?.filter((r) => r.event === "UPDATE") ?? [];
        const summary = [];
        if (added.length > 0) summary.push(`${added.length} added`);
        if (updated.length > 0) summary.push(`${updated.length} updated`);
        if (summary.length === 0) summary.push("No new memories extracted");

        return {
          content: [{ type: "text", text: `Stored: ${summary.join(", ")}. ${result.results?.map((r) => `[${r.event}] ${r.memory}`).join("; ") ?? ""}` }],
          details: { action: "stored", results: result.results },
        };
      } catch (err) {
        return { content: [{ type: "text", text: `Memory add failed: ${String(err)}` }], details: { error: String(err) } };
      }
    },
  };
}
