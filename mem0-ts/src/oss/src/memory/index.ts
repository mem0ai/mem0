import { v4 as uuidv4 } from "uuid";
import { createHash } from "crypto";
import {
  MemoryConfig,
  MemoryConfigSchema,
  MemoryItem,
  Message,
  SearchFilters,
  SearchResult,
  VectorStoreResult,
} from "../types";
import {
  EmbedderFactory,
  LLMFactory,
  VectorStoreFactory,
  HistoryManagerFactory,
} from "../utils/factory";
import {
  FactRetrievalSchema,
  getFactRetrievalMessages,
  getUpdateMemoryMessages,
  parseMessages,
  extractJson,
  ADDITIVE_EXTRACTION_PROMPT,
  AGENT_CONTEXT_SUFFIX,
  AdditiveExtractionSchema,
  generateAdditiveExtractionPrompt,
} from "../prompts";
import { DummyHistoryManager } from "../storage/DummyHistoryManager";
import { Embedder } from "../embeddings/base";
import { LLM } from "../llms/base";
import { VectorStore } from "../vector_stores/base";
import { ConfigManager } from "../config/manager";

import {
  AddMemoryOptions,
  SearchMemoryOptions,
  DeleteAllMemoryOptions,
  GetAllMemoryOptions,
  UpdateProjectOptions,
} from "./memory.types";
import { parse_vision_messages } from "../utils/memory";
import { HistoryManager } from "../storage/base";
import { captureClientEvent } from "../utils/telemetry";
import {
  detectScaleThresholdFromAddResult,
  detectScaleThresholdFromTopK,
  detectPerformanceSlowQuery,
  detectTemporalUsageFromMetadata,
  detectTemporalUsageFromSearch,
  displayDecayUsageNotice,
  displayFirstRunNotice,
  displayPerformanceSlowQueryNotice,
  displayScaleThresholdNotice,
  displayTemporalUsageNotice,
  getDecayFeatureErrorMessage,
  getDecayUsageDeleteCountAfterSuccess,
  getTemporalFeatureErrorMessage,
  isDecayUsageDeleteEligible,
  PerformanceSlowQueryTrigger,
  ScaleThresholdTrigger,
} from "../utils/notices";
import { lemmatizeForBm25 } from "../utils/lemmatization";
import {
  extractEntities,
  extractEntitiesBatch,
} from "../utils/entity_extraction";
import {
  scoreAndRank,
  getBm25Params,
  normalizeBm25,
  ENTITY_BOOST_WEIGHT,
  ScoredResult,
} from "../utils/scoring";
import { getDefaultVectorStoreDbPath } from "../utils/sqlite";
import { getOrCreateMem0UserId } from "../../../client/config";

const SCOPE_KEYS = ["user_id", "agent_id", "run_id"] as const;
type ScopeKey = (typeof SCOPE_KEYS)[number];

const SCOPE_KEY_ALIASES: Record<ScopeKey, "userId" | "agentId" | "runId"> = {
  user_id: "userId",
  agent_id: "agentId",
  run_id: "runId",
};

// Entity params that must be passed via filters - check both snake_case and camelCase
const ENTITY_PARAMS: string[] = [
  ...SCOPE_KEYS,
  ...Object.values(SCOPE_KEY_ALIASES),
];

const RESERVED_PAYLOAD_KEYS = new Set<string>([
  ...SCOPE_KEYS,
  ...Object.values(SCOPE_KEY_ALIASES),
  "hash",
  "data",
  "createdAt",
  "updatedAt",
  "created_at",
  "updated_at",
  "textLemmatized",
  "attributedTo",
]);

const MIN_SCOPE_POST_FILTER_FETCH = 60;
// deleteAll has no cursor-aware vector-store list API today, so use a large
// one-shot page and fail closed for providers that cannot prove total counts.
const DELETE_ALL_SCOPE_FETCH_LIMIT = 10000;

/**
 * Validates that no top-level entity parameters are passed in config.
 * @throws Error if entity params are found at top level
 */
function rejectTopLevelEntityParams(
  config: Record<string, any>,
  methodName: string,
): void {
  const invalidKeys = Object.keys(config).filter((k) =>
    ENTITY_PARAMS.includes(k),
  );
  if (invalidKeys.length > 0) {
    throw new Error(
      `Top-level entity parameters [${invalidKeys.join(", ")}] are not supported in ${methodName}(). ` +
        `Use filters: { userId: "..." } instead.`,
    );
  }
}

/**
 * Validates and normalizes an entity ID.
 * - Trims leading/trailing whitespace
 * - Rejects empty or whitespace-only strings
 * - Rejects strings containing internal whitespace
 * @returns The trimmed entity ID, or undefined if input is undefined
 * @throws Error if entity ID is invalid
 */
function validateAndTrimEntityId(
  value: string | undefined,
  name: string,
): string | undefined {
  if (value === undefined) return undefined;
  const trimmed = value.trim();
  if (trimmed === "") {
    throw new Error(
      `Invalid ${name}: cannot be empty or whitespace-only. Provide a valid identifier.`,
    );
  }
  if (/\s/.test(trimmed)) {
    throw new Error(
      `Invalid ${name}: cannot contain whitespace. Provide a valid identifier without spaces.`,
    );
  }
  return trimmed;
}

/**
 * Validates search parameters.
 * @throws Error if threshold or topK are invalid
 */
function validateSearchParams(threshold?: number, topK?: number): void {
  if (threshold !== undefined) {
    if (typeof threshold !== "number" || isNaN(threshold)) {
      throw new Error("threshold must be a valid number");
    }
    if (threshold < 0 || threshold > 1) {
      throw new Error(
        `Invalid threshold: ${threshold}. Must be between 0 and 1 (inclusive).`,
      );
    }
  }
  if (topK !== undefined) {
    if (typeof topK !== "number" || isNaN(topK) || !Number.isInteger(topK)) {
      throw new Error("topK must be a valid integer");
    }
    if (topK < 0) {
      throw new Error(`Invalid topK: ${topK}. Must be a non-negative integer.`);
    }
  }
}

export class Memory {
  private config: MemoryConfig;
  private customInstructions: string | undefined;
  private embedder: Embedder;
  private vectorStore!: VectorStore;
  private llm: LLM;
  private db: HistoryManager;
  private collectionName: string | undefined;
  private apiVersion: string;
  telemetryId: string;
  private _initPromise: Promise<void>;
  private _initError?: Error;
  private _entityStore?: VectorStore;

  constructor(config: Partial<MemoryConfig> = {}) {
    // Merge and validate config
    this.config = ConfigManager.mergeConfig(config);

    this.customInstructions = this.config.customInstructions;
    this.embedder = EmbedderFactory.create(
      this.config.embedder.provider,
      this.config.embedder.config,
    );
    // Vector store creation is deferred to _autoInitialize() so that
    // the embedding dimension can be auto-detected first when not
    // explicitly configured.
    this.llm = LLMFactory.create(
      this.config.llm.provider,
      this.config.llm.config,
    );
    if (this.config.disableHistory) {
      this.db = new DummyHistoryManager();
    } else {
      this.db = HistoryManagerFactory.create(
        this.config.historyStore!.provider,
        this.config.historyStore!,
      );
    }

    this.collectionName = this.config.vectorStore.config.collectionName;
    this.apiVersion = this.config.version || "v1.0";
    this.telemetryId = "anonymous";

    // Auto-detect embedding dimension (if needed), create vector store,
    // and initialize it. All public methods await this before proceeding.
    this._initPromise = this._autoInitialize().catch((error) => {
      this._initError =
        error instanceof Error ? error : new Error(String(error));
      console.error(this._initError);
    });
  }

  /**
   * If no explicit dimension was provided, runs a probe embedding to
   * detect it. Then creates and initializes the vector store.
   */
  private async _autoInitialize(): Promise<void> {
    if (!this.config.vectorStore.config.dimension) {
      try {
        const probe = await this.embedder.embed("dimension probe");
        this.config.vectorStore.config.dimension = probe.length;
      } catch (error: any) {
        throw new Error(
          `Failed to auto-detect embedding dimension from provider '${this.config.embedder.provider}': ${error.message}. ` +
            `Please set 'dimension' in vectorStore.config or 'embeddingDims' in embedder.config explicitly.`,
        );
      }
    }

    this.vectorStore = VectorStoreFactory.create(
      this.config.vectorStore.provider,
      this.config.vectorStore.config,
    );

    // The vector store constructor may fire initialize() asynchronously
    // (e.g. Qdrant). Explicitly await it here to guarantee the backing
    // store (collections, tables, etc.) is ready before any public method
    // attempts to read or write.
    await this.vectorStore.initialize();

    await this._initializeTelemetry();
  }

  /**
   * Ensures that auto-initialization (dimension detection + vector store
   * creation) has completed before any public method proceeds.
   * If a previous init attempt failed, retries automatically.
   */
  private async _ensureInitialized(): Promise<void> {
    await this._initPromise;
    if (this._initError) {
      // Clear failed state and retry — the embedder or vector store
      // may have been transiently unavailable at startup.
      this._initError = undefined;
      this._initPromise = this._autoInitialize().catch((error) => {
        this._initError =
          error instanceof Error ? error : new Error(String(error));
        console.error(this._initError);
      });
      await this._initPromise;
      if (this._initError) {
        throw this._initError;
      }
    }
  }

  private async getEntityStore(): Promise<VectorStore> {
    if (!this._entityStore) {
      const entityCollectionName = `${this.collectionName}_entities`;
      const entityConfig = {
        ...this.config.vectorStore.config,
        collectionName: entityCollectionName,
      };
      // For file-based stores (memory/SQLite), always use a separate DB for entities
      if (this.config.vectorStore.provider === "memory") {
        const basePath = entityConfig.dbPath || getDefaultVectorStoreDbPath();
        entityConfig.dbPath = basePath.replace(/\.db$/, "_entities.db");
      }
      this._entityStore = VectorStoreFactory.create(
        this.config.vectorStore.provider,
        entityConfig,
      );
      await this._entityStore.initialize();
    }
    return this._entityStore;
  }

  /**
   * Normalize a filters object for entity-store scoping: keeps only
   * user_id/agent_id/run_id keys whose values are defined.
   */
  private _sessionFiltersFromPayload(
    payload: Record<string, any>,
  ): Record<string, any> {
    const filters: Record<string, any> = {};
    for (const key of SCOPE_KEYS) {
      const value = this._payloadScopeValue(payload, key);
      if (value !== undefined && value !== null) {
        filters[key] = value;
      }
    }
    return filters;
  }

  private _payloadScopeValue(payload: Record<string, any>, key: ScopeKey): any {
    const canonicalValue = payload[key];
    if (canonicalValue !== undefined && canonicalValue !== null) {
      return canonicalValue;
    }
    return payload[SCOPE_KEY_ALIASES[key]];
  }

  private _metadataFromPayload(
    payload: Record<string, any>,
  ): Record<string, any> {
    const metadata: Record<string, any> = {};
    for (const [key, value] of Object.entries(payload)) {
      if (!RESERVED_PAYLOAD_KEYS.has(key)) {
        metadata[key] = value;
      }
    }
    return metadata;
  }

  private _payloadCreatedAt(payload: Record<string, any>): any {
    return payload.createdAt ?? payload.created_at;
  }

  private _payloadUpdatedAt(payload: Record<string, any>): any {
    return payload.updatedAt ?? payload.updated_at;
  }

  private _providerFiltersForRequestedScope(
    filters: Record<string, any>,
  ): Record<string, any> | undefined {
    const providerFilters = this._stripScopeWildcardsForProvider(filters);
    if (!providerFilters) {
      return undefined;
    }

    const provider = this.config.vectorStore.provider.toLowerCase();
    if (["pgvector", "qdrant"].includes(provider)) {
      return this._providerFilterFromAlternatives(
        this._providerScopeAliasAlternatives(providerFilters),
      );
    }

    if (!this._providerSupportsLogicalFilters(provider)) {
      return this._stripUnsupportedLogicalFiltersForProvider(providerFilters);
    }

    return providerFilters;
  }

  private _isLogicalFilterKey(key: string): boolean {
    return (
      key === "AND" ||
      key === "OR" ||
      key === "NOT" ||
      key === "$and" ||
      key === "$or" ||
      key === "$not"
    );
  }

  private _providerSupportsLogicalFilters(provider: string): boolean {
    return provider === "memory";
  }

  private _stripUnsupportedLogicalFiltersForProvider(
    filter: Record<string, any>,
  ): Record<string, any> | undefined {
    const result: Record<string, any> = {};

    for (const [key, value] of Object.entries(filter)) {
      if (this._isLogicalFilterKey(key)) {
        continue;
      }
      result[key] = value;
    }

    return Object.keys(result).length > 0 ? result : undefined;
  }

  private _stripScopeWildcardsForProvider(
    filter: Record<string, any>,
  ): Record<string, any> | undefined {
    const result: Record<string, any> = {};

    for (const [key, value] of Object.entries(filter)) {
      if (this._canonicalScopeKey(key) && value === "*") {
        continue;
      }

      if (this._isLogicalFilterKey(key) && Array.isArray(value)) {
        const logicalFilters: Record<string, any>[] = [];
        let logicalFilterIsUnrestricted = false;

        for (const condition of value) {
          if (
            !condition ||
            typeof condition !== "object" ||
            Array.isArray(condition)
          ) {
            logicalFilters.push(condition);
            continue;
          }

          const stripped = this._stripScopeWildcardsForProvider(condition);
          if (!stripped) {
            if (key === "OR" || key === "$or") {
              logicalFilterIsUnrestricted = true;
              break;
            }
            continue;
          }
          logicalFilters.push(stripped);
        }

        if (!logicalFilterIsUnrestricted && logicalFilters.length > 0) {
          result[key] = logicalFilters;
        }
        continue;
      }

      result[key] = value;
    }

    return Object.keys(result).length > 0 ? result : undefined;
  }

  private _wildcardScopeKeys(
    filter: unknown,
    keys = new Set<ScopeKey>(),
  ): Set<ScopeKey> {
    if (!filter || typeof filter !== "object") {
      return keys;
    }

    if (Array.isArray(filter)) {
      for (const item of filter) {
        this._wildcardScopeKeys(item, keys);
      }
      return keys;
    }

    for (const [key, value] of Object.entries(filter)) {
      const scopeKey = this._canonicalScopeKey(key);
      if (scopeKey && value === "*") {
        keys.add(scopeKey);
      }

      if (this._isLogicalFilterKey(key)) {
        this._wildcardScopeKeys(value, keys);
      }
    }

    return keys;
  }

  private _rejectWildcardScopeFilters(
    filter: Record<string, any>,
    methodName: string,
  ): void {
    const wildcardScopeKeys = SCOPE_KEYS.filter((key) =>
      this._wildcardScopeKeys(filter).has(key),
    );

    if (wildcardScopeKeys.length === 0) {
      return;
    }

    const suffix =
      methodName === "deleteAll"
        ? " because it is destructive. Provide explicit scope values, or use reset() to delete all memories."
        : ". Provide explicit scope values.";

    throw new Error(
      `Wildcard scope filters [${wildcardScopeKeys.join(", ")}] are not supported in ${methodName}()${suffix}`,
    );
  }

  private _providerScopeAliasAlternatives(
    filter: Record<string, any>,
  ): Record<string, any>[] {
    let alternatives: Record<string, any>[] = [{}];

    const appendAndClauses = (
      filterObject: Record<string, any>,
      clauses: Record<string, any>[],
    ): Record<string, any> => {
      const nonEmptyClauses = clauses.filter(
        (clause) => Object.keys(clause).length > 0,
      );
      if (nonEmptyClauses.length === 0) {
        return filterObject;
      }

      const existingAnd = Array.isArray(filterObject.$and)
        ? filterObject.$and
        : filterObject.$and !== undefined
          ? [filterObject.$and]
          : [];

      return {
        ...filterObject,
        $and: [...existingAnd, ...nonEmptyClauses],
      };
    };

    const mergeConjunctiveFilters = (
      left: Record<string, any>,
      right: Record<string, any>,
    ): Record<string, any> => {
      let merged = { ...left };

      for (const [key, value] of Object.entries(right)) {
        if (!(key in merged)) {
          merged[key] = value;
          continue;
        }

        if (
          key === "$and" &&
          Array.isArray(merged.$and) &&
          Array.isArray(value)
        ) {
          merged = appendAndClauses(merged, value);
          continue;
        }

        const existingValue = merged[key];
        delete merged[key];
        merged = appendAndClauses(merged, [
          { [key]: existingValue },
          { [key]: value },
        ]);
      }

      return merged;
    };

    const mergeAlternatives = (branches: Record<string, any>[]) => {
      alternatives = alternatives.flatMap((alternative) =>
        branches.map((branch) => mergeConjunctiveFilters(alternative, branch)),
      );
    };

    const appendToAlternatives = (key: string, value: any) => {
      alternatives = alternatives.map((alternative) => ({
        ...alternative,
        [key]: value,
      }));
    };

    for (const [key, value] of Object.entries(filter)) {
      if (key === "AND" || key === "$and") {
        if (!Array.isArray(value)) {
          appendToAlternatives(key, value);
          continue;
        }
        for (const condition of value) {
          if (
            condition &&
            typeof condition === "object" &&
            !Array.isArray(condition)
          ) {
            mergeAlternatives(this._providerScopeAliasAlternatives(condition));
          }
        }
        continue;
      }

      if (key === "OR" || key === "$or") {
        if (!Array.isArray(value)) {
          appendToAlternatives(key, value);
          continue;
        }
        const branches = value.flatMap((condition) =>
          condition &&
          typeof condition === "object" &&
          !Array.isArray(condition)
            ? this._providerScopeAliasAlternatives(condition)
            : [],
        );
        if (branches.some((branch) => Object.keys(branch).length === 0)) {
          continue;
        }
        if (branches.length > 0) {
          mergeAlternatives(branches);
        }
        continue;
      }

      if (key === "NOT" || key === "$not") {
        if (!Array.isArray(value)) {
          appendToAlternatives(key, value);
          continue;
        }
        const notBranches = value.flatMap((condition) =>
          condition &&
          typeof condition === "object" &&
          !Array.isArray(condition)
            ? this._providerScopeAliasAlternatives(condition)
            : [],
        );
        const nonEmptyBranches = notBranches.filter(
          (branch) => Object.keys(branch).length > 0,
        );
        if (nonEmptyBranches.length > 0) {
          alternatives = alternatives.map((alternative) => ({
            ...alternative,
            $not: [
              ...((alternative.$not as Record<string, any>[] | undefined) ??
                []),
              ...nonEmptyBranches,
            ],
          }));
        }
        continue;
      }

      const scopeKey = this._canonicalScopeKey(key);
      if (scopeKey) {
        mergeAlternatives([
          { [scopeKey]: value },
          { [SCOPE_KEY_ALIASES[scopeKey]]: value },
        ]);
        continue;
      }

      appendToAlternatives(key, value);
    }

    return alternatives;
  }

  private _providerFilterFromAlternatives(
    alternatives: Record<string, any>[],
  ): Record<string, any> | undefined {
    const nonEmptyAlternatives = alternatives.filter(
      (alternative) => Object.keys(alternative).length > 0,
    );
    if (nonEmptyAlternatives.length === 0) {
      return undefined;
    }
    if (nonEmptyAlternatives.length === 1) {
      return nonEmptyAlternatives[0];
    }
    return { $or: nonEmptyAlternatives };
  }

  private _providerListCountIsTotal(): boolean {
    return ["memory", "pgvector", "redis", "supabase"].includes(
      this.config.vectorStore.provider.toLowerCase(),
    );
  }

  private async _listByRequestedScope(
    filters: Record<string, any>,
    options: {
      topK?: number;
      initialLimit: number;
      exhaustive?: boolean;
    },
  ): Promise<VectorStoreResult[]> {
    if (!options.exhaustive && options.topK === 0) {
      return [];
    }

    const providerFilters = this._providerFiltersForRequestedScope(filters);
    const providerReturnsTotalCount = this._providerListCountIsTotal();
    const provider = this.config.vectorStore.provider;
    let fetchLimit = options.initialLimit;
    let scoped: VectorStoreResult[] = [];

    while (true) {
      const [rawMemories, rawCount] = await this.vectorStore.list(
        providerFilters,
        fetchLimit,
      );
      scoped = this.filterByRequestedScope(rawMemories, filters);

      if (
        !options.exhaustive &&
        options.topK !== undefined &&
        scoped.length >= options.topK
      ) {
        return scoped.slice(0, options.topK);
      }

      const total = providerReturnsTotalCount ? Number(rawCount) : undefined;
      if (total !== undefined && Number.isFinite(total) && fetchLimit < total) {
        const nextLimit = options.exhaustive
          ? total
          : Math.min(total, Math.max(fetchLimit * 2, fetchLimit + 1));

        if (nextLimit > fetchLimit) {
          fetchLimit = nextLimit;
          continue;
        }
      }

      if (
        options.exhaustive &&
        !providerReturnsTotalCount &&
        rawMemories.length >= fetchLimit
      ) {
        throw new Error(
          `deleteAll cannot safely delete all scoped memories for vector store provider '${provider}' because list() returned a full page without a total count. Narrow the scope filters or delete matching memories individually.`,
        );
      }

      if (
        !options.exhaustive &&
        !providerReturnsTotalCount &&
        options.topK !== undefined &&
        scoped.length < options.topK &&
        rawMemories.length >= fetchLimit
      ) {
        throw new Error(
          `getAll cannot safely return all requested scoped memories for vector store provider '${provider}' because list() returned a full page without a total count. Narrow the scope filters or lower topK.`,
        );
      }

      if (
        total === undefined ||
        !Number.isFinite(total) ||
        fetchLimit >= total
      ) {
        return options.topK === undefined
          ? scoped
          : scoped.slice(0, options.topK);
      }
    }
  }

  private async _deleteAllByRequestedScope(
    filters: Record<string, any>,
  ): Promise<number> {
    const providerFilters = this._providerFiltersForRequestedScope(filters);
    const providerReturnsTotalCount = this._providerListCountIsTotal();
    const provider = this.config.vectorStore.provider;
    let deletedCount = 0;
    const deletedIds = new Set<string>();

    while (true) {
      const [rawMemories, rawCount] = await this.vectorStore.list(
        providerFilters,
        DELETE_ALL_SCOPE_FETCH_LIMIT,
      );
      const scoped = this.filterByRequestedScope(rawMemories, filters);

      if (
        !providerReturnsTotalCount &&
        rawMemories.length >= DELETE_ALL_SCOPE_FETCH_LIMIT
      ) {
        throw new Error(
          `deleteAll cannot safely delete all scoped memories for vector store provider '${provider}' because list() returned a full page without a total count. Narrow the scope filters or delete matching memories individually.`,
        );
      }

      if (scoped.length === 0) {
        const total = providerReturnsTotalCount ? Number(rawCount) : undefined;
        if (
          total !== undefined &&
          Number.isFinite(total) &&
          total > 0 &&
          total > rawMemories.length &&
          rawMemories.length >= DELETE_ALL_SCOPE_FETCH_LIMIT
        ) {
          throw new Error(
            `deleteAll cannot safely delete all scoped memories for vector store provider '${provider}' because scoped rows may be hidden behind a full provider page. Narrow the scope filters or delete matching memories individually.`,
          );
        }
        return deletedCount;
      }

      const nextScoped = scoped.filter((memory) => !deletedIds.has(memory.id));
      if (nextScoped.length === 0) {
        throw new Error(
          `deleteAll cannot safely delete all scoped memories for vector store provider '${provider}' because repeated list() calls made no deletion progress. Narrow the scope filters or delete matching memories individually.`,
        );
      }

      for (const memory of nextScoped) {
        await this.deleteMemory(memory.id);
        deletedIds.add(memory.id);
      }
      deletedCount += nextScoped.length;

      if (rawMemories.length < DELETE_ALL_SCOPE_FETCH_LIMIT) {
        return deletedCount;
      }
    }
  }

  private _normalizeEntityText(value: string): string {
    return value.trim().toLowerCase().replace(/\s+/g, " ");
  }

  private async _existingEntitiesByText(
    entityStore: VectorStore,
    filters: Record<string, any>,
  ): Promise<Map<string, { id: string; payload: Record<string, any> }>> {
    const rowsByText = new Map<
      string,
      { id: string; payload: Record<string, any> }
    >();
    let rows: Array<{ id: string; payload: Record<string, any> }> = [];
    try {
      const listed = await entityStore.list(filters, 10000);
      rows = (
        Array.isArray(listed) && Array.isArray(listed[0])
          ? listed[0]
          : (listed as any)
      ) as Array<{ id: string; payload: Record<string, any> }>;
    } catch (e) {
      console.debug(
        `Exact entity lookup failed, falling back to semantic dedup: ${e}`,
      );
      return rowsByText;
    }

    for (const row of rows) {
      const text = row.payload?.data;
      if (typeof text !== "string") continue;
      const key = this._normalizeEntityText(text);
      if (key && !rowsByText.has(key)) {
        rowsByText.set(key, row);
      }
    }
    return rowsByText;
  }

  /**
   * Remove `memoryId` from every entity record scoped to `filters`.
   * If an entity's `linkedMemoryIds` becomes empty after removal, the
   * entity record itself is deleted. Errors on individual entities are
   * swallowed so one bad record does not break the whole operation.
   *
   * No-op if the entity store has not been initialized yet.
   */
  private async _removeMemoryFromEntityStore(
    memoryId: string,
    filters: Record<string, any>,
  ): Promise<void> {
    let entityStore: VectorStore;
    try {
      entityStore = await this.getEntityStore();
    } catch (e) {
      console.debug(`Entity store unavailable during cleanup: ${e}`);
      return;
    }

    let rows: Array<{ id: string; payload: Record<string, any> }> = [];
    try {
      const listed = await entityStore.list(filters, 10000);
      rows = (
        Array.isArray(listed) && Array.isArray(listed[0])
          ? listed[0]
          : (listed as any)
      ) as Array<{ id: string; payload: Record<string, any> }>;
    } catch (e) {
      console.debug(`Entity store list failed during cleanup: ${e}`);
      return;
    }

    for (const row of rows) {
      try {
        const payload = row.payload || {};
        const linked: string[] = Array.isArray(payload.linkedMemoryIds)
          ? payload.linkedMemoryIds
          : [];
        if (!linked.includes(memoryId)) continue;

        const remaining = linked.filter((id) => id !== memoryId);
        if (remaining.length === 0) {
          try {
            await entityStore.delete(row.id);
          } catch (e) {
            console.debug(`Entity delete failed for id=${row.id}: ${e}`);
          }
        } else {
          const newPayload = { ...payload, linkedMemoryIds: remaining };
          // entityStore.update requires a vector — re-embed entity text.
          const entityText =
            typeof payload.data === "string" ? payload.data : "";
          if (!entityText) {
            // Can't re-embed without text; skip gracefully.
            console.debug(
              `Entity id=${row.id} missing 'data'; skipping update during cleanup`,
            );
            continue;
          }
          let vec: number[];
          try {
            vec = await this.embedder.embed(entityText);
          } catch (e) {
            console.debug(`Entity re-embed failed for '${entityText}': ${e}`);
            continue;
          }
          try {
            await entityStore.update(row.id, vec, newPayload);
          } catch (e) {
            console.debug(`Entity update failed for id=${row.id}: ${e}`);
          }
        }
      } catch (e) {
        console.debug(`Entity cleanup error for id=${row?.id}: ${e}`);
      }
    }
  }

  /**
   * Extract entities from `text` and link them to `memoryId` in the
   * entity store, scoped to `filters` (user_id / agent_id / run_id).
   *
   * Simpler single-memory variant of Phase 7 in add(): no cross-memory
   * dedup, but still does per-entity "search for existing, update if
   * match >= 0.95 else insert new". Non-fatal errors are swallowed.
   */
  private async _linkEntitiesForMemory(
    memoryId: string,
    text: string,
    filters: Record<string, any>,
  ): Promise<void> {
    try {
      const entities = extractEntities(text);
      if (entities.length === 0) return;

      const entityStore = await this.getEntityStore();
      const exactMatches = await this._existingEntitiesByText(
        entityStore,
        filters,
      );

      for (const entity of entities) {
        try {
          let entityVec: number[];
          try {
            entityVec = await this.embedder.embed(entity.text);
          } catch (e) {
            console.debug(`Entity embed failed for '${entity.text}': ${e}`);
            continue;
          }

          let matches: Array<{
            id: string;
            score?: number;
            payload: Record<string, any>;
          }> = [];
          const exactMatch = exactMatches.get(
            this._normalizeEntityText(entity.text),
          );
          if (!exactMatch) {
            try {
              matches = await entityStore.search(entityVec, 1, filters);
            } catch {}
          }

          const semanticMatch =
            matches.length > 0 && (matches[0].score ?? 0) >= 0.95
              ? matches[0]
              : undefined;
          const match = exactMatch ?? semanticMatch;
          if (match) {
            const payload = match.payload || {};
            const linked = new Set<string>(
              Array.isArray(payload.linkedMemoryIds)
                ? payload.linkedMemoryIds
                : [],
            );
            linked.add(memoryId);
            payload.linkedMemoryIds = Array.from(linked).sort();
            try {
              await entityStore.update(match.id, entityVec, payload);
            } catch (e) {
              console.debug(`Entity update failed for '${entity.text}': ${e}`);
            }
          } else {
            const entityPayload: Record<string, any> = {
              data: entity.text,
              entityType: entity.type,
              linkedMemoryIds: [memoryId],
            };
            if (filters.user_id) entityPayload.user_id = filters.user_id;
            if (filters.agent_id) entityPayload.agent_id = filters.agent_id;
            if (filters.run_id) entityPayload.run_id = filters.run_id;

            try {
              await entityStore.insert(
                [entityVec],
                [uuidv4()],
                [entityPayload],
              );
            } catch (e) {
              console.debug(`Entity insert failed for '${entity.text}': ${e}`);
            }
          }
        } catch (e) {
          console.debug(`Entity link error for '${entity.text}': ${e}`);
        }
      }
    } catch (e) {
      console.warn(`Entity linking failed during update: ${e}`);
    }
  }

  private buildSessionScope(filters: SearchFilters): string {
    const parts: string[] = [];
    for (const key of ["agent_id", "run_id", "user_id"].sort()) {
      const val = (filters as any)[key];
      if (val) parts.push(`${key}=${val}`);
    }
    return parts.join("&");
  }

  private filterByRequestedScope<T extends Pick<VectorStoreResult, "payload">>(
    results: T[],
    filters: Record<string, any>,
  ): T[] {
    if (!this._filterContainsScope(filters)) {
      return results;
    }

    // Defense-in-depth after provider filtering: replay filters that contain
    // requested scope keys so provider drift cannot leak or delete wrong-scope
    // rows. Bounded vector-store APIs do not expose a shared cursor, so callers
    // may see fewer rows if polluted rows crowd out valid in-scope rows.
    return results.filter((result) =>
      this._matchesScopeFilter(result.payload ?? {}, filters),
    );
  }

  private _canonicalScopeKey(key: string): ScopeKey | undefined {
    if ((SCOPE_KEYS as readonly string[]).includes(key)) {
      return key as ScopeKey;
    }

    for (const [scopeKey, alias] of Object.entries(SCOPE_KEY_ALIASES)) {
      if (alias === key) {
        return scopeKey as ScopeKey;
      }
    }

    return undefined;
  }

  private _filterContainsScope(filter: any): boolean {
    if (!filter || typeof filter !== "object" || Array.isArray(filter)) {
      return false;
    }

    for (const [key, value] of Object.entries(filter)) {
      if (
        this._canonicalScopeKey(key) &&
        value !== undefined &&
        value !== null
      ) {
        return true;
      }
      if (
        (key === "AND" ||
          key === "OR" ||
          key === "NOT" ||
          key === "$and" ||
          key === "$or" ||
          key === "$not") &&
        Array.isArray(value) &&
        value.some((condition) => this._filterContainsScope(condition))
      ) {
        return true;
      }
    }

    return false;
  }

  private _matchesScopeFilter(
    payload: Record<string, any>,
    filter: any,
  ): boolean {
    if (!filter || typeof filter !== "object" || Array.isArray(filter)) {
      return true;
    }

    for (const [key, value] of Object.entries(filter)) {
      if (key === "AND" || key === "$and") {
        if (!Array.isArray(value)) {
          return false;
        }
        if (
          !value.every((condition) =>
            this._matchesScopeFilter(payload, condition),
          )
        ) {
          return false;
        }
        continue;
      }

      if (key === "OR" || key === "$or") {
        if (!Array.isArray(value) || value.length === 0) {
          return false;
        }
        if (
          !value.some((condition) =>
            this._matchesScopeFilter(payload, condition),
          )
        ) {
          return false;
        }
        continue;
      }

      if (key === "NOT" || key === "$not") {
        if (!Array.isArray(value)) {
          return false;
        }
        if (
          value.some((condition) =>
            this._matchesScopeFilter(payload, condition),
          )
        ) {
          return false;
        }
        continue;
      }

      const scopeKey = this._canonicalScopeKey(key);
      if (value === undefined || value === null) {
        continue;
      }

      if (!this._matchesFieldCondition(payload, key, value, scopeKey)) {
        return false;
      }
    }

    return true;
  }

  private _matchesFieldCondition(
    payload: Record<string, any>,
    key: string,
    condition: any,
    scopeKey?: ScopeKey,
  ): boolean {
    const payloadValue = scopeKey
      ? this._payloadScopeValue(payload, scopeKey)
      : payload[key];

    if (condition === "*") {
      return scopeKey
        ? payloadValue !== undefined && payloadValue !== null
        : true;
    }

    if (Array.isArray(condition)) {
      return condition.includes(payloadValue);
    }

    if (typeof condition === "object" && condition !== null) {
      for (const [operator, value] of Object.entries(condition)) {
        if (operator === "eq") {
          if (payloadValue !== value) return false;
        } else if (operator === "ne") {
          if (
            (scopeKey &&
              (payloadValue === undefined || payloadValue === null)) ||
            payloadValue === value
          ) {
            return false;
          }
        } else if (operator === "gt") {
          if (!this._compareFilterValues(payloadValue, value, ">")) {
            return false;
          }
        } else if (operator === "gte") {
          if (!this._compareFilterValues(payloadValue, value, ">=")) {
            return false;
          }
        } else if (operator === "lt") {
          if (!this._compareFilterValues(payloadValue, value, "<")) {
            return false;
          }
        } else if (operator === "lte") {
          if (!this._compareFilterValues(payloadValue, value, "<=")) {
            return false;
          }
        } else if (operator === "in") {
          if (!Array.isArray(value) || !value.includes(payloadValue)) {
            return false;
          }
        } else if (operator === "nin") {
          if (
            !Array.isArray(value) ||
            (scopeKey &&
              (payloadValue === undefined || payloadValue === null)) ||
            value.includes(payloadValue)
          ) {
            return false;
          }
        } else if (operator === "contains") {
          if (
            typeof payloadValue !== "string" ||
            !payloadValue.includes(String(value))
          ) {
            return false;
          }
        } else if (operator === "icontains") {
          if (
            typeof payloadValue !== "string" ||
            !payloadValue.toLowerCase().includes(String(value).toLowerCase())
          ) {
            return false;
          }
        } else {
          return false;
        }
      }
      return true;
    }

    return payloadValue === condition;
  }

  private _compareFilterValues(
    payloadValue: any,
    filterValue: any,
    operator: ">" | ">=" | "<" | "<=",
  ): boolean {
    if (payloadValue === undefined || payloadValue === null) {
      return false;
    }

    const payloadNumber = Number(payloadValue);
    const filterNumber = Number(filterValue);
    if (Number.isFinite(payloadNumber) && Number.isFinite(filterNumber)) {
      if (operator === ">") return payloadNumber > filterNumber;
      if (operator === ">=") return payloadNumber >= filterNumber;
      if (operator === "<") return payloadNumber < filterNumber;
      return payloadNumber <= filterNumber;
    }

    const payloadTime =
      payloadValue instanceof Date
        ? payloadValue.getTime()
        : Date.parse(String(payloadValue));
    const filterTime =
      filterValue instanceof Date
        ? filterValue.getTime()
        : Date.parse(String(filterValue));
    if (Number.isFinite(payloadTime) && Number.isFinite(filterTime)) {
      if (operator === ">") return payloadTime > filterTime;
      if (operator === ">=") return payloadTime >= filterTime;
      if (operator === "<") return payloadTime < filterTime;
      return payloadTime <= filterTime;
    }

    return false;
  }

  private async _initializeTelemetry() {
    try {
      await this._getTelemetryId();

      // Capture initialization event
      await captureClientEvent("init", this, {
        api_version: this.apiVersion,
        client_type: "Memory",
        collection_name: this.collectionName,
      });
    } catch (error) {}
  }

  private async _getTelemetryId() {
    try {
      if (
        !this.telemetryId ||
        this.telemetryId === "anonymous" ||
        this.telemetryId === "anonymous-supabase"
      ) {
        this.telemetryId =
          (await getOrCreateMem0UserId()) ||
          (await this.vectorStore.getUserId());
        try {
          await this.vectorStore.setUserId(this.telemetryId);
        } catch {}
      }
      return this.telemetryId;
    } catch (error) {
      this.telemetryId = "anonymous";
      return this.telemetryId;
    }
  }

  private async _captureEvent(methodName: string, additionalData = {}) {
    try {
      await this._getTelemetryId();
      await captureClientEvent(methodName, this, {
        ...additionalData,
        api_version: this.apiVersion,
        collection_name: this.collectionName,
      });
    } catch (error) {
      console.error(`Failed to capture ${methodName} event:`, error);
    }
  }

  private async _displayFirstRunNotice(triggerFunction: string) {
    try {
      await this._getTelemetryId();
      await displayFirstRunNotice(this, triggerFunction);
    } catch {}
  }

  private async _displayDecayUsageNotice(trigger: {
    triggerFunction: "delete" | "delete_all";
    triggerSource: "delete_count" | "delete_all";
    triggerReason: "repeated_deletes" | "bulk_delete";
    deleteCount?: number;
    deletedCount?: number;
  }) {
    try {
      await this._getTelemetryId();
      await displayDecayUsageNotice(this, trigger);
    } catch {}
  }

  private async _displayTemporalUsageNotice(trigger: {
    triggerFunction: "add" | "search";
    triggerSource: "metadata" | "query" | "filter";
    triggerReason:
      | "date_like_metadata"
      | "relative_phrase"
      | "date_like_query"
      | "date_range_filter";
  }) {
    try {
      await this._getTelemetryId();
      await displayTemporalUsageNotice(this, trigger);
    } catch {}
  }

  private async _displayScaleThresholdNotice(trigger: ScaleThresholdTrigger) {
    try {
      await this._getTelemetryId();
      await displayScaleThresholdNotice(this, trigger);
    } catch {}
  }

  private async _displayPerformanceSlowQueryNotice(
    trigger: PerformanceSlowQueryTrigger,
  ) {
    try {
      await this._getTelemetryId();
      await displayPerformanceSlowQueryNotice(this, trigger);
    } catch {}
  }

  private async _getNoticeTelemetryId() {
    try {
      if (
        !this.telemetryId ||
        this.telemetryId === "anonymous" ||
        this.telemetryId === "anonymous-supabase"
      ) {
        this.telemetryId = (await getOrCreateMem0UserId()) || "anonymous";
      }
      return this.telemetryId;
    } catch {
      this.telemetryId = "anonymous";
      return this.telemetryId;
    }
  }

  static fromConfig(configDict: Record<string, any>): Memory {
    try {
      const config = MemoryConfigSchema.parse(configDict);
      return new Memory(config);
    } catch (e) {
      console.error("Configuration validation error:", e);
      throw e;
    }
  }

  async updateProject(options: UpdateProjectOptions = {}): Promise<never> {
    if (options?.decay === true) {
      await this._getNoticeTelemetryId();
      throw new Error(await getDecayFeatureErrorMessage(this));
    }

    throw new Error("Project updates are not supported by the OSS Memory SDK.");
  }

  async add(
    messages: string | Message[],
    config: AddMemoryOptions,
  ): Promise<SearchResult> {
    if (config?.timestamp !== undefined) {
      await this._getNoticeTelemetryId();
      throw new Error(
        await getTemporalFeatureErrorMessage(this, {
          triggerFunction: "add",
          triggerParameter: "timestamp",
        }),
      );
    }

    // Validate messages input
    if (messages === undefined || messages === null) {
      throw new Error(
        "messages is required and cannot be undefined or null. Provide a string or array of messages.",
      );
    }
    if (Array.isArray(messages)) {
      if (messages.length === 0) {
        throw new Error(
          "messages array cannot be empty. Provide at least one message with non-empty content.",
        );
      }
      const allBlank = messages.every(
        (m) => typeof m.content === "string" && m.content.trim() === "",
      );
      if (allBlank) {
        throw new Error(
          "messages array cannot contain only blank content. Provide at least one message with non-empty content.",
        );
      }
    } else if (messages.trim() === "") {
      throw new Error(
        "messages string cannot be empty. Provide non-empty content.",
      );
    }

    const temporalUsageNotice = detectTemporalUsageFromMetadata(
      config?.metadata,
    );

    await this._ensureInitialized();
    await this._captureEvent("add", {
      message_count: Array.isArray(messages) ? messages.length : 1,
      has_metadata: !!config.metadata,
      has_filters: !!config.filters,
      infer: config.infer,
    });
    const { metadata = {}, filters = {}, infer = true } = config;

    // Validate and trim entity IDs
    const userId = validateAndTrimEntityId(config.userId, "userId");
    const agentId = validateAndTrimEntityId(config.agentId, "agentId");
    const runId = validateAndTrimEntityId(config.runId, "runId");

    // Convert camelCase entity params to snake_case for storage (matches API and search/getAll filters)
    if (userId) filters.user_id = metadata.user_id = userId;
    if (agentId) filters.agent_id = metadata.agent_id = agentId;
    if (runId) filters.run_id = metadata.run_id = runId;

    if (!filters.user_id && !filters.agent_id && !filters.run_id) {
      throw new Error(
        "One of the filters: userId, agentId or runId is required!",
      );
    }

    const parsedMessages = Array.isArray(messages)
      ? (messages as Message[])
      : [{ role: "user", content: messages }];

    const final_parsedMessages = await parse_vision_messages(parsedMessages);

    // Add to vector store
    const vectorStoreResult = await this.addToVectorStore(
      final_parsedMessages,
      metadata,
      filters,
      infer,
    );

    if (temporalUsageNotice) {
      await this._displayTemporalUsageNotice({
        triggerFunction: "add",
        triggerSource: temporalUsageNotice.triggerSource,
        triggerReason: temporalUsageNotice.triggerReason,
      });
    } else {
      const scaleThresholdNotice = await detectScaleThresholdFromAddResult(
        this,
        vectorStoreResult,
      );
      if (scaleThresholdNotice) {
        await this._displayScaleThresholdNotice({
          triggerFunction: "add",
          ...scaleThresholdNotice,
        });
      } else {
        await this._displayFirstRunNotice("add");
      }
    }

    return {
      results: vectorStoreResult,
    };
  }

  private async addToVectorStore(
    messages: Message[],
    metadata: Record<string, any>,
    filters: SearchFilters,
    infer: boolean,
  ): Promise<MemoryItem[]> {
    if (!infer) {
      const returnedMemories: MemoryItem[] = [];
      for (const message of messages) {
        if (message.role === "system") {
          continue;
        }
        const memoryId = await this.createMemory(
          message.content as string,
          {},
          metadata,
        );
        returnedMemories.push({
          id: memoryId,
          memory: message.content as string,
          metadata: { event: "ADD" },
        });
      }
      return returnedMemories;
    }

    // === V3 PHASED BATCH PIPELINE ===

    // Phase 0: Context gathering
    const sessionScope = this.buildSessionScope(filters);
    let lastMessages: Array<{
      role: string;
      content: string;
      name?: string;
    }> = [];
    if (typeof this.db.getLastMessages === "function") {
      try {
        lastMessages = await this.db.getLastMessages(sessionScope, 10);
      } catch {
        // getLastMessages not supported — proceed without context
      }
    }
    // Preserve role on the messages being extracted so the prompt's role-aware
    // logic and the required `attributed_to` output have the speaker to work
    // with. Matches the Python oss `parse_messages` helper (`role: content`);
    // without this, assistant statements get attributed to the user.
    const parsedMessages = messages
      .map((m) => `${m.role}: ${m.content}`)
      .join("\n");

    // Phase 1: Existing memory retrieval
    const queryEmbedding = await this.embedder.embed(parsedMessages);
    const providerFilters = this._providerFiltersForRequestedScope(filters);
    const existingResults = this.filterByRequestedScope(
      await this.vectorStore.search(
        queryEmbedding,
        MIN_SCOPE_POST_FILTER_FETCH,
        providerFilters,
      ),
      filters,
    );

    // Map UUIDs to integers (anti-hallucination)
    const existingMemories: Array<{ id: string; text: string }> = [];
    const uuidMapping: Record<string, string> = {};
    for (let idx = 0; idx < existingResults.length; idx++) {
      const mem = existingResults[idx];
      uuidMapping[String(idx)] = mem.id;
      existingMemories.push({
        id: String(idx),
        text: mem.payload?.data ?? "",
      });
    }

    // Phase 2: LLM extraction (single call)
    const isAgentScoped = !!filters.agent_id && !filters.user_id;
    let systemPrompt = ADDITIVE_EXTRACTION_PROMPT;
    if (isAgentScoped) {
      systemPrompt += AGENT_CONTEXT_SUFFIX;
    }

    const userPrompt = generateAdditiveExtractionPrompt({
      existingMemories,
      newMessages: parsedMessages,
      lastKMessages: lastMessages,
      customInstructions: this.customInstructions,
    });

    let response: string;
    try {
      response = (await this.llm.generateResponse(
        [
          { role: "system", content: systemPrompt },
          { role: "user", content: userPrompt },
        ],
        { type: "json_object" },
      )) as string;
    } catch (e) {
      console.error("LLM extraction failed:", e);
      return [];
    }

    // Parse response
    let extractedMemories: Array<{
      id?: string;
      text?: string;
      attributed_to?: string;
      linked_memory_ids?: string[];
    }> = [];
    try {
      const cleanResponse = extractJson(response);
      if (cleanResponse && cleanResponse.trim()) {
        try {
          const parsed = AdditiveExtractionSchema.parse(
            JSON.parse(cleanResponse),
          );
          extractedMemories = parsed.memory;
        } catch {
          const fallbackJson = extractJson(cleanResponse);
          extractedMemories = JSON.parse(fallbackJson)?.memory ?? [];
        }
      }
    } catch (e) {
      console.error("Error parsing extraction response:", e);
      extractedMemories = [];
    }

    if (extractedMemories.length === 0) {
      // Save messages even if nothing extracted
      if (typeof this.db.saveMessages === "function") {
        try {
          await this.db.saveMessages(
            messages.map((m) => ({
              role: m.role,
              content: m.content as string,
            })),
            sessionScope,
          );
        } catch {}
      }
      return [];
    }

    // Phase 3: Batch embed all extracted memory texts
    const memTexts = extractedMemories
      .map((m) => m.text ?? "")
      .filter((t) => t.length > 0);
    let embedMap: Record<string, number[]> = {};
    try {
      const memEmbeddingsList = await this.embedder.embedBatch(memTexts);
      for (let i = 0; i < memTexts.length; i++) {
        embedMap[memTexts[i]] = memEmbeddingsList[i];
      }
    } catch {
      // Fallback: embed individually
      for (const text of memTexts) {
        try {
          embedMap[text] = await this.embedder.embed(text);
        } catch (e) {
          console.warn(`Failed to embed memory text: ${e}`);
        }
      }
    }

    // Phase 4-5: CPU processing + hash dedup
    const existingHashes = new Set<string>();
    for (const mem of existingResults) {
      const h = mem.payload?.hash;
      if (h) existingHashes.add(h);
    }

    const records: Array<{
      memoryId: string;
      text: string;
      embedding: number[];
      payload: Record<string, any>;
    }> = [];
    const seenHashes = new Set<string>();

    for (const mem of extractedMemories) {
      const text = mem.text;
      if (!text || !(text in embedMap)) continue;

      const memHash = createHash("md5").update(text).digest("hex");
      if (existingHashes.has(memHash) || seenHashes.has(memHash)) {
        continue;
      }
      seenHashes.add(memHash);

      const textLemmatized = lemmatizeForBm25(text);
      const memoryId = uuidv4();
      const now = new Date().toISOString();

      const memPayload: Record<string, any> = {
        ...metadata,
        data: text,
        textLemmatized,
        hash: memHash,
        createdAt: now,
        updatedAt: now,
      };
      if (mem.attributed_to) {
        memPayload.attributedTo = mem.attributed_to;
      }
      if (filters.user_id) memPayload.user_id = filters.user_id;
      if (filters.agent_id) memPayload.agent_id = filters.agent_id;
      if (filters.run_id) memPayload.run_id = filters.run_id;

      records.push({
        memoryId,
        text,
        embedding: embedMap[text],
        payload: memPayload,
      });
    }

    if (records.length === 0) {
      if (typeof this.db.saveMessages === "function") {
        try {
          await this.db.saveMessages(
            messages.map((m) => ({
              role: m.role,
              content: m.content as string,
            })),
            sessionScope,
          );
        } catch {}
      }
      return [];
    }

    // Phase 6: Batch persist
    const allVectors = records.map((r) => r.embedding);
    const allIds = records.map((r) => r.memoryId);
    const allPayloads = records.map((r) => r.payload);

    try {
      await this.vectorStore.insert(allVectors, allIds, allPayloads);
    } catch {
      // Fallback: insert one by one
      for (let i = 0; i < allIds.length; i++) {
        try {
          await this.vectorStore.insert(
            [allVectors[i]],
            [allIds[i]],
            [allPayloads[i]],
          );
        } catch (e) {
          console.error(`Failed to insert memory ${allIds[i]}: ${e}`);
        }
      }
    }

    // Batch history
    const historyRecords = records.map((r) => ({
      memoryId: r.memoryId,
      previousValue: null as string | null,
      newValue: r.text as string | null,
      action: "ADD",
      createdAt: r.payload.createdAt as string | undefined,
      updatedAt: undefined as string | undefined,
      isDeleted: 0,
    }));

    if (typeof this.db.batchAddHistory === "function") {
      try {
        await this.db.batchAddHistory(historyRecords);
      } catch {
        // Fallback: add one by one
        for (const hr of historyRecords) {
          try {
            await this.db.addHistory(
              hr.memoryId,
              null,
              hr.newValue,
              "ADD",
              hr.createdAt,
            );
          } catch (e) {
            console.error(`Failed to add history for ${hr.memoryId}: ${e}`);
          }
        }
      }
    } else {
      for (const hr of historyRecords) {
        try {
          await this.db.addHistory(
            hr.memoryId,
            null,
            hr.newValue,
            "ADD",
            hr.createdAt,
          );
        } catch (e) {
          console.error(`Failed to add history for ${hr.memoryId}: ${e}`);
        }
      }
    }

    // Phase 7: Batch entity linking
    try {
      const allTexts = records.map((r) => r.text);
      const allEntities = extractEntitiesBatch(allTexts);

      // 7a: Global dedup — collect unique entities across all memories
      const globalEntities: Record<
        string,
        { entityType: string; entityText: string; memoryIds: Set<string> }
      > = {};
      for (let idx = 0; idx < records.length; idx++) {
        const memoryId = records[idx].memoryId;
        const entities = idx < allEntities.length ? allEntities[idx] : [];
        for (const entity of entities) {
          const key = entity.text.trim().toLowerCase();
          if (key in globalEntities) {
            globalEntities[key].memoryIds.add(memoryId);
          } else {
            globalEntities[key] = {
              entityType: entity.type,
              entityText: entity.text,
              memoryIds: new Set([memoryId]),
            };
          }
        }
      }

      const orderedKeys = Object.keys(globalEntities);
      if (orderedKeys.length > 0) {
        const entityTexts = orderedKeys.map(
          (k) => globalEntities[k].entityText,
        );

        // 7b: Single batch embed for all unique entities
        let entityEmbeddings: (number[] | null)[];
        try {
          entityEmbeddings = await this.embedder.embedBatch(entityTexts);
        } catch {
          // Fallback: embed individually
          entityEmbeddings = [];
          for (const t of entityTexts) {
            try {
              entityEmbeddings.push(await this.embedder.embed(t));
            } catch {
              entityEmbeddings.push(null);
            }
          }
        }

        // Filter out entities with failed embeddings
        const valid: Array<{ index: number; key: string }> = [];
        for (let i = 0; i < orderedKeys.length; i++) {
          if (entityEmbeddings[i] !== null) {
            valid.push({ index: i, key: orderedKeys[i] });
          }
        }

        if (valid.length > 0) {
          const entityStore = await this.getEntityStore();
          const exactMatches = await this._existingEntitiesByText(
            entityStore,
            filters,
          );

          // 7c: Search for existing entities one by one (no batch search)
          const toInsertVectors: number[][] = [];
          const toInsertIds: string[] = [];
          const toInsertPayloads: Record<string, any>[] = [];

          for (const { index: j, key } of valid) {
            const { entityType, entityText, memoryIds } = globalEntities[key];
            const entityVec = entityEmbeddings[j]!;

            let matches: Array<{
              id: string;
              score?: number;
              payload: Record<string, any>;
            }> = [];
            const exactMatch = exactMatches.get(key);
            if (!exactMatch) {
              try {
                matches = await entityStore.search(entityVec, 1, filters);
              } catch {}
            }

            const semanticMatch =
              matches.length > 0 && (matches[0].score ?? 0) >= 0.95
                ? matches[0]
                : undefined;
            const match = exactMatch ?? semanticMatch;
            if (match) {
              // Update existing entity
              const payload = match.payload || {};
              const linked = new Set<string>(payload.linkedMemoryIds ?? []);
              for (const mid of memoryIds) linked.add(mid);
              payload.linkedMemoryIds = Array.from(linked).sort();
              try {
                await entityStore.update(match.id, entityVec, payload);
              } catch (e) {
                console.debug(`Entity update failed for '${entityText}': ${e}`);
              }
            } else {
              // New entity — collect for batch insert
              const entityPayload: Record<string, any> = {
                data: entityText,
                entityType,
                linkedMemoryIds: Array.from(memoryIds).sort(),
              };
              if (filters.user_id) entityPayload.user_id = filters.user_id;
              if (filters.agent_id) entityPayload.agent_id = filters.agent_id;
              if (filters.run_id) entityPayload.run_id = filters.run_id;

              toInsertVectors.push(entityVec);
              toInsertIds.push(uuidv4());
              toInsertPayloads.push(entityPayload);
            }
          }

          // 7e: Single batch insert for all new entities
          if (toInsertVectors.length > 0) {
            try {
              await entityStore.insert(
                toInsertVectors,
                toInsertIds,
                toInsertPayloads,
              );
            } catch (e) {
              console.warn(`Batch entity insert failed: ${e}`);
            }
          }
        }
      }
    } catch (e) {
      console.warn(`Batch entity linking failed: ${e}`);
    }

    // Phase 8: Save messages + return
    if (typeof this.db.saveMessages === "function") {
      try {
        await this.db.saveMessages(
          messages.map((m) => ({
            role: m.role,
            content: m.content as string,
          })),
          sessionScope,
        );
      } catch {}
    }

    return records.map((r) => ({
      id: r.memoryId,
      memory: r.text,
      metadata: { event: "ADD" },
    }));
  }

  async get(memoryId: string): Promise<MemoryItem | null> {
    await this._ensureInitialized();
    const memory = await this.vectorStore.get(memoryId);
    if (!memory) {
      await this._displayFirstRunNotice("get");
      return null;
    }

    const payload = memory.payload || {};
    const filters = this._sessionFiltersFromPayload(payload);

    const memoryItem: MemoryItem = {
      id: memory.id,
      memory: payload.data,
      hash: payload.hash,
      createdAt: this._payloadCreatedAt(payload),
      updatedAt: this._payloadUpdatedAt(payload),
      metadata: this._metadataFromPayload(payload),
    };

    const result = {
      ...memoryItem,
      ...filters,
      ...(payload.attributedTo && {
        attributedTo: payload.attributedTo,
      }),
    };
    await this._displayFirstRunNotice("get");
    return result;
  }

  async search(
    query: string,
    config: SearchMemoryOptions,
  ): Promise<SearchResult> {
    if (config?.referenceDate !== undefined) {
      await this._getNoticeTelemetryId();
      throw new Error(
        await getTemporalFeatureErrorMessage(this, {
          triggerFunction: "search",
          triggerParameter: "referenceDate",
        }),
      );
    }

    const temporalUsageNotice = detectTemporalUsageFromSearch(
      query,
      config?.filters,
    );

    // Reject top-level entity params - must use filters instead
    rejectTopLevelEntityParams(config as Record<string, any>, "search");

    // Validate search parameters (before applying defaults)
    validateSearchParams(config.threshold, config.topK);

    // Validate and trim entity IDs in filters. Only include keys whose
    // validated value is defined — otherwise downstream vector stores
    // receive `agent_id: undefined` / `run_id: undefined` and fail
    // (Qdrant rejects the malformed match, pgvector binds NULL, Redis
    // emits a literal "undefined" string in TAG filters).
    const normalizedFilters: Record<string, any> = config.filters
      ? Object.fromEntries(
          Object.entries({
            ...config.filters,
            user_id: validateAndTrimEntityId(config.filters.user_id, "user_id"),
            agent_id: validateAndTrimEntityId(
              config.filters.agent_id,
              "agent_id",
            ),
            run_id: validateAndTrimEntityId(config.filters.run_id, "run_id"),
          }).filter(([, v]) => v !== undefined),
        )
      : {};

    this._rejectWildcardScopeFilters(normalizedFilters, "search");

    await this._ensureInitialized();
    const { topK = 20, threshold = 0.1, explain = false } = config;

    await this._captureEvent("search", {
      query_length: query.length,
      topK,
      has_filters: !!config.filters,
    });

    let effectiveFilters: Record<string, any> = { ...normalizedFilters };

    // Apply enhanced metadata filtering if advanced operators are detected
    if (this._hasAdvancedOperators(effectiveFilters)) {
      effectiveFilters = this._processMetadataFilters(effectiveFilters);
    }

    // Validate filters contains at least one entity ID (snake_case)
    if (
      !effectiveFilters.user_id &&
      !effectiveFilters.agent_id &&
      !effectiveFilters.run_id
    ) {
      throw new Error(
        "filters must contain at least one of: user_id, agent_id, run_id. " +
          "Example: filters: { user_id: 'u1' }",
      );
    }

    const searchStartMs = Date.now();

    // Step 1: Preprocess query
    const queryLemmatized = lemmatizeForBm25(query);
    const queryEntities = extractEntities(query);

    // Step 2: Embed query
    const queryEmbedding = await this.embedder.embed(query);

    // Step 3: Semantic search (over-fetch for scoring pool)
    const internalLimit = Math.max(topK * 4, 60);
    const providerFilters =
      this._providerFiltersForRequestedScope(effectiveFilters);
    const semanticResults = this.filterByRequestedScope(
      await this.vectorStore.search(
        queryEmbedding,
        internalLimit,
        providerFilters,
      ),
      effectiveFilters,
    );

    // Step 4: Keyword search (if store supports it)
    let keywordResults: Array<{
      id: string;
      score?: number;
      payload: Record<string, any>;
    }> | null = null;
    if (typeof this.vectorStore.keywordSearch === "function") {
      try {
        const rawKeywordResults =
          (await this.vectorStore.keywordSearch(
            queryLemmatized,
            internalLimit,
            providerFilters,
          )) ?? null;
        keywordResults = rawKeywordResults
          ? this.filterByRequestedScope(rawKeywordResults, effectiveFilters)
          : null;
      } catch {
        keywordResults = null;
      }
    }

    // Step 5: Compute BM25 scores from keyword results
    const bm25Scores: Record<string, number> = {};
    if (keywordResults) {
      const [midpoint, steepness] = getBm25Params(query, queryLemmatized);
      for (const mem of keywordResults) {
        const memId = String(mem.id);
        const rawScore = mem.score ?? 0;
        if (rawScore > 0) {
          bm25Scores[memId] = normalizeBm25(rawScore, midpoint, steepness);
        }
      }
    }

    // Step 6: Compute entity boosts
    const entityBoosts: Record<string, number> = {};
    if (queryEntities.length > 0) {
      try {
        // Deduplicate entities (max 8)
        const seen = new Set<string>();
        const deduped: Array<{ type: string; text: string }> = [];
        for (const entity of queryEntities.slice(0, 8)) {
          const key = entity.text.trim().toLowerCase();
          if (key && !seen.has(key)) {
            seen.add(key);
            deduped.push(entity);
          }
        }

        if (deduped.length > 0) {
          const entityStore = await this.getEntityStore();
          const entitySearchFilters: Record<string, any> = {};
          for (const k of ["user_id", "agent_id", "run_id"] as const) {
            if (effectiveFilters[k])
              entitySearchFilters[k] = effectiveFilters[k];
          }
          const entityTexts = deduped.map((e) => e.text);
          const embeddings = await this.embedder.embedBatch(entityTexts);

          if (embeddings.length !== entityTexts.length) {
            console.warn(
              `embedBatch returned ${embeddings.length} vectors for ${entityTexts.length} texts — skipping entity boost`,
            );
          } else {
            const searchResults = await Promise.allSettled(
              deduped.map((_, i) =>
                entityStore.search(embeddings[i], 500, entitySearchFilters),
              ),
            );

            for (const result of searchResults) {
              if (result.status === "rejected") {
                console.warn(
                  "Entity boost search failed for one entity:",
                  result.reason,
                );
                continue;
              }

              for (const match of result.value) {
                const similarity = match.score ?? 0;
                if (similarity < 0.5) continue;

                const payload = match.payload || {};
                const linkedMemoryIds = payload.linkedMemoryIds ?? [];
                if (!Array.isArray(linkedMemoryIds)) continue;

                const numLinked = Math.max(linkedMemoryIds.length, 1);
                const memoryCountWeight =
                  1.0 / (1.0 + 0.001 * (numLinked - 1) ** 2);
                const boost =
                  similarity * ENTITY_BOOST_WEIGHT * memoryCountWeight;

                for (const memoryId of linkedMemoryIds) {
                  if (memoryId) {
                    const memKey = String(memoryId);
                    entityBoosts[memKey] = Math.max(
                      entityBoosts[memKey] ?? 0,
                      boost,
                    );
                  }
                }
              }
            }
          }
        }
      } catch (e) {
        console.warn("Entity boost computation failed:", e);
      }
    }

    // Step 7: Build candidate set from semantic results
    const candidates = semanticResults.map((mem) => ({
      id: String(mem.id),
      score: mem.score ?? 0,
      payload: mem.payload || {},
    }));

    // Step 8: Score and rank
    const scoredResults = scoreAndRank(
      candidates,
      bm25Scores,
      entityBoosts,
      threshold ?? 0.1,
      topK,
      explain,
    );

    // Step 9: Format results
    const results = scoredResults
      .filter((scored) => scored.payload?.data)
      .map((scored) => {
        const payload = scored.payload || {};
        return {
          id: scored.id,
          memory: payload.data,
          hash: payload.hash,
          createdAt: this._payloadCreatedAt(payload),
          updatedAt: this._payloadUpdatedAt(payload),
          score: scored.score,
          metadata: this._metadataFromPayload(payload),
          ...this._sessionFiltersFromPayload(payload),
          ...(payload.attributedTo && { attributedTo: payload.attributedTo }),
          ...(scored.scoreDetails && { score_details: scored.scoreDetails }),
        };
      });

    const result = {
      results,
    };
    const searchElapsedMs = Date.now() - searchStartMs;
    if (temporalUsageNotice) {
      await this._displayTemporalUsageNotice({
        triggerFunction: "search",
        triggerSource: temporalUsageNotice.triggerSource,
        triggerReason: temporalUsageNotice.triggerReason,
      });
    } else {
      const scaleThresholdNotice = detectScaleThresholdFromTopK(topK);
      if (scaleThresholdNotice) {
        await this._displayScaleThresholdNotice({
          triggerFunction: "search",
          ...scaleThresholdNotice,
        });
      } else {
        const performanceSlowQueryNotice = detectPerformanceSlowQuery(
          searchElapsedMs,
          topK,
          results.length,
        );
        if (performanceSlowQueryNotice) {
          await this._displayPerformanceSlowQueryNotice({
            triggerFunction: "search",
            triggerReason: "slow_query",
            ...performanceSlowQueryNotice,
          });
        } else {
          await this._displayFirstRunNotice("search");
        }
      }
    }
    return result;
  }

  async update(memoryId: string, data: string): Promise<{ message: string }> {
    await this._ensureInitialized();
    await this._captureEvent("update", { memory_id: memoryId });
    const embedding = await this.embedder.embed(data);
    await this.updateMemory(memoryId, data, { [data]: embedding });
    const result = { message: "Memory updated successfully!" };
    await this._displayFirstRunNotice("update");
    return result;
  }

  async delete(memoryId: string): Promise<{ message: string }> {
    await this._ensureInitialized();
    await this._captureEvent("delete", { memory_id: memoryId });
    await this.deleteMemory(memoryId);
    const result = { message: "Memory deleted successfully!" };
    const deleteCount = getDecayUsageDeleteCountAfterSuccess();
    if (isDecayUsageDeleteEligible(deleteCount)) {
      await this._displayDecayUsageNotice({
        triggerFunction: "delete",
        triggerSource: "delete_count",
        triggerReason: "repeated_deletes",
        deleteCount,
      });
    } else {
      await this._displayFirstRunNotice("delete");
    }
    return result;
  }

  async deleteAll(
    config: DeleteAllMemoryOptions,
  ): Promise<{ message: string }> {
    await this._ensureInitialized();
    await this._captureEvent("delete_all", {
      has_user_id: !!config.userId,
      has_agent_id: !!config.agentId,
      has_run_id: !!config.runId,
    });
    const userId = validateAndTrimEntityId(config.userId, "userId");
    const agentId = validateAndTrimEntityId(config.agentId, "agentId");
    const runId = validateAndTrimEntityId(config.runId, "runId");

    // Convert camelCase entity params to snake_case for filters (matches storage and search/getAll)
    const filters: SearchFilters = {};
    if (userId) filters.user_id = userId;
    if (agentId) filters.agent_id = agentId;
    if (runId) filters.run_id = runId;

    if (!Object.keys(filters).length) {
      throw new Error(
        "At least one filter is required to delete all memories. If you want to delete all memories, use the `reset()` method.",
      );
    }

    this._rejectWildcardScopeFilters(filters, "deleteAll");

    const deletedCount = await this._deleteAllByRequestedScope(filters);

    const result = { message: "Memories deleted successfully!" };
    if (deletedCount > 0) {
      await this._displayDecayUsageNotice({
        triggerFunction: "delete_all",
        triggerSource: "delete_all",
        triggerReason: "bulk_delete",
        deletedCount,
      });
    } else {
      await this._displayFirstRunNotice("delete_all");
    }
    return result;
  }

  async history(memoryId: string): Promise<any[]> {
    await this._ensureInitialized();
    const result = await this.db.getHistory(memoryId);
    await this._displayFirstRunNotice("history");
    return result;
  }

  async reset(): Promise<void> {
    await this._ensureInitialized();
    await this._captureEvent("reset");
    await this.db.reset();

    // Check provider before attempting deleteCol
    if (this.config.vectorStore.provider.toLowerCase() !== "langchain") {
      try {
        await this.vectorStore.deleteCol();
      } catch (e) {
        console.error(
          `Failed to delete collection for provider '${this.config.vectorStore.provider}':`,
          e,
        );
        // Decide if you want to re-throw or just log
      }
    } else {
      console.warn(
        "Memory.reset(): Skipping vector store collection deletion as 'langchain' provider is used. Underlying Langchain vector store data is not cleared by this operation.",
      );
    }

    if (this._entityStore) {
      try {
        await this._entityStore.deleteCol();
      } catch {}
      this._entityStore = undefined;
    }

    // Re-initialize factories/clients based on the original config.
    // Dimension is already set in this.config from the initial probe,
    // so _autoInitialize will skip the probe and just re-create the store.
    this.embedder = EmbedderFactory.create(
      this.config.embedder.provider,
      this.config.embedder.config,
    );
    this.llm = LLMFactory.create(
      this.config.llm.provider,
      this.config.llm.config,
    );

    // Re-create vector store via _autoInitialize (which handles dimension + creation)
    this._initError = undefined;
    this._initPromise = this._autoInitialize().catch((error) => {
      this._initError =
        error instanceof Error ? error : new Error(String(error));
      console.error(this._initError);
    });
    await this._initPromise;
    await this._displayFirstRunNotice("reset");
  }

  async getAll(config: GetAllMemoryOptions): Promise<SearchResult> {
    // Reject top-level entity params - must use filters instead
    rejectTopLevelEntityParams(config as Record<string, any>, "getAll");

    // Validate topK if provided (before applying defaults)
    validateSearchParams(undefined, config.topK);

    await this._ensureInitialized();

    const { topK = 20 } = config;

    // Validate and trim entity IDs in filters. Drop keys that resolve to
    // undefined so downstream vector stores don't receive
    // `agent_id: undefined` / `run_id: undefined` and fail.
    const filters: Record<string, any> = Object.fromEntries(
      Object.entries({
        ...(config.filters || {}),
        user_id: validateAndTrimEntityId(config.filters?.user_id, "user_id"),
        agent_id: validateAndTrimEntityId(config.filters?.agent_id, "agent_id"),
        run_id: validateAndTrimEntityId(config.filters?.run_id, "run_id"),
      }).filter(([, v]) => v !== undefined),
    );

    this._rejectWildcardScopeFilters(filters, "getAll");

    await this._captureEvent("get_all", {
      topK,
      has_user_id: !!filters.user_id,
      has_agent_id: !!filters.agent_id,
      has_run_id: !!filters.run_id,
    });

    // Validate filters contains at least one entity ID (snake_case)
    if (!filters.user_id && !filters.agent_id && !filters.run_id) {
      throw new Error(
        "filters must contain at least one of: user_id, agent_id, run_id. " +
          "Example: filters: { user_id: 'u1' }",
      );
    }

    const fetchLimit =
      topK === 0 ? 0 : Math.max(topK * 4, MIN_SCOPE_POST_FILTER_FETCH);
    const memories = await this._listByRequestedScope(filters, {
      topK,
      initialLimit: fetchLimit,
    });

    const results = memories.map((mem) => ({
      id: mem.id,
      memory: mem.payload.data,
      hash: mem.payload.hash,
      createdAt: this._payloadCreatedAt(mem.payload),
      updatedAt: this._payloadUpdatedAt(mem.payload),
      metadata: this._metadataFromPayload(mem.payload),
      ...this._sessionFiltersFromPayload(mem.payload),
      ...(mem.payload.attributedTo && {
        attributedTo: mem.payload.attributedTo,
      }),
    }));

    const result = { results };
    const scaleThresholdNotice = detectScaleThresholdFromTopK(topK);
    if (scaleThresholdNotice) {
      await this._displayScaleThresholdNotice({
        triggerFunction: "get_all",
        ...scaleThresholdNotice,
      });
    } else {
      await this._displayFirstRunNotice("get_all");
    }
    return result;
  }

  private async createMemory(
    data: string,
    existingEmbeddings: Record<string, number[]>,
    metadata: Record<string, any>,
  ): Promise<string> {
    const memoryId = uuidv4();
    const embedding =
      existingEmbeddings[data] || (await this.embedder.embed(data));

    const memoryMetadata = {
      ...metadata,
      data,
      hash: createHash("md5").update(data).digest("hex"),
      textLemmatized: lemmatizeForBm25(data),
      createdAt: new Date().toISOString(),
    };

    await this.vectorStore.insert([embedding], [memoryId], [memoryMetadata]);
    await this.db.addHistory(
      memoryId,
      null,
      data,
      "ADD",
      memoryMetadata.createdAt,
    );

    return memoryId;
  }

  private async updateMemory(
    memoryId: string,
    data: string,
    existingEmbeddings: Record<string, number[]>,
    metadata: Record<string, any> = {},
  ): Promise<string> {
    const existingMemory = await this.vectorStore.get(memoryId);
    if (!existingMemory) {
      throw new Error(`Memory with ID ${memoryId} not found`);
    }

    const prevValue = existingMemory.payload.data;
    const embedding =
      existingEmbeddings[data] || (await this.embedder.embed(data));

    const newMetadata = {
      ...existingMemory.payload,
      ...metadata,
      data,
      hash: createHash("md5").update(data).digest("hex"),
      textLemmatized: lemmatizeForBm25(data),
      createdAt: existingMemory.payload.createdAt,
      updatedAt: new Date().toISOString(),
    };

    await this.vectorStore.update(memoryId, embedding, newMetadata);
    await this.db.addHistory(
      memoryId,
      prevValue,
      data,
      "UPDATE",
      newMetadata.createdAt,
      newMetadata.updatedAt,
    );

    // Entity-store cleanup: strip this memory's id from old-text entities,
    // then re-extract entities from the new text and link them back.
    try {
      const sessionFilters = this._sessionFiltersFromPayload(newMetadata);
      await this._removeMemoryFromEntityStore(memoryId, sessionFilters);
      await this._linkEntitiesForMemory(memoryId, data, sessionFilters);
    } catch (e) {
      console.warn(`Entity store cleanup/link failed during update: ${e}`);
    }

    return memoryId;
  }

  private async deleteMemory(memoryId: string): Promise<string> {
    const existingMemory = await this.vectorStore.get(memoryId);
    if (!existingMemory) {
      throw new Error(`Memory with ID ${memoryId} not found`);
    }

    const prevValue = existingMemory.payload.data;
    const sessionFilters = this._sessionFiltersFromPayload(
      existingMemory.payload || {},
    );
    await this.vectorStore.delete(memoryId);
    await this.db.addHistory(
      memoryId,
      prevValue,
      null,
      "DELETE",
      undefined,
      undefined,
      1,
    );

    // Entity-store cleanup: strip this memory's id from any entity records
    // that linked to it. Non-fatal — log and continue on error.
    try {
      await this._removeMemoryFromEntityStore(memoryId, sessionFilters);
    } catch (e) {
      console.warn(`Entity store cleanup failed during delete: ${e}`);
    }

    return memoryId;
  }

  /**
   * Check if filters contain advanced operators that need special processing.
   */
  private _hasAdvancedOperators(filters: Record<string, any>): boolean {
    if (!filters || typeof filters !== "object") {
      return false;
    }

    for (const [key, value] of Object.entries(filters)) {
      // Check for platform-style logical operators
      if (
        key === "AND" ||
        key === "OR" ||
        key === "NOT" ||
        key === "$and" ||
        key === "$or" ||
        key === "$not"
      ) {
        return true;
      }
      // Check for comparison operators
      if (
        typeof value === "object" &&
        value !== null &&
        !Array.isArray(value)
      ) {
        for (const op of Object.keys(value)) {
          if (
            [
              "eq",
              "ne",
              "gt",
              "gte",
              "lt",
              "lte",
              "in",
              "nin",
              "contains",
              "icontains",
            ].includes(op)
          ) {
            return true;
          }
        }
      }
      // Check for wildcard values
      if (value === "*") {
        return true;
      }
    }
    return false;
  }

  /**
   * Process enhanced metadata filters and convert them to vector store compatible format.
   * Converts AND/OR/NOT to $or/$not format that vector stores can interpret.
   */
  private _processMetadataFilters(
    metadataFilters: Record<string, any>,
  ): Record<string, any> {
    const processCondition = (
      key: string,
      condition: any,
    ): Record<string, any> => {
      if (typeof condition !== "object" || condition === null) {
        // Simple equality: {"key": "value"} or wildcard
        if (condition === "*") {
          return { [key]: "*" };
        }
        return { [key]: condition };
      }

      if (Array.isArray(condition)) {
        // Array shorthand for "in" operator
        return { [key]: { in: condition } };
      }

      const result: Record<string, any> = {};
      const operatorMap: Record<string, string> = {
        eq: "eq",
        ne: "ne",
        gt: "gt",
        gte: "gte",
        lt: "lt",
        lte: "lte",
        in: "in",
        nin: "nin",
        contains: "contains",
        icontains: "icontains",
      };

      for (const [operator, value] of Object.entries(condition)) {
        if (operator in operatorMap) {
          if (!result[key]) {
            result[key] = {};
          }
          result[key][operatorMap[operator]] = value;
        } else {
          throw new Error(`Unsupported metadata filter operator: ${operator}`);
        }
      }
      return result;
    };

    const processFilterObject = (
      filters: Record<string, any>,
    ): Record<string, any> => {
      const processedFilters: Record<string, any> = {};

      const appendAndFilters = (clauses: Record<string, any>[]) => {
        const nonEmptyClauses = clauses.filter(
          (clause) => Object.keys(clause).length > 0,
        );
        if (nonEmptyClauses.length === 0) {
          return;
        }
        processedFilters["$and"] = [
          ...((processedFilters["$and"] as Record<string, any>[] | undefined) ??
            []),
          ...nonEmptyClauses,
        ];
      };

      const setProcessedClause = (key: string, value: any) => {
        if (
          key === "$and" &&
          Array.isArray(processedFilters["$and"]) &&
          Array.isArray(value)
        ) {
          appendAndFilters(value as Record<string, any>[]);
          return;
        }

        if (!(key in processedFilters)) {
          processedFilters[key] = value;
          return;
        }

        const existingValue = processedFilters[key];
        delete processedFilters[key];
        appendAndFilters([{ [key]: existingValue }, { [key]: value }]);
      };

      for (const [key, value] of Object.entries(filters)) {
        if (key === "AND" || key === "$and") {
          // Logical AND: preserve each conjunct so repeated keys/logical
          // groups cannot overwrite each other while filters are normalized.
          if (!Array.isArray(value)) {
            throw new Error("AND operator requires a list of conditions");
          }
          appendAndFilters(
            value.map((condition) =>
              processFilterObject(condition as Record<string, any>),
            ),
          );
        } else if (key === "OR" || key === "$or") {
          // Logical OR: Pass through to vector store for implementation-specific handling
          if (!Array.isArray(value) || value.length === 0) {
            throw new Error(
              "OR operator requires a non-empty list of conditions",
            );
          }
          setProcessedClause(
            "$or",
            value.map((condition) =>
              processFilterObject(condition as Record<string, any>),
            ),
          );
        } else if (key === "NOT" || key === "$not") {
          // Logical NOT: Pass through to vector store for implementation-specific handling
          if (!Array.isArray(value) || value.length === 0) {
            throw new Error(
              "NOT operator requires a non-empty list of conditions",
            );
          }
          setProcessedClause(
            "$not",
            value.map((condition) =>
              processFilterObject(condition as Record<string, any>),
            ),
          );
        } else {
          for (const [processedKey, processedValue] of Object.entries(
            processCondition(key, value),
          )) {
            setProcessedClause(processedKey, processedValue);
          }
        }
      }

      return processedFilters;
    };

    return processFilterObject(metadataFilters);
  }
}
