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
    private readonly orgId?: string,
    private readonly projectId?: string,
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
    const opts: { apiKey: string; org_id?: string; project_id?: string } = {
      apiKey: this.apiKey,
    };
    if (this.orgId) opts.org_id = this.orgId;
    if (this.projectId) opts.project_id = this.projectId;
    this.client = new MemoryClient(opts);
  }

  async add(
    messages: Array<{ role: string; content: string }>,
    options: AddOptions,
  ): Promise<AddResult> {
    await this.ensureClient();
    const opts: Record<string, unknown> = { user_id: options.user_id };
    if (options.run_id) opts.run_id = options.run_id;
    if (options.custom_instructions)
      opts.custom_instructions = options.custom_instructions;
    if (options.custom_categories)
      opts.custom_categories = options.custom_categories;
    if (options.enable_graph) opts.enable_graph = options.enable_graph;
    if (options.output_format) opts.output_format = options.output_format;
    if (options.source) opts.source = options.source;
    // Agentic harness: direct storage bypass
    if (options.infer !== undefined) opts.infer = options.infer;
    if (options.deduced_memories)
      opts.deduced_memories = options.deduced_memories;
    if (options.metadata) opts.metadata = options.metadata;
    if (options.expiration_date) opts.expiration_date = options.expiration_date;
    if (options.immutable) opts.immutable = options.immutable;

    const result = await this.client.add(messages, opts);
    return normalizeAddResult(result);
  }

  async search(query: string, options: SearchOptions): Promise<MemoryItem[]> {
    await this.ensureClient();
    // Base filters: always scope by user_id, optionally by run_id
    const baseFilters: Record<string, unknown> = { user_id: options.user_id };
    if (options.run_id) baseFilters.run_id = options.run_id;

    // Merge agent-provided filters (created_at ranges, metadata, etc.)
    // with base filters. Agent filters extend, never override user scoping.
    const mergedFilters = options.filters
      ? { AND: [baseFilters, options.filters] }
      : baseFilters;

    const opts: Record<string, unknown> = {
      api_version: "v2",
      filters: mergedFilters,
    };
    if (options.top_k != null) opts.top_k = options.top_k;
    if (options.threshold != null) opts.threshold = options.threshold;
    if (options.keyword_search != null)
      opts.keyword_search = options.keyword_search;
    if (options.reranking != null) opts.rerank = options.reranking;
    if (options.filter_memories != null)
      opts.filter_memories = options.filter_memories;
    if (options.categories != null) opts.categories = options.categories;

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
    const opts: Record<string, unknown> = { user_id: options.user_id };
    if (options.run_id) opts.run_id = options.run_id;
    if (options.page_size != null) opts.page_size = options.page_size;
    if (options.source) opts.source = options.source;

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
    await this.client.deleteAll({ user_id: userId });
  }

  async history(
    memoryId: string,
  ): Promise<
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
  private memory: any; // Memory from mem0ai/oss
  private initPromise: Promise<void> | null = null;

  constructor(
    private readonly ossConfig?: Mem0Config["oss"],
    private readonly customPrompt?: string,
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

  private async _init(): Promise<void> {
    const { Memory } = await import("mem0ai/oss");

    const config: Record<string, unknown> = { version: "v1.1" };

    if (this.ossConfig?.embedder) config.embedder = this.ossConfig.embedder;
    if (this.ossConfig?.vectorStore)
      config.vectorStore = this.ossConfig.vectorStore;
    if (this.ossConfig?.llm) config.llm = this.ossConfig.llm;

    if (this.ossConfig?.historyDbPath) {
      const dbPath = this.resolvePath
        ? this.resolvePath(this.ossConfig.historyDbPath)
        : this.ossConfig.historyDbPath;
      config.historyDbPath = dbPath;
    }

    if (this.ossConfig?.disableHistory) {
      config.disableHistory = true;
    }

    if (this.customPrompt) config.customPrompt = this.customPrompt;

    try {
      this.memory = new Memory(config);
    } catch (err) {
      // If initialization fails (e.g. native SQLite binding resolution under
      // jiti), retry with history disabled — the history DB is the most common
      // source of native-binding failures and is not required for core
      // memory operations.
      if (!config.disableHistory) {
        console.warn(
          "[mem0] Memory initialization failed, retrying with history disabled:",
          err instanceof Error ? err.message : err,
        );
        config.disableHistory = true;
        this.memory = new Memory(config);
      } else {
        throw err;
      }
    }

    // Force the SDK's internal auto-initialization to complete now.
    // Without this, concurrent method calls (e.g. auto-recall + stats)
    // both trigger _autoInitialize() simultaneously, causing PGVector's
    // pg client to call connect() twice → "Client has already been
    // connected" crash. (#4638)
    try {
      await this.memory.getAll({ userId: "__mem0_warmup__" });
    } catch {
      // Warmup errors are non-fatal — the SDK may still work for
      // subsequent calls once its internal state settles.
    }
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
    if (options.expiration_date)
      addOpts.expirationDate = options.expiration_date;
    if (options.immutable) addOpts.immutable = options.immutable;

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
    // OSS SDK uses camelCase: userId/runId, not user_id/run_id
    const opts: Record<string, unknown> = { userId: options.user_id };
    if (options.run_id) opts.runId = options.run_id;
    if (options.limit != null) opts.limit = options.limit;
    else if (options.top_k != null) opts.limit = options.top_k;
    if (options.keyword_search != null)
      opts.keyword_search = options.keyword_search;
    if (options.reranking != null) opts.reranking = options.reranking;
    if (options.source) opts.source = options.source;
    if (options.threshold != null) opts.threshold = options.threshold;

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
    // OSS SDK uses camelCase: userId/runId, not user_id/run_id
    const getAllOpts: Record<string, unknown> = { userId: options.user_id };
    if (options.run_id) getAllOpts.runId = options.run_id;
    if (options.source) getAllOpts.source = options.source;
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

  async history(
    memoryId: string,
  ): Promise<
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
    } catch {
      // OSS may not support history depending on config
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
    return new OSSProvider(cfg.oss, cfg.customPrompt, (p) =>
      api.resolvePath(p),
    );
  }

  return new PlatformProvider(cfg.apiKey!, cfg.orgId, cfg.projectId);
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
      const result = await provider.add(
        msgs as Array<{ role: string; content: string }>,
        {
          user_id: opts.userId ?? userId,
          ...(opts.runId && { run_id: opts.runId }),
          ...(opts.metadata && { metadata: opts.metadata }),
          ...(opts.immutable && { immutable: true }),
          ...(opts.infer === false && { infer: false }),
          ...(opts.expires && { expiration_date: opts.expires }),
          ...(opts.enableGraph && { enable_graph: true }),
        },
      );
      return result as unknown as Record<string, unknown>;
    },

    async search(query, opts = {}) {
      const results = await provider.search(query, {
        user_id: opts.userId ?? userId,
        top_k: opts.topK,
        threshold: opts.threshold,
        keyword_search: opts.keyword,
        reranking: opts.rerank,
        filters: opts.filters,
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
