/**
 * Shared type definitions for the OpenClaw Mem0 plugin.
 */

export type Mem0Mode = "platform" | "open-source";

export type Mem0Config = {
  mode: Mem0Mode;
  // Platform-specific
  apiKey?: string;
  orgId?: string;
  projectId?: string;
  customInstructions: string;
  customCategories: Record<string, string>;
  enableGraph: boolean;
  // OSS-specific
  customPrompt?: string;
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
  // Agentic harness skills
  skills?: SkillsConfig;
};

export interface AddOptions {
  user_id: string;
  run_id?: string;
  custom_instructions?: string;
  custom_categories?: Array<Record<string, string>>;
  enable_graph?: boolean;
  output_format?: string;
  source?: string;
  // Agentic harness additions
  infer?: boolean;
  deduced_memories?: string[];
  metadata?: Record<string, unknown>;
  expiration_date?: string;
  immutable?: boolean;
}

export interface SearchOptions {
  user_id: string;
  run_id?: string;
  top_k?: number;
  threshold?: number;
  limit?: number;
  keyword_search?: boolean;
  reranking?: boolean;
  filter_memories?: boolean;
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
    enableGraph?: boolean;
    credentialPatterns?: string[];
  };
  recall?: {
    enabled?: boolean;
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
    schedule?: string;
    mergeThreshold?: number;
    maxMemoriesPerUser?: number;
    preserveImmutable?: boolean;
    credentialScan?: boolean;
    expireStaleAfterDays?: number;
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
  delete(memoryId: string): Promise<void>;
}
