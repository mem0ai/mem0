/**
 * Token-budgeted, category-ranked recall engine.
 *
 * Replaces naive "dump all search results" with:
 * 1. Search memories with threshold filtering
 * 2. Rank by category priority (identity first)
 * 3. Token-budget the results
 * 4. Format by category with importance scores
 */

import type {
  Mem0Provider,
  MemoryItem,
  SkillsConfig,
  SearchOptions,
} from "./types.ts";

// ============================================================================
// Defaults
// ============================================================================

const DEFAULT_TOKEN_BUDGET = 1500;
const DEFAULT_MAX_MEMORIES = 15;
const DEFAULT_THRESHOLD = 0.4;
const DEFAULT_CATEGORY_ORDER = [
  "identity",
  "configuration",
  "rule",
  "preference",
  "decision",
  "technical",
  "relationship",
  "project",
  "operational",
];

// Rough token estimate: ~4 chars per token for English text
const CHARS_PER_TOKEN = 4;

// ============================================================================
// Types
// ============================================================================

interface RecallResult {
  /** Formatted context string for injection */
  context: string;
  /** Raw memories retrieved */
  memories: MemoryItem[];
  /** Token count estimate */
  tokenEstimate: number;
}

// ============================================================================
// Category Detection
// ============================================================================

function getMemoryCategory(memory: MemoryItem): string {
  // Check metadata first (skill-stored memories have explicit category)
  if (
    memory.metadata?.category &&
    typeof memory.metadata.category === "string"
  ) {
    return memory.metadata.category;
  }
  // Check categories array (mem0-extracted memories)
  if (memory.categories?.length) {
    return memory.categories[0];
  }
  return "uncategorized";
}

function getMemoryImportance(memory: MemoryItem): number {
  if (
    memory.metadata?.importance &&
    typeof memory.metadata.importance === "number"
  ) {
    return memory.metadata.importance;
  }
  // Default importance by category
  const cat = getMemoryCategory(memory);
  const defaults: Record<string, number> = {
    identity: 0.95,
    configuration: 0.95,
    rule: 0.9,
    preference: 0.85,
    decision: 0.8,
    technical: 0.8,
    relationship: 0.75,
    project: 0.75,
    operational: 0.6,
  };
  return defaults[cat] ?? 0.5;
}

// ============================================================================
// Token Estimation
// ============================================================================

function estimateTokens(text: string): number {
  return Math.ceil(text.length / CHARS_PER_TOKEN);
}

// ============================================================================
// Memory Ranking
// ============================================================================

function rankMemories(
  memories: MemoryItem[],
  categoryOrder: string[],
): MemoryItem[] {
  const orderMap = new Map(categoryOrder.map((cat, i) => [cat, i]));

  return [...memories].sort((a, b) => {
    const catA = getMemoryCategory(a);
    const catB = getMemoryCategory(b);
    const orderA = orderMap.get(catA) ?? 999;
    const orderB = orderMap.get(catB) ?? 999;

    // Primary sort: category priority
    if (orderA !== orderB) return orderA - orderB;

    // Secondary sort: importance (higher first)
    const impA = getMemoryImportance(a);
    const impB = getMemoryImportance(b);
    if (impA !== impB) return impB - impA;

    // Tertiary sort: search relevance score
    return (b.score ?? 0) - (a.score ?? 0);
  });
}

// ============================================================================
// Token Budgeting
// ============================================================================

function budgetMemories(
  rankedMemories: MemoryItem[],
  tokenBudget: number,
  maxMemories: number,
  identityAlwaysInclude: boolean,
): MemoryItem[] {
  const selected: MemoryItem[] = [];
  let usedTokens = 0;

  for (const memory of rankedMemories) {
    if (selected.length >= maxMemories) break;

    const memTokens = estimateTokens(memory.memory);
    const isIdentity =
      getMemoryCategory(memory) === "identity" ||
      getMemoryCategory(memory) === "configuration";

    // Identity/config always included if flag is set
    if (identityAlwaysInclude && isIdentity) {
      selected.push(memory);
      usedTokens += memTokens;
      continue;
    }

    // Budget check for non-identity memories
    if (usedTokens + memTokens > tokenBudget) continue;

    selected.push(memory);
    usedTokens += memTokens;
  }

  return selected;
}

// ============================================================================
// Formatting
// ============================================================================

function formatRecalledMemories(
  memories: MemoryItem[],
  userId: string,
): string {
  if (memories.length === 0) {
    return `<recalled-memories>\nNo stored memories found for "${userId}".\n</recalled-memories>`;
  }

  // Group by category
  const grouped = new Map<string, MemoryItem[]>();
  for (const mem of memories) {
    const cat = getMemoryCategory(mem);
    const existing = grouped.get(cat) || [];
    existing.push(mem);
    grouped.set(cat, existing);
  }

  const lines: string[] = [
    `<recalled-memories>`,
    `Stored memories for "${userId}" (${memories.length} total, ranked by importance):`,
    "",
  ];

  // Format each category group
  for (const [category, mems] of grouped.entries()) {
    const label = category.charAt(0).toUpperCase() + category.slice(1);
    lines.push(`${label}:`);
    for (const mem of mems) {
      const imp = getMemoryImportance(mem);
      const cats = mem.categories?.length
        ? ` [${mem.categories.join(", ")}]`
        : "";
      lines.push(`- ${mem.memory}${cats} (${Math.round(imp * 100)}%)`);
    }
    lines.push("");
  }

  lines.push("</recalled-memories>");
  return lines.join("\n");
}

// ============================================================================
// Query Sanitization
// ============================================================================

/**
 * Strip OpenClaw metadata prefix from event.prompt before using as search query.
 * This only removes framework noise (sender metadata, timestamps) — NOT
 * conversational rewriting. Query rewriting is the agent's responsibility
 * via the skill protocol (the agent formulates search queries with context).
 */
export function sanitizeQuery(raw: string): string {
  let cleaned = raw.replace(
    /Sender\s*\(untrusted metadata\):\s*```json[\s\S]*?```\s*/gi,
    "",
  );
  cleaned = cleaned.replace(/^\[.*?\]\s*/g, "");
  cleaned = cleaned.trim();
  return cleaned || raw;
}

// ============================================================================
// Public API
// ============================================================================

/**
 * Perform token-budgeted, category-ranked recall.
 */
export async function recall(
  provider: Mem0Provider,
  query: string,
  userId: string,
  config: SkillsConfig = {},
  sessionId?: string,
): Promise<RecallResult> {
  const recallConfig = config.recall ?? {};
  const tokenBudget = recallConfig.tokenBudget ?? DEFAULT_TOKEN_BUDGET;
  const maxMemories = recallConfig.maxMemories ?? DEFAULT_MAX_MEMORIES;
  const threshold = recallConfig.threshold ?? DEFAULT_THRESHOLD;
  const categoryOrder = recallConfig.categoryOrder ?? DEFAULT_CATEGORY_ORDER;
  const identityAlwaysInclude = recallConfig.identityAlwaysInclude !== false;

  // Build search options (v3.0.0: keyword_search, reranking, filter_memories removed)
  const searchOpts: SearchOptions = {
    user_id: userId,
    top_k: maxMemories * 2, // Over-fetch for ranking
    threshold,
    source: "OPENCLAW",
  };

  // Sanitize query: strip OpenClaw metadata prefix before searching
  const cleanQuery = sanitizeQuery(query);

  // Search long-term memories
  let longTermMemories: MemoryItem[] = [];
  try {
    longTermMemories = await provider.search(cleanQuery, searchOpts);
  } catch (err) {
    // Graceful degradation — recall failure shouldn't block the agent
    console.warn(
      "[mem0] Recall search failed:",
      err instanceof Error ? err.message : err,
    );
  }

  // Search session memories if we have a session
  let sessionMemories: MemoryItem[] = [];
  if (sessionId) {
    try {
      sessionMemories = await provider.search(cleanQuery, {
        ...searchOpts,
        run_id: sessionId,
        top_k: 5,
      });
    } catch {
      // Session search failure is non-critical
    }
  }

  // Deduplicate: session memories that are also in long-term
  const longTermIds = new Set(longTermMemories.map((m) => m.id));
  const uniqueSession = sessionMemories.filter((m) => !longTermIds.has(m.id));

  // Combine and rank
  const allMemories = [...longTermMemories, ...uniqueSession];
  const ranked = rankMemories(allMemories, categoryOrder);
  const budgeted = budgetMemories(
    ranked,
    tokenBudget,
    maxMemories,
    identityAlwaysInclude,
  );

  // Format for injection
  const context = formatRecalledMemories(budgeted, userId);
  const tokenEstimate = estimateTokens(context);

  return { context, memories: budgeted, tokenEstimate };
}
