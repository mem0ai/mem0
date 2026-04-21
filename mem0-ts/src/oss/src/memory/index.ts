import { v4 as uuidv4 } from "uuid";
import { createHash } from "crypto";
import {
  MemoryConfig,
  MemoryConfigSchema,
  MemoryItem,
  Message,
  SearchFilters,
  SearchResult,
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
} from "./memory.types";
import { parse_vision_messages } from "../utils/memory";
import { HistoryManager } from "../storage/base";
import { captureClientEvent } from "../utils/telemetry";
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

// Entity params that must be passed via filters - check both snake_case and camelCase
const ENTITY_PARAMS = [
  "user_id",
  "agent_id",
  "run_id",
  "userId",
  "agentId",
  "runId",
];

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
    if (payload.user_id) filters.user_id = payload.user_id;
    if (payload.agent_id) filters.agent_id = payload.agent_id;
    if (payload.run_id) filters.run_id = payload.run_id;
    return filters;
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
          try {
            matches = await entityStore.search(entityVec, 1, filters);
          } catch {}

          if (matches.length > 0 && (matches[0].score ?? 0) >= 0.95) {
            const match = matches[0];
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
        this.telemetryId = await this.vectorStore.getUserId();
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

  static fromConfig(configDict: Record<string, any>): Memory {
    try {
      const config = MemoryConfigSchema.parse(configDict);
      return new Memory(config);
    } catch (e) {
      console.error("Configuration validation error:", e);
      throw e;
    }
  }

  async add(
    messages: string | Message[],
    config: AddMemoryOptions,
  ): Promise<SearchResult> {
    // Validate messages input
    if (messages === undefined || messages === null) {
      throw new Error(
        "messages is required and cannot be undefined or null. Provide a string or array of messages.",
      );
    }

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
        if (message.content === "system") {
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
    const parsedMessages = messages.map((m) => m.content).join("\n");

    // Phase 1: Existing memory retrieval
    const queryEmbedding = await this.embedder.embed(parsedMessages);
    const existingResults = await this.vectorStore.search(
      queryEmbedding,
      10,
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
            try {
              matches = await entityStore.search(entityVec, 1, filters);
            } catch {}

            if (matches.length > 0 && (matches[0].score ?? 0) >= 0.95) {
              // Update existing entity
              const match = matches[0];
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
    if (!memory) return null;

    const filters = {
      ...(memory.payload.user_id && { user_id: memory.payload.user_id }),
      ...(memory.payload.agent_id && { agent_id: memory.payload.agent_id }),
      ...(memory.payload.run_id && { run_id: memory.payload.run_id }),
    };

    const memoryItem: MemoryItem = {
      id: memory.id,
      memory: memory.payload.data,
      hash: memory.payload.hash,
      createdAt: memory.payload.createdAt,
      updatedAt: memory.payload.updatedAt,
      metadata: {},
    };

    // Add additional metadata
    const excludedKeys = new Set([
      "userId",
      "agentId",
      "runId",
      "hash",
      "data",
      "createdAt",
      "updatedAt",
      "textLemmatized",
      "attributedTo",
    ]);
    for (const [key, value] of Object.entries(memory.payload)) {
      if (!excludedKeys.has(key)) {
        memoryItem.metadata![key] = value;
      }
    }

    return { ...memoryItem, ...filters };
  }

  async search(
    query: string,
    config: SearchMemoryOptions,
  ): Promise<SearchResult> {
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

    await this._ensureInitialized();
    const { topK = 20, threshold = 0.1 } = config;

    await this._captureEvent("search", {
      query_length: query.length,
      topK,
      has_filters: !!config.filters,
    });

    let effectiveFilters: Record<string, any> = { ...normalizedFilters };

    // Apply enhanced metadata filtering if advanced operators are detected
    if (this._hasAdvancedOperators(effectiveFilters)) {
      const processedFilters = this._processMetadataFilters(effectiveFilters);
      // Remove logical/operator keys that have been reprocessed
      for (const logicalKey of ["AND", "OR", "NOT"]) {
        delete effectiveFilters[logicalKey];
      }
      for (const fk of Object.keys(effectiveFilters)) {
        if (
          !["AND", "OR", "NOT", "user_id", "agent_id", "run_id"].includes(fk) &&
          typeof effectiveFilters[fk] === "object" &&
          effectiveFilters[fk] !== null
        ) {
          delete effectiveFilters[fk];
        }
      }
      effectiveFilters = { ...effectiveFilters, ...processedFilters };
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

    // Step 1: Preprocess query
    const queryLemmatized = lemmatizeForBm25(query);
    const queryEntities = extractEntities(query);

    // Step 2: Embed query
    const queryEmbedding = await this.embedder.embed(query);

    // Step 3: Semantic search (over-fetch for scoring pool)
    const internalLimit = Math.max(topK * 4, 60);
    const semanticResults = await this.vectorStore.search(
      queryEmbedding,
      internalLimit,
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
        keywordResults =
          (await this.vectorStore.keywordSearch(
            queryLemmatized,
            internalLimit,
            effectiveFilters,
          )) ?? null;
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

          for (const entity of deduped) {
            try {
              const entityEmbedding = await this.embedder.embed(entity.text);
              const matches = await entityStore.search(
                entityEmbedding,
                500,
                effectiveFilters,
              );

              for (const match of matches) {
                const similarity = match.score ?? 0;
                if (similarity < 0.5) continue;

                const payload = match.payload || {};
                const linkedMemoryIds = payload.linkedMemoryIds ?? [];
                if (!Array.isArray(linkedMemoryIds)) continue;

                // Spread-attenuated boost
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
            } catch (e) {
              // Individual entity boost failed — continue
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
    );

    // Step 9: Format results
    const excludedKeys = new Set([
      "user_id",
      "agent_id",
      "run_id",
      "hash",
      "data",
      "createdAt",
      "updatedAt",
      "textLemmatized",
      "attributedTo",
    ]);

    const results = scoredResults
      .filter((scored) => scored.payload?.data)
      .map((scored) => {
        const payload = scored.payload || {};
        return {
          id: scored.id,
          memory: payload.data,
          hash: payload.hash,
          createdAt: payload.createdAt,
          updatedAt: payload.updatedAt,
          score: scored.score,
          metadata: Object.entries(payload)
            .filter(([key]) => !excludedKeys.has(key))
            .reduce((acc, [key, value]) => ({ ...acc, [key]: value }), {}),
          ...(payload.user_id && { user_id: payload.user_id }),
          ...(payload.agent_id && { agent_id: payload.agent_id }),
          ...(payload.run_id && { run_id: payload.run_id }),
        };
      });

    return {
      results,
    };
  }

  async update(memoryId: string, data: string): Promise<{ message: string }> {
    await this._ensureInitialized();
    await this._captureEvent("update", { memory_id: memoryId });
    const embedding = await this.embedder.embed(data);
    await this.updateMemory(memoryId, data, { [data]: embedding });
    return { message: "Memory updated successfully!" };
  }

  async delete(memoryId: string): Promise<{ message: string }> {
    await this._ensureInitialized();
    await this._captureEvent("delete", { memory_id: memoryId });
    await this.deleteMemory(memoryId);
    return { message: "Memory deleted successfully!" };
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
    const { userId, agentId, runId } = config;

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

    const [memories] = await this.vectorStore.list(filters);
    for (const memory of memories) {
      await this.deleteMemory(memory.id);
    }

    return { message: "Memories deleted successfully!" };
  }

  async history(memoryId: string): Promise<any[]> {
    await this._ensureInitialized();
    return this.db.getHistory(memoryId);
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

    const [memories] = await this.vectorStore.list(filters, topK);

    const excludedKeys = new Set([
      "user_id",
      "agent_id",
      "run_id",
      "hash",
      "data",
      "createdAt",
      "updatedAt",
      "textLemmatized",
      "attributedTo",
    ]);
    const results = memories.map((mem) => ({
      id: mem.id,
      memory: mem.payload.data,
      hash: mem.payload.hash,
      createdAt: mem.payload.createdAt,
      updatedAt: mem.payload.updatedAt,
      metadata: Object.entries(mem.payload)
        .filter(([key]) => !excludedKeys.has(key))
        .reduce((acc, [key, value]) => ({ ...acc, [key]: value }), {}),
      ...(mem.payload.user_id && { user_id: mem.payload.user_id }),
      ...(mem.payload.agent_id && { agent_id: mem.payload.agent_id }),
      ...(mem.payload.run_id && { run_id: mem.payload.run_id }),
    }));

    return { results };
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
      ...metadata,
      data,
      hash: createHash("md5").update(data).digest("hex"),
      createdAt: existingMemory.payload.createdAt,
      updatedAt: new Date().toISOString(),
      ...(existingMemory.payload.user_id && {
        user_id: existingMemory.payload.user_id,
      }),
      ...(existingMemory.payload.agent_id && {
        agent_id: existingMemory.payload.agent_id,
      }),
      ...(existingMemory.payload.run_id && {
        run_id: existingMemory.payload.run_id,
      }),
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
      if (key === "AND" || key === "OR" || key === "NOT") {
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
    const processedFilters: Record<string, any> = {};

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

    for (const [key, value] of Object.entries(metadataFilters)) {
      if (key === "AND") {
        // Logical AND: combine multiple conditions
        if (!Array.isArray(value)) {
          throw new Error("AND operator requires a list of conditions");
        }
        for (const condition of value) {
          for (const [subKey, subValue] of Object.entries(condition)) {
            Object.assign(processedFilters, processCondition(subKey, subValue));
          }
        }
      } else if (key === "OR") {
        // Logical OR: Pass through to vector store for implementation-specific handling
        if (!Array.isArray(value) || value.length === 0) {
          throw new Error(
            "OR operator requires a non-empty list of conditions",
          );
        }
        processedFilters["$or"] = [];
        for (const condition of value) {
          const orCondition: Record<string, any> = {};
          for (const [subKey, subValue] of Object.entries(
            condition as Record<string, any>,
          )) {
            Object.assign(orCondition, processCondition(subKey, subValue));
          }
          processedFilters["$or"].push(orCondition);
        }
      } else if (key === "NOT") {
        // Logical NOT: Pass through to vector store for implementation-specific handling
        if (!Array.isArray(value) || value.length === 0) {
          throw new Error(
            "NOT operator requires a non-empty list of conditions",
          );
        }
        processedFilters["$not"] = [];
        for (const condition of value) {
          const notCondition: Record<string, any> = {};
          for (const [subKey, subValue] of Object.entries(
            condition as Record<string, any>,
          )) {
            Object.assign(notCondition, processCondition(subKey, subValue));
          }
          processedFilters["$not"].push(notCondition);
        }
      } else {
        Object.assign(processedFilters, processCondition(key, value));
      }
    }

    return processedFilters;
  }
}
