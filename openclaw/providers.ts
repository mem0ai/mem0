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
        event: r.event ?? r.metadata?.event ?? (r.status === "PENDING" ? "ADD" : "ADD"),
      })),
    };
  }
  // Platform API without output_format returns flat array
  if (Array.isArray(raw)) {
    return {
      results: raw.map((r: any) => ({
        id: r.id ?? r.memory_id ?? "",
        memory: r.memory ?? r.text ?? "",
        event: r.event ?? r.metadata?.event ?? (r.status === "PENDING" ? "ADD" : "ADD"),
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
  ) { }

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
    const opts: { apiKey: string; org_id?: string; project_id?: string } = { apiKey: this.apiKey };
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

    const result = await this.client.add(messages, opts);
    return normalizeAddResult(result);
  }

  async search(query: string, options: SearchOptions): Promise<MemoryItem[]> {
    await this.ensureClient();
    const filters: Record<string, unknown> = { user_id: options.user_id };
    if (options.run_id) filters.run_id = options.run_id;

    const opts: Record<string, unknown> = {
      api_version: "v2",
      filters,
    };
    if (options.top_k != null) opts.top_k = options.top_k;
    if (options.threshold != null) opts.threshold = options.threshold;
    if (options.keyword_search != null) opts.keyword_search = options.keyword_search;
    if (options.reranking != null) opts.rerank = options.reranking;

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

  async delete(memoryId: string): Promise<void> {
    await this.ensureClient();
    await this.client.delete(memoryId);
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
  ) { }

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
    const result = await this.memory.add(messages, addOpts);
    return normalizeAddResult(result);
  }

  async search(query: string, options: SearchOptions): Promise<MemoryItem[]> {
    await this.ensureMemory();
    // OSS SDK uses camelCase: userId/runId, not user_id/run_id
    const opts: Record<string, unknown> = { userId: options.user_id };
    if (options.run_id) opts.runId = options.run_id;
    if (options.limit != null) opts.limit = options.limit;
    else if (options.top_k != null) opts.limit = options.top_k;
    if (options.keyword_search != null) opts.keyword_search = options.keyword_search;
    if (options.reranking != null) opts.reranking = options.reranking;
    if (options.source) opts.source = options.source;
    if (options.threshold != null) opts.threshold = options.threshold;

    const results = await this.memory.search(query, opts);
    const normalized = normalizeSearchResults(results);

    // Filter results by threshold if specified (client-side filtering as fallback)
    if (options.threshold != null) {
      return normalized.filter(item => (item.score ?? 0) >= options.threshold!);
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

  async delete(memoryId: string): Promise<void> {
    await this.ensureMemory();
    await this.memory.delete(memoryId);
  }
}

// ============================================================================
// Memory Runtime Provider
// ============================================================================

type RuntimeScope = {
  namespaceId: string;
  namespaceName: string;
  agentId: string;
  agentName: string;
};

function encodeRuntimeId(scope: RuntimeScope, resourceKind: string, id: string): string {
  return `rt:${scope.namespaceId}:${resourceKind}:${id}`;
}

function decodeRuntimeId(memoryId: string): { namespaceId: string; resourceKind: string; id: string } {
  const parts = memoryId.split(":");
  if (parts.length !== 4 || parts[0] !== "rt") {
    throw new Error(`Unsupported runtime memory id: ${memoryId}`);
  }
  return {
    namespaceId: parts[1]!,
    resourceKind: parts[2]!,
    id: parts[3]!,
  };
}

class MemoryRuntimeProvider implements Mem0Provider {
  private scopeCache = new Map<string, Promise<RuntimeScope>>();

  constructor(
    private readonly runtimeConfig: NonNullable<Mem0Config["runtime"]>,
  ) { }

  async add(
    messages: Array<{ role: string; content: string }>,
    options: AddOptions,
  ): Promise<AddResult> {
    const scope = await this.ensureScope(options.user_id);
    const response = await this.request("POST", "/v1/adapters/openclaw/events", {
      namespace_id: scope.namespaceId,
      agent_id: scope.agentId,
      session_id: options.run_id,
      event_type: "conversation_turn",
      space_hint: options.run_id ? "session-space" : "project-space",
      messages,
      metadata: {},
    });

    const memoryText = messages.map((message) => message.content).join("\n");
    return {
      results: [
        {
          id: encodeRuntimeId(scope, "episode", response.event.episode_id),
          memory: memoryText,
          event: "ADD",
        },
      ],
    };
  }

  async search(query: string, options: SearchOptions): Promise<MemoryItem[]> {
    const scope = await this.ensureScope(options.user_id);
    const response = await this.request("POST", "/v1/adapters/openclaw/search", {
      namespace_id: scope.namespaceId,
      agent_id: scope.agentId,
      session_id: options.run_id,
      query,
      limit: options.limit ?? options.top_k ?? 5,
    });

    return (response.results ?? []).map((item: any) => ({
      id: encodeRuntimeId(scope, item.resource_kind ?? "memory", item.id),
      memory: item.memory ?? "",
      user_id: options.user_id,
      score: item.score,
      metadata: {
        ...(item.metadata ?? {}),
        resource_kind: item.resource_kind,
        space_type: item.space_type,
      },
      created_at: item.created_at,
      updated_at: item.updated_at,
    }));
  }

  async get(memoryId: string): Promise<MemoryItem> {
    const decoded = decodeRuntimeId(memoryId);
    const response = await this.request(
      "GET",
      `/v1/adapters/openclaw/memories/${decoded.id}?namespace_id=${encodeURIComponent(decoded.namespaceId)}`,
    );
    return {
      id: memoryId,
      memory: response.memory ?? "",
      metadata: {
        ...(response.metadata ?? {}),
        resource_kind: response.resource_kind,
        space_type: response.space_type,
      },
      created_at: response.created_at,
      updated_at: response.updated_at,
    };
  }

  async getAll(options: ListOptions): Promise<MemoryItem[]> {
    const scope = await this.ensureScope(options.user_id);
    const search = new URLSearchParams({
      namespace_id: scope.namespaceId,
      agent_id: scope.agentId,
    });
    if (options.run_id) search.set("session_id", options.run_id);
    const response = await this.request("GET", `/v1/adapters/openclaw/memories?${search.toString()}`);

    return (response.results ?? []).map((item: any) => ({
      id: encodeRuntimeId(scope, item.resource_kind ?? "memory", item.id),
      memory: item.memory ?? "",
      user_id: options.user_id,
      score: item.score,
      metadata: {
        ...(item.metadata ?? {}),
        resource_kind: item.resource_kind,
        space_type: item.space_type,
      },
      created_at: item.created_at,
      updated_at: item.updated_at,
    }));
  }

  async delete(memoryId: string): Promise<void> {
    const decoded = decodeRuntimeId(memoryId);
    await this.request(
      "DELETE",
      `/v1/adapters/openclaw/memories/${decoded.id}?namespace_id=${encodeURIComponent(decoded.namespaceId)}`,
    );
  }

  private async ensureScope(userId: string): Promise<RuntimeScope> {
    const existing = this.scopeCache.get(userId);
    if (existing) return existing;

    const pending = this.request("POST", "/v1/adapters/openclaw/bootstrap", {
      namespace_name: userId,
      agent_name: this.runtimeConfig.agentName ?? "primary",
      external_ref: userId,
    }).then((payload) => ({
      namespaceId: payload.namespace_id,
      namespaceName: payload.namespace_name,
      agentId: payload.agent_id,
      agentName: payload.agent_name,
    }));

    this.scopeCache.set(userId, pending);
    return pending;
  }

  private async request(method: string, path: string, body?: unknown): Promise<any> {
    const headers: Record<string, string> = {};
    if (body !== undefined) headers["content-type"] = "application/json";
    if (this.runtimeConfig.apiKey) headers["x-api-key"] = this.runtimeConfig.apiKey;

    const response = await fetch(`${this.runtimeConfig.baseUrl.replace(/\/$/, "")}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Memory runtime request failed (${response.status}): ${text}`);
    }
    if (response.status === 204) return {};
    return response.json();
  }
}

// ============================================================================
// Provider Factory
// ============================================================================

export function createProvider(
  cfg: Mem0Config,
  api: OpenClawPluginApi,
): Mem0Provider {
  if (cfg.mode === "runtime") {
    return new MemoryRuntimeProvider(cfg.runtime!);
  }

  if (cfg.mode === "open-source") {
    return new OSSProvider(cfg.oss, cfg.customPrompt, (p) =>
      api.resolvePath(p),
    );
  }

  return new PlatformProvider(cfg.apiKey!, cfg.orgId, cfg.projectId);
}
