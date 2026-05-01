/**
 * Mem0 provider implementations: Platform (cloud) and OSS (self-hosted).
 */

import type { OpenClawPluginApi } from "openclaw/plugin-sdk";
import type {
  Mem0Config,
  Mem0Provider,
  AddOptions,
  SearchOptions,
  ListOptions,
  MemoryItem,
  AddResult,
} from "./types.ts";

// ============================================================================
// Result Normalizers
// ============================================================================

function normalizeMemoryItem(raw: any): MemoryItem {
  return {
    id: raw.id ?? raw.memory_id ?? "",
    memory: raw.memory ?? raw.text ?? raw.content ?? "",
    // Handle both platform (user_id, created_at) and OSS (userId, createdAt) field names
    user_id: raw.user_id ?? raw.userId,
    score: raw.score,
    categories: raw.categories,
    metadata: raw.metadata,
    created_at: raw.created_at ?? raw.createdAt,
    updated_at: raw.updated_at ?? raw.updatedAt,
  };
}

function normalizeSearchResults(raw: any): MemoryItem[] {
  // Platform API returns flat array, OSS returns { results: [...] }
  if (Array.isArray(raw)) return raw.map(normalizeMemoryItem);
  if (raw?.results && Array.isArray(raw.results))
    return raw.results.map(normalizeMemoryItem);
  return [];
}

function normalizeAddResult(raw: any): AddResult {
  // Handle { results: [...] } shape (both platform and OSS)
  if (raw?.results && Array.isArray(raw.results)) {
    return {
      results: raw.results.map((r: any) => ({
        id: r.id ?? r.memory_id ?? "",
        memory: r.memory ?? r.text ?? "",
        // Platform API may return PENDING status (async processing)
        // OSS stores event in metadata.event
        event:
          r.event ??
          r.metadata?.event ??
          (r.status === "PENDING" ? "ADD" : "ADD"),
      })),
    };
  }
  // Platform API without output_format returns flat array
  if (Array.isArray(raw)) {
    return {
      results: raw.map((r: any) => ({
        id: r.id ?? r.memory_id ?? "",
        memory: r.memory ?? r.text ?? "",
        event:
          r.event ??
          r.metadata?.event ??
          (r.status === "PENDING" ? "ADD" : "ADD"),
      })),
    };
  }
  return { results: [] };
}

// ============================================================================
// Platform Provider (Mem0 Cloud)
// ============================================================================

class PlatformProvider implements Mem0Provider {
  private client: any; // MemoryClient from mem0ai
  private initPromise: Promise<void> | null = null;

  constructor(
    private readonly apiKey: string,
    private readonly baseUrl?: string,
  ) {}

  private async ensureClient(): Promise<void> {
    if (this.client) return;
    if (this.initPromise) return this.initPromise;
    this.initPromise = this._init().catch((err) => {
      this.initPromise = null;
      throw err;
    });
    return this.initPromise;
  }

  private async _init(): Promise<void> {
    const { default: MemoryClient } = await import("mem0ai");
    const opts: {
      apiKey: string;
      host?: string;
    } = {
      apiKey: this.apiKey,
    };
    if (this.baseUrl) opts.host = this.baseUrl;
    this.client = new MemoryClient(opts);
  }

  async add(
    messages: Array<{ role: string; content: string }>,
    options: AddOptions,
  ): Promise<AddResult> {
    await this.ensureClient();
    // v3.0.0: SDK uses camelCase (userId, runId, etc.) - it converts to snake_case internally
    const opts: Record<string, unknown> = { userId: options.user_id };
    if (options.run_id) opts.runId = options.run_id;
    if (options.custom_instructions)
      opts.customInstructions = options.custom_instructions;
    if (options.custom_categories)
      opts.customCategories = options.custom_categories;
    if (options.source) opts.source = options.source;
    // Agentic harness: direct storage bypass
    if (options.infer !== undefined) opts.infer = options.infer;
    if (options.deduced_memories)
      opts.deducedMemories = options.deduced_memories;
    if (options.metadata) opts.metadata = options.metadata;

    const result = await this.client.add(messages, opts);
    return normalizeAddResult(result);
  }

  async search(query: string, options: SearchOptions): Promise<MemoryItem[]> {
    await this.ensureClient();
    // v3.0.0: SDK uses camelCase options, userId must be in filters
    const opts: Record<string, unknown> = {};
    if (options.top_k != null) opts.topK = options.top_k;
    if (options.threshold != null) opts.threshold = options.threshold;
    if (options.categories != null) opts.categories = options.categories;

    // Build filters with user_id/run_id inside (v3.0.0 requirement)
    // Filters use snake_case as they're passed directly to the API
    // Note: source is NOT a valid filter field - only used when adding
    const baseFilters: Record<string, unknown> = { user_id: options.user_id };
    if (options.run_id) baseFilters.run_id = options.run_id;

    if (options.filters) {
      opts.filters = { AND: [baseFilters, options.filters] };
    } else {
      opts.filters = baseFilters;
    }

    const results = await this.client.search(query, opts);
    return normalizeSearchResults(results);
  }

  async get(memoryId: string): Promise<MemoryItem> {
    await this.ensureClient();
    const result = await this.client.get(memoryId);
    return normalizeMemoryItem(result);
  }

  async getAll(options: ListOptions): Promise<MemoryItem[]> {
    await this.ensureClient();
    // v3.0.0: SDK uses camelCase options, userId must be in filters
    // Filters use snake_case as they're passed directly to the API
    // Note: source is NOT a valid filter field - only used when adding
    const filters: Record<string, unknown> = { user_id: options.user_id };
    if (options.run_id) filters.run_id = options.run_id;

    const opts: Record<string, unknown> = { filters };
    if (options.page_size != null) opts.pageSize = options.page_size;

    const results = await this.client.getAll(opts);
    if (Array.isArray(results)) return results.map(normalizeMemoryItem);
    // Some versions return { results: [...] }
    if (results?.results && Array.isArray(results.results))
      return results.results.map(normalizeMemoryItem);
    return [];
  }

  async update(memoryId: string, text: string): Promise<void> {
    await this.ensureClient();
    await this.client.update(memoryId, { text });
  }

  async delete(memoryId: string): Promise<void> {
    await this.ensureClient();
    await this.client.delete(memoryId);
  }

  async deleteAll(userId: string): Promise<void> {
    await this.ensureClient();
    // v3.0.0: SDK uses camelCase
    await this.client.deleteAll({ userId });
  }

  async history(memoryId: string): Promise<
    Array<{
      id: string;
      old_memory: string;
      new_memory: string;
      event: string;
      created_at: string;
    }>
  > {
    await this.ensureClient();
    const result = await this.client.history(memoryId);
    return Array.isArray(result) ? result : [];
  }
}

// ============================================================================
// Open-Source Provider (Self-hosted)
// ============================================================================

class OSSProvider implements Mem0Provider {
  private static _warnPatched = false;
  private memory: any; // Memory from mem0ai/oss
  private initPromise: Promise<void> | null = null;

  constructor(
    private readonly ossConfig?: Mem0Config["oss"],
    private readonly customInstructions?: string,
    private readonly resolvePath?: (p: string) => string,
  ) {}

  private async ensureMemory(): Promise<void> {
    if (this.memory) return;
    if (this.initPromise) return this.initPromise;
    this.initPromise = this._init().catch((err) => {
      this.initPromise = null;
      throw err;
    });
    return this.initPromise;
  }

  private _buildConfig(disableHistory = false): Record<string, unknown> {
    // v3.0.0: removed version field
    const config: Record<string, unknown> = {};

    const defaultEmbedder = {
      provider: "openai",
      config: { model: "text-embedding-3-small" },
    };
    const defaultLlm = { provider: "openai", config: { model: "gpt-5-mini" } };

    const stripEmpty = (obj: Record<string, unknown>) => {
      const out = { ...obj };
      for (const k of Object.keys(out)) {
        if (out[k] === "") delete out[k];
      }
      return out;
    };

    if (this.ossConfig?.embedder) {
      const ec = stripEmpty(this.ossConfig.embedder.config ?? {});
      if (ec.host && !ec.url) {
        ec.url = ec.host;
        delete ec.host;
      }
      config.embedder = {
        provider: this.ossConfig.embedder.provider || defaultEmbedder.provider,
        config: { ...defaultEmbedder.config, ...ec },
      };
    } else {
      config.embedder = defaultEmbedder;
    }

    if (this.ossConfig?.llm) {
      const lc = stripEmpty(this.ossConfig.llm.config ?? {});
      if (lc.host && !lc.url) {
        lc.url = lc.host;
        delete lc.host;
      }
      config.llm = {
        provider: this.ossConfig.llm.provider || defaultLlm.provider,
        config: { ...defaultLlm.config, ...lc },
      };
    } else {
      config.llm = defaultLlm;
    }

    if (this.ossConfig?.vectorStore) {
      const vs = { ...this.ossConfig.vectorStore } as Record<string, unknown>;
      const vsCfg = (vs.config ?? {}) as Record<string, unknown>;
      // Resolve dims from embedder config if vector store doesn't have them
      const embedderDims = (config.embedder as any)?.config?.embeddingDims;
      if (!vsCfg.dimension && embedderDims) {
        vsCfg.dimension = embedderDims;
      }
      // Sync both dimension fields — Qdrant reads dimension, PGVector reads embeddingModelDims
      if (vsCfg.dimension && !vsCfg.embeddingModelDims) {
        vsCfg.embeddingModelDims = vsCfg.dimension;
      } else if (vsCfg.embeddingModelDims && !vsCfg.dimension) {
        vsCfg.dimension = vsCfg.embeddingModelDims;
      }
      vs.config = vsCfg;
      config.vectorStore = vs;
    }

    if (this.ossConfig?.historyDbPath) {
      const raw = this.ossConfig.historyDbPath;
      const isAbsolute = raw.startsWith("/") || /^[A-Za-z]:[/\\]/.test(raw);
      const dbPath =
        isAbsolute || !this.resolvePath ? raw : this.resolvePath(raw);
      config.historyDbPath = dbPath;
    }

    if (disableHistory || this.ossConfig?.disableHistory) {
      config.disableHistory = true;
    }

    // v3.0.0: customPrompt renamed to customInstructions
    if (this.customInstructions) config.customInstructions = this.customInstructions;
    return config;
  }

  private async _init(): Promise<void> {
    const mod = await import("mem0ai/oss");
    const Memory = mod.Memory;
    for (const cls of ["PGVector", "RedisDB", "Qdrant"]) {
      const VectorCls = (mod as any)[cls];
      if (!VectorCls || VectorCls.prototype.__patched) continue;
      const origInit = VectorCls.prototype.initialize;
      VectorCls.prototype.initialize = function (this: any) {
        if (!this.config?.embeddingModelDims && this.config?.dimension) {
          this.config.embeddingModelDims = this.config.dimension;
        }
        // Qdrant reads this.dimension directly
        if (!this.dimension && this.config?.dimension) {
          this.dimension = this.config.dimension;
        }
        // Skip premature constructor call when dimensions unknown
        const dims = this.config?.embeddingModelDims ?? this.dimension;
        if (!dims) return Promise.resolve();
        // Run the real initialize only once
        if (!this._initializePromise) {
          this._initializePromise = origInit.call(this);
        }
        return this._initializePromise;
      };
      VectorCls.prototype.__patched = true;
    }

    // Proactively detect broken better-sqlite3 native binding (e.g. Node
    // version mismatch) and skip history to avoid noisy constructor failures.
    let sqliteOk = true;
    if (!this.ossConfig?.disableHistory) {
      try {
        // @ts-ignore — better-sqlite3 is a transitive dep; no types in this package
        const bs3Mod = await import("better-sqlite3");
        const BS3 = bs3Mod.default ?? bs3Mod;
        const testDb = new (BS3 as any)(":memory:");
        (testDb as any).close();
      } catch {
        sqliteOk = false;
      }
    }

    if (!OSSProvider._warnPatched) {
      const origWarn = console.warn;
      console.warn = (...args: unknown[]) => {
        if (typeof args[0] === "string" && args[0].includes("checkCompatibility")) return;
        origWarn.apply(console, args);
      };
      OSSProvider._warnPatched = true;
    }

    let mem: any;
    try {
      mem = new Memory(this._buildConfig(!sqliteOk));
    } catch (err) {
      if (!this.ossConfig?.disableHistory && sqliteOk) {
        console.warn(
          "[mem0] Memory initialization failed, retrying with history disabled:",
          err instanceof Error ? err.message : err,
        );
        mem = new Memory(this._buildConfig(true));
      } else {
        throw err;
      }
    }

    // v3.0.0: entity IDs must be in filters, not top-level
    await mem.getAll({ filters: { user_id: "__mem0_warmup__" } });

    this.memory = mem;
  }

  async add(
    messages: Array<{ role: string; content: string }>,
    options: AddOptions,
  ): Promise<AddResult> {
    await this.ensureMemory();
    // OSS SDK uses camelCase: userId/runId, not user_id/run_id
    const addOpts: Record<string, unknown> = { userId: options.user_id };
    if (options.run_id) addOpts.runId = options.run_id;
    if (options.source) addOpts.source = options.source;
    // Agentic harness: direct storage bypass
    if (options.infer !== undefined) addOpts.infer = options.infer;
    if (options.metadata) addOpts.metadata = options.metadata;
    // v3.0.0: removed expiration_date, immutable

    // OSS SDK doesn't support deduced_memories — when infer=false, it stores
    // raw message content directly. Rewrite messages to contain the facts so
    // OSS stores the right text.
    let effectiveMessages = messages;
    if (options.infer === false && options.deduced_memories?.length) {
      effectiveMessages = options.deduced_memories.map((fact) => ({
        role: "user",
        content: fact,
      }));
    }

    const result = await this.memory.add(effectiveMessages, addOpts);
    return normalizeAddResult(result);
  }

  async search(query: string, options: SearchOptions): Promise<MemoryItem[]> {
    await this.ensureMemory();
    // v3.0.0: entity IDs must be in filters, not top-level; limit renamed to topK
    const opts: Record<string, unknown> = {};
    if (options.top_k != null) opts.topK = options.top_k;
    if (options.threshold != null) opts.threshold = options.threshold;

    // Build filters with user_id/run_id inside (v3.0.0 requirement)
    // Filters use snake_case as they're passed directly to the vector store
    // Note: source is NOT a valid filter field - only used when adding
    const baseFilters: Record<string, unknown> = { user_id: options.user_id };
    if (options.run_id) baseFilters.run_id = options.run_id;

    // Merge with any additional user-provided filters
    if (options.filters) {
      opts.filters = { AND: [baseFilters, options.filters] };
    } else {
      opts.filters = baseFilters;
    }

    const results = await this.memory.search(query, opts);
    const normalized = normalizeSearchResults(results);

    // Filter results by threshold if specified (client-side filtering as fallback)
    if (options.threshold != null) {
      return normalized.filter(
        (item) => (item.score ?? 0) >= options.threshold!,
      );
    }

    return normalized;
  }

  async get(memoryId: string): Promise<MemoryItem> {
    await this.ensureMemory();
    const result = await this.memory.get(memoryId);
    return normalizeMemoryItem(result);
  }

  async getAll(options: ListOptions): Promise<MemoryItem[]> {
    await this.ensureMemory();
    // v3.0.0: entity IDs must be in filters, not top-level
    // Filters use snake_case as they're passed directly to the vector store
    // Note: source is NOT a valid filter field - only used when adding
    const filters: Record<string, unknown> = { user_id: options.user_id };
    if (options.run_id) filters.run_id = options.run_id;

    // OSS SDK uses topK for limiting results (not pageSize like Platform)
    const getAllOpts: Record<string, unknown> = { filters };
    if (options.page_size != null) getAllOpts.topK = options.page_size;

    const results = await this.memory.getAll(getAllOpts);
    if (Array.isArray(results)) return results.map(normalizeMemoryItem);
    if (results?.results && Array.isArray(results.results))
      return results.results.map(normalizeMemoryItem);
    return [];
  }

  async update(memoryId: string, text: string): Promise<void> {
    await this.ensureMemory();
    await this.memory.update(memoryId, text);
  }

  async delete(memoryId: string): Promise<void> {
    await this.ensureMemory();
    await this.memory.delete(memoryId);
  }

  async deleteAll(userId: string): Promise<void> {
    await this.ensureMemory();
    await this.memory.deleteAll({ userId });
  }

  async history(memoryId: string): Promise<
    Array<{
      id: string;
      old_memory: string;
      new_memory: string;
      event: string;
      created_at: string;
    }>
  > {
    await this.ensureMemory();
    try {
      const result = await this.memory.history(memoryId);
      return Array.isArray(result) ? result : [];
    } catch (err) {
      // OSS may not support history depending on config (e.g. disableHistory)
      console.warn(
        "[mem0] OSS history() failed:",
        err instanceof Error ? err.message : err,
      );
      return [];
    }
  }
}

// ============================================================================
// Provider Factory
// ============================================================================

export function createProvider(
  cfg: Mem0Config,
  api: OpenClawPluginApi,
): Mem0Provider {
  if (cfg.mode === "open-source") {
    // v3.0.0: use customInstructions (was customPrompt)
    return new OSSProvider(cfg.oss, cfg.customInstructions, (p) =>
      api.resolvePath(p),
    );
  }

  return new PlatformProvider(cfg.apiKey!, cfg.baseUrl);
}

// ============================================================================
// Provider-to-Backend Adapter
// ============================================================================

import type { Backend } from "./backend/base.ts";

/**
 * Wraps an existing Mem0Provider as the Backend interface.
 * Used in OSS mode where PlatformBackend cannot be used.
 * Platform-only methods (entities, events) throw clear errors.
 */
export function providerToBackend(
  provider: Mem0Provider,
  userId: string,
): Backend {
  return {
    async add(content, messages, opts = {}) {
      const msgs = messages ?? (content ? [{ role: "user", content }] : []);
      // v3.0.0: removed immutable, expiration_date
      const result = await provider.add(
        msgs as Array<{ role: string; content: string }>,
        {
          user_id: opts.userId ?? userId,
          source: "OPENCLAW",
          ...(opts.runId && { run_id: opts.runId }),
          ...(opts.metadata && { metadata: opts.metadata }),
          ...(opts.infer === false && { infer: false }),
        },
      );
      return result as unknown as Record<string, unknown>;
    },

    async search(query, opts = {}) {
      // v3.0.0: removed keyword_search, reranking
      const results = await provider.search(query, {
        user_id: opts.userId ?? userId,
        top_k: opts.topK,
        threshold: opts.threshold,
        filters: opts.filters,
        source: "OPENCLAW",
      });
      return results as unknown as Record<string, unknown>[];
    },

    async get(memoryId) {
      const item = await provider.get(memoryId);
      return item as unknown as Record<string, unknown>;
    },

    async listMemories(opts = {}) {
      const items = await provider.getAll({
        user_id: opts.userId ?? userId,
        page_size: opts.pageSize,
        source: "OPENCLAW",
      });
      return items as unknown as Record<string, unknown>[];
    },

    async update(memoryId, content, metadata) {
      if (content) await provider.update(memoryId, content);
      if (metadata) {
        // OSS provider doesn't support metadata-only updates — log warning
        console.warn(
          "providerToBackend: metadata updates are not supported in OSS mode, only text updates are applied",
        );
      }
      return { id: memoryId, updated: true };
    },

    async delete(memoryId, opts = {}) {
      if (opts.all) {
        await provider.deleteAll(opts.userId ?? userId);
        return { deleted: "all" };
      }
      if (memoryId) {
        await provider.delete(memoryId);
        return { deleted: memoryId };
      }
      throw new Error("Either memoryId or all is required");
    },

    async deleteEntities() {
      throw new Error("Entity management is only available in platform mode.");
    },
    async status() {
      return { connected: true, backend: "oss" };
    },
    async entities() {
      throw new Error("Entity management is only available in platform mode.");
    },
    async listEvents() {
      throw new Error("Event management is only available in platform mode.");
    },
    async getEvent() {
      throw new Error("Event management is only available in platform mode.");
    },
  };
}
