/**
 * memory_store tool — extracted from index.ts registerTools().
 *
 * Saves important information in long-term memory via Mem0.
 * Supports skills mode (direct storage with infer=false) and
 * legacy mode (mem0 extraction LLM handles deduplication).
 */

import { Type } from "@sinclair/typebox";
import type {
  Mem0Config,
  Mem0Provider,
  AddOptions,
  SearchOptions,
} from "../types.ts";
import { isSubagentSession } from "../isolation.ts";
import { resolveCategories, ttlToExpirationDate } from "../skill-loader.ts";

import type { ToolContext } from "./index.ts";

// ---------------------------------------------------------------------------
// Tool factory
// ---------------------------------------------------------------------------

/**
 * Creates the `memory_store` tool config object suitable for
 * `api.registerTool(config, { name })`.
 */
export function createMemoryStoreTool(ctx: ToolContext) {
  const {
    api,
    cfg,
    provider,
    resolveUserId,
    getCurrentSessionId,
    buildAddOptions,
    buildSearchOptions,
    skillsActive,
  } = ctx;

  return {
    name: "memory_store",
    label: "Memory Store",
    description:
      "Save important information in long-term memory via Mem0. Use for preferences, facts, decisions, and anything worth remembering.",
    parameters: Type.Object({
      text: Type.Optional(
        Type.String({
          description:
            "Single fact to remember. Use 'facts' array instead when storing multiple facts from one conversation turn.",
        }),
      ),
      facts: Type.Optional(
        Type.Array(Type.String(), {
          description:
            "Array of facts to store in one call. ALL facts MUST share the same category. If a turn has facts in different categories, make one call per category. Category determines retention policy (TTL, immutability).",
        }),
      ),
      category: Type.Optional(
        Type.String({
          description:
            'Memory category. Determines retention policy (TTL, immutability). All facts in this call inherit this category. Options: "identity", "preference", "decision", "rule", "project", "configuration", "technical", "relationship"',
        }),
      ),
      importance: Type.Optional(
        Type.Number({
          description:
            "Importance override (0.0-1.0). Omit to use category default. Applies to all facts in this call. Defaults: identity/config 0.95, rules 0.90, preferences 0.85, decisions 0.80, projects 0.75, operational 0.60",
        }),
      ),
      userId: Type.Optional(
        Type.String({
          description: "User ID to scope this memory",
        }),
      ),
      agentId: Type.Optional(
        Type.String({
          description:
            'Agent ID to store memory under a specific agent\'s namespace (e.g. "researcher"). Overrides userId.',
        }),
      ),
      metadata: Type.Optional(
        Type.Record(Type.String(), Type.Unknown(), {
          description: "Additional metadata to attach to this memory",
        }),
      ),
      longTerm: Type.Optional(
        Type.Boolean({
          description:
            "Store as long-term (user-scoped) memory. Default: true. Set to false for session-scoped memory.",
        }),
      ),
      // --- NEW CLI-parity parameters ---
      immutable: Type.Optional(
        Type.Boolean({
          description: "Prevent future updates to this memory",
        }),
      ),
      infer: Type.Optional(
        Type.Boolean({
          description: "Set to false to skip inference and store raw",
        }),
      ),
      expires: Type.Optional(
        Type.String({
          description: "Expiration date (YYYY-MM-DD)",
        }),
      ),
      enableGraph: Type.Optional(
        Type.Boolean({
          description: "Enable graph memory extraction",
        }),
      ),
      categories: Type.Optional(
        Type.Array(Type.String(), {
          description: "Categories for this memory",
        }),
      ),
    }),

    async execute(_toolCallId: string, params: Record<string, unknown>) {
      const p = params as {
        text?: string;
        facts?: string[];
        category?: string;
        importance?: number;
        userId?: string;
        agentId?: string;
        metadata?: Record<string, unknown>;
        longTerm?: boolean;
        // New CLI-parity params
        immutable?: boolean;
        infer?: boolean;
        expires?: string;
        enableGraph?: boolean;
        categories?: string[];
      };
      const { userId, agentId, longTerm = true } = p;

      // Resolve facts: prefer 'facts' array, fall back to single 'text'
      const allFacts: string[] = p.facts?.length
        ? p.facts
        : p.text
          ? [p.text]
          : [];
      if (allFacts.length === 0) {
        return {
          content: [
            {
              type: "text",
              text: "No facts provided. Pass 'text' or 'facts' array.",
            },
          ],
          details: { error: "missing_facts" },
        };
      }

      try {
        const currentSessionId = getCurrentSessionId();

        // Block subagent writes at the tool level. The system prompt
        // instructs subagents not to store, but a disobedient tool call
        // would write to a transient namespace that is never read again.
        if (isSubagentSession(currentSessionId)) {
          api.logger.warn(
            "openclaw-mem0: blocked memory_store from subagent session",
          );
          return {
            content: [
              {
                type: "text",
                text: "Memory storage is not available in subagent sessions. The main agent handles memory.",
              },
            ],
            details: { error: "subagent_blocked" },
          };
        }

        const uid = resolveUserId({ agentId, userId });
        const runId =
          !longTerm && currentSessionId ? currentSessionId : undefined;

        // Skills mode: bypass extraction LLM, store directly via infer=false
        if (skillsActive) {
          // Enforce batch homogeneity: if no category provided for a multi-fact
          // batch, warn. The prompt teaches batch-by-category but this is the
          // runtime safety net.
          if (allFacts.length > 1 && !p.category) {
            api.logger.warn(
              `openclaw-mem0: multi-fact batch (${allFacts.length} facts) without category. Retention policy defaults to uncategorized. Prompt instructs batch-by-category.`,
            );
          }

          // Resolve metadata: prefer explicit params, fall back to metadata record
          const rawMetadata = p.metadata;
          const category =
            p.category ?? (rawMetadata?.category as string | undefined);
          const importance =
            p.importance ?? (rawMetadata?.importance as number | undefined);
          const parsedMetadata: Record<string, unknown> = {
            ...(rawMetadata ?? {}),
            ...(category && { category }),
            ...(importance !== undefined && { importance }),
          };
          const categories = resolveCategories(cfg.skills);
          const catConfig = category ? categories[category] : undefined;
          const expirationDate = catConfig
            ? ttlToExpirationDate(catConfig.ttl)
            : undefined;
          const isImmutable = catConfig?.immutable ?? false;

          // Single API call: all facts go as deduced_memories array
          const addOpts: AddOptions = {
            user_id: uid,
            source: "OPENCLAW",
            infer: false,
            deduced_memories: allFacts,
            metadata: parsedMetadata ?? {},
            ...(expirationDate && { expiration_date: expirationDate }),
            ...(isImmutable && { immutable: true }),
          };
          if (runId) addOpts.run_id = runId;
          if (cfg.mode === "platform") {
            addOpts.output_format = "v1.1";
            if (cfg.enableGraph || cfg.skills?.triage?.enableGraph) {
              addOpts.enable_graph = true;
            }
          }

          // Apply new CLI-parity params (override category-derived values)
          if (p.immutable !== undefined) addOpts.immutable = p.immutable;
          if (p.infer !== undefined) addOpts.infer = p.infer;
          if (p.expires !== undefined) addOpts.expiration_date = p.expires;
          if (p.enableGraph !== undefined) addOpts.enable_graph = p.enableGraph;
          if (p.categories !== undefined)
            (addOpts as unknown as Record<string, unknown>).categories =
              p.categories;

          const result = await provider!.add(
            [{ role: "user", content: allFacts.join("\n") }],
            addOpts,
          );

          const count = result.results?.length ?? 0;
          api.logger.info(
            `openclaw-mem0: skills-mode stored ${count} memor${count === 1 ? "y" : "ies"} from ${allFacts.length} fact(s) in 1 API call (infer=false, category=${category ?? "none"})`,
          );

          return {
            content: [
              {
                type: "text",
                text: `Stored ${allFacts.length} fact(s) [${category ?? "uncategorized"}]: ${allFacts.map((f) => `"${f.slice(0, 60)}${f.length > 60 ? "..." : ""}"`).join(", ")}`,
              },
            ],
            details: {
              action: "stored",
              mode: "skills",
              infer: false,
              category,
              factCount: allFacts.length,
              results: result.results,
            },
          };
        }

        // Legacy mode: let mem0 extraction LLM handle it
        const combinedText = allFacts.join("\n");

        // Pre-check for near-duplicates so the extraction model has
        // context about existing memories and can UPDATE rather than ADD
        const preview = combinedText.slice(0, 200);
        const dedupOpts = buildSearchOptions(uid, 3);
        dedupOpts.threshold = 0.85;
        const existing = await provider!.search(preview, dedupOpts);
        if (existing.length > 0) {
          api.logger.info(
            `openclaw-mem0: found ${existing.length} similar existing memories — mem0 may update instead of add`,
          );
        }

        const legacyAddOpts = buildAddOptions(uid, runId, currentSessionId);

        // Apply new CLI-parity params to legacy mode as well
        if (p.immutable !== undefined) legacyAddOpts.immutable = p.immutable;
        if (p.infer !== undefined) legacyAddOpts.infer = p.infer;
        if (p.expires !== undefined) legacyAddOpts.expiration_date = p.expires;
        if (p.enableGraph !== undefined)
          legacyAddOpts.enable_graph = p.enableGraph;
        if (p.categories !== undefined)
          (legacyAddOpts as unknown as Record<string, unknown>).categories =
            p.categories;

        const result = await provider!.add(
          [{ role: "user", content: combinedText }],
          legacyAddOpts,
        );

        const added = result.results?.filter((r) => r.event === "ADD") ?? [];
        const updated =
          result.results?.filter((r) => r.event === "UPDATE") ?? [];

        const summary = [];
        if (added.length > 0)
          summary.push(
            `${added.length} new memor${added.length === 1 ? "y" : "ies"} added`,
          );
        if (updated.length > 0)
          summary.push(
            `${updated.length} memor${updated.length === 1 ? "y" : "ies"} updated`,
          );
        if (summary.length === 0) summary.push("No new memories extracted");

        return {
          content: [
            {
              type: "text",
              text: `Stored: ${summary.join(", ")}. ${result.results?.map((r) => `[${r.event}] ${r.memory}`).join("; ") ?? ""}`,
            },
          ],
          details: {
            action: "stored",
            results: result.results,
          },
        };
      } catch (err) {
        return {
          content: [
            {
              type: "text",
              text: `Memory store failed: ${String(err)}`,
            },
          ],
          details: { error: String(err) },
        };
      }
    },
  };
}
