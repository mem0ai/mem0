/**
 * Shared type definitions for the OpenClaw Mem0 plugin.
 */

export type Mem0Mode = "platform" | "open-source";

export type Mem0Config = {
  mode: Mem0Mode;
  // Platform-specific
  apiKey?: string;
  anonymousTelemetryId?: string;
  baseUrl?: string;
  customInstructions: string;
  customCategories: Record<string, string>;
  // OSS-specific (customPrompt renamed to customInstructions in v3.0.0)
  oss?: {
    embedder?: { provider: string; config: Record<string, unknown> };
    vectorStore?: { provider: string; config: Record<string, unknown> };
    llm?: { provider: string; config: Record<string, unknown> };
    historyDbPath?: string;
    disableHistory?: boolean;
  };
  // Shared
  userId: string;
  autoCapture: boolean;
  autoRecall: boolean;
  searchThreshold: number;
  topK: number;
  // Setup state
  needsSetup?: boolean;
  // Agentic harness skills
  skills?: SkillsConfig;
};

export interface AddOptions {
  user_id: string;
  run_id?: string;
  custom_instructions?: string;
  custom_categories?: Record<string, string>;
  source?: string;
  // Agentic harness additions
  infer?: boolean;
  deduced_memories?: string[];
  metadata?: Record<string, unknown>;
}

export interface SearchOptions {
  user_id: string;
  run_id?: string;
  top_k?: number;
  threshold?: number;
  categories?: string[];
  filters?: Record<string, unknown>;
  source?: string;
}

// ============================================================================
// Skills Configuration Types
// ============================================================================

export interface CategoryConfig {
  importance: number;
  ttl: string | null; // e.g. "7d", "90d", null = permanent
  immutable?: boolean;
}

export interface SkillsConfig {
  triage?: {
    enabled?: boolean;
    importanceThreshold?: number;
    credentialPatterns?: string[];
  };
  recall?: {
    /** Master switch. false = no auto-recall regardless of strategy. */
    enabled?: boolean;
    /** Controls auto-recall behavior. Only consulted when enabled !== false.
     *  "smart" (default): long-term search only, 1 search/turn.
     *  "manual": zero plugin searches, agent controls all search.
     *  "always": long-term + session search, 2 searches/turn. */
    strategy?: "always" | "smart" | "manual";
    tokenBudget?: number;
    maxMemories?: number;
    rerank?: boolean;
    keywordSearch?: boolean;
    filterMemories?: boolean;
    threshold?: number;
    identityAlwaysInclude?: boolean;
    categoryOrder?: string[];
  };
  dream?: {
    enabled?: boolean;
    /** Enable automatic triggering based on activity gates. Default: true when dream enabled. */
    auto?: boolean;
    /** Minimum hours between consolidations. Default: 24. */
    minHours?: number;
    /** Minimum interactive sessions before triggering. Default: 5. */
    minSessions?: number;
    /** Minimum total memories to justify consolidation. Default: 20. */
    minMemories?: number;
  };
  domain?: string;
  customRules?: {
    include?: string[];
    exclude?: string[];
  };
  categories?: Record<string, CategoryConfig>;
}

export interface ListOptions {
  user_id: string;
  run_id?: string;
  page_size?: number;
  source?: string;
}

export interface MemoryItem {
  id: string;
  memory: string;
  user_id?: string;
  score?: number;
  categories?: string[];
  metadata?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
}

export interface AddResultItem {
  id: string;
  memory: string;
  event: "ADD" | "UPDATE" | "DELETE" | "NOOP";
}

export interface AddResult {
  results: AddResultItem[];
}

export interface Mem0Provider {
  add(
    messages: Array<{ role: string; content: string }>,
    options: AddOptions,
  ): Promise<AddResult>;
  search(query: string, options: SearchOptions): Promise<MemoryItem[]>;
  get(memoryId: string): Promise<MemoryItem>;
  getAll(options: ListOptions): Promise<MemoryItem[]>;
  update(memoryId: string, text: string): Promise<void>;
  delete(memoryId: string): Promise<void>;
  deleteAll(userId: string): Promise<void>;
  history(
    memoryId: string,
  ): Promise<
    Array<{
      id: string;
      old_memory: string;
      new_memory: string;
      event: string;
      created_at: string;
    }>
  >;
}
