import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

/**
 * The `@aws-sdk/client-neptune-graph` dependency is loaded on first use via dynamic
 * `import()` so the package stays optional (mirrors `aws_bedrock.ts`).
 */
interface NeptuneAnalyticsConfig extends VectorStoreConfig {
  graphIdentifier?: string;
  endpoint?: string;
  collectionName: string;
  dimension?: number;
  client?: NeptuneGraphClientLike;
}

interface NeptuneGraphClientLike {
  send(command: any): Promise<NeptuneExecuteQueryOutput>;
}

interface NeptuneSDK {
  NeptuneGraphClient: new (
    config: Record<string, any>,
  ) => NeptuneGraphClientLike;
  ExecuteQueryCommand: new (input: Record<string, any>) => any;
}

interface NeptuneExecuteQueryOutput {
  payload?: {
    transformToString(encoding?: string): Promise<string>;
  };
}

type NeptuneQueryRecord = Record<string, any>;
type NeptuneVertexFilter = Record<string, any>;

interface WhereClauseResult {
  clause: string;
  parameters: Record<string, any>;
  nextIndex: number;
}

export class NeptuneAnalyticsVectorStore implements VectorStore {
  private clientConfig: Record<string, any>;
  private clientOverride?: NeptuneGraphClientLike;
  private sdkPromise?: Promise<NeptuneSDK>;
  private clientPromise?: Promise<NeptuneGraphClientLike>;
  private readonly graphIdentifier: string;
  private readonly collectionName: string;
  private readonly collectionLabel: string;
  private readonly collectionLabelExpr: string;
  private readonly userLabel: string;
  private readonly userLabelExpr: string;
  private readonly userNodeId: string;
  private readonly dimension: number;
  private _initPromise?: Promise<void>;
  private cachedUserId?: string;

  constructor(config: NeptuneAnalyticsConfig) {
    this.graphIdentifier = this.resolveGraphIdentifier(config);
    this.collectionName = config.collectionName || "memories";
    this.collectionLabel = `MEM0_VECTOR_${this.collectionName}`;
    this.collectionLabelExpr = this.escapeLabel(this.collectionLabel);
    this.userLabel = "MEM0_VECTOR_memory_migrations";
    this.userLabelExpr = this.escapeLabel(this.userLabel);
    this.userNodeId = "mem0-user";
    this.dimension = config.dimension || 1536;
    this.clientConfig = this.buildClientConfig(config);
    this.clientOverride = config.client;

    void this.initialize().catch(console.error);
  }

  initialize(): Promise<void> {
    if (!this._initPromise) {
      this._initPromise = this._doInitialize();
    }
    return this._initPromise;
  }

  private async _doInitialize(): Promise<void> {
    return;
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    this.assertBatchDimensions(vectors, "Insert");
    const existingIds = await this.findExistingIds(ids);

    const rows = vectors.map((vector, index) => ({
      node_id: ids[index],
      properties: this.buildStoredPayload(payloads[index] || {}),
      embedding: vector,
    }));

    const propertiesQuery = `
      UNWIND $rows AS row
      MERGE (n:${this.collectionLabelExpr} {\`~id\`: row.node_id})
      ON CREATE SET n = row.properties
      ON MATCH SET n += row.properties
    `;

    const vectorQuery = `
      UNWIND $rows AS row
      MATCH (n:${this.collectionLabelExpr} {\`~id\`: row.node_id})
      WITH n, row.embedding AS embedding
      CALL neptune.algo.vectors.upsert(n, embedding)
      YIELD success
      RETURN success
    `;

    try {
      await this.executeQuery(propertiesQuery, { rows });
      const results = await this.executeQuery(vectorQuery, { rows });
      this.assertSuccessfulResults(results, "Insert");
    } catch (error) {
      await this.cleanupFailedInsert(ids.filter((id) => !existingIds.has(id)));
      throw error;
    }
  }

  async keywordSearch(): Promise<null> {
    return null;
  }

  async search(
    query: number[],
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    this.assertVectorDimension(query, "Query");

    const vertexFilter = this.buildVertexFilter(filters);
    const results = await this.executeQuery(
      `
        CALL neptune.algo.vectors.topK.byEmbedding(
          ${this.serializeAlgorithmInput({
            topK,
            embedding: query,
            vertexFilter,
          })}
        )
        YIELD node, score
        RETURN node, score
      `,
    );

    return results.map((record) => this.normalizeSearchResult(record));
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    const results = await this.executeQuery(
      `
        MATCH (n:${this.collectionLabelExpr} {\`~id\`: $vectorId})
        RETURN n
        LIMIT 1
      `,
      {
        vectorId,
      },
    );

    if (results.length === 0) {
      return null;
    }

    return this.normalizeNodeResult(results[0]);
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    if (vector.length > 0) {
      this.assertVectorDimension(vector, "Vector");
    }

    const hasPayload = !!payload && Object.keys(payload).length > 0;
    const hasVector = vector.length > 0;

    // ponytail: a combined update writes the payload before the embedding, and Neptune's vector
    // index isn't transactional -- if the upsert below fails, the new payload would otherwise be
    // left committed against the stale embedding (searches would match the old vector but return
    // the new metadata). Capture the prior node so a failed upsert can be restored; this is
    // best-effort compensation, not a rollback. Only needed when both writes happen -- a
    // payload-only or vector-only update can't desync.
    // The restore assumes a single writer per vectorId -- concurrent updates to the same node can
    // interleave and clobber each other's compensation. AWS advises against concurrent same-vertex
    // writes to the Neptune Analytics vector index for exactly this reason.
    const priorResult =
      hasPayload && hasVector ? await this.get(vectorId) : null;

    if (hasPayload) {
      const properties = this.buildStoredPayload(payload);
      await this.executeQuery(
        `
          MATCH (n:${this.collectionLabelExpr} {\`~id\`: $vectorId})
          SET n = $properties
          RETURN n
        `,
        {
          vectorId,
          properties,
        },
      );
    }

    if (hasVector) {
      try {
        const updateResults = await this.executeQuery(
          `
            MATCH (n:${this.collectionLabelExpr} {\`~id\`: $vectorId})
            WITH n, $embedding AS embedding
            CALL neptune.algo.vectors.upsert(n, embedding)
            YIELD success
            RETURN success
          `,
          {
            vectorId,
            embedding: vector,
          },
        );
        this.assertSuccessfulResults(updateResults, "Update");
      } catch (error) {
        if (priorResult) {
          try {
            await this.executeQuery(
              `
                MATCH (n:${this.collectionLabelExpr} {\`~id\`: $vectorId})
                SET n = $properties
                RETURN n
              `,
              {
                vectorId,
                properties: priorResult.payload,
              },
            );
          } catch (restoreError) {
            // Do not mask the original failure with a compensation failure.
            console.error(
              "Neptune Analytics: failed to restore prior payload after a failed update upsert",
              restoreError,
            );
          }
        }
        throw error;
      }
    }
  }

  async delete(vectorId: string): Promise<void> {
    await this.executeQuery(
      `
        MATCH (n:${this.collectionLabelExpr} {\`~id\`: $vectorId})
        DETACH DELETE n
      `,
      {
        vectorId,
      },
    );
  }

  async deleteCol(): Promise<void> {
    await this.executeQuery(
      `
        MATCH (n:${this.collectionLabelExpr})
        DETACH DELETE n
      `,
    );
  }

  async list(
    filters?: SearchFilters,
    topK: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    const { clause, parameters } = this.buildWhereClause(filters);
    const whereClause = clause ? `WHERE ${clause}` : "";
    const [results, countResults] = await Promise.all([
      this.executeQuery(
        `
          MATCH (n:${this.collectionLabelExpr})
          ${whereClause}
          RETURN n
          LIMIT $limit
        `,
        {
          ...parameters,
          limit: topK,
        },
      ),
      this.executeQuery(
        `
          MATCH (n:${this.collectionLabelExpr})
          ${whereClause}
          RETURN count(n) AS count
        `,
        parameters,
      ),
    ]);

    const items = results.map((record) => this.normalizeNodeResult(record));
    const count = Number(countResults[0]?.count);
    return [items, Number.isFinite(count) ? count : items.length];
  }

  async getUserId(): Promise<string> {
    if (this.cachedUserId) {
      return this.cachedUserId;
    }

    const results = await this.executeQuery(
      `
        MATCH (n:${this.userLabelExpr} {\`~id\`: $userNodeId})
        RETURN n
        LIMIT 1
      `,
      {
        userNodeId: this.userNodeId,
      },
    );

    const existing = results[0];
    const userId = existing ? this.extractUserId(existing) : undefined;
    if (userId) {
      this.cachedUserId = userId;
      return userId;
    }

    const randomUserId =
      Math.random().toString(36).substring(2, 15) +
      Math.random().toString(36).substring(2, 15);
    await this.setUserId(randomUserId);
    return randomUserId;
  }

  async setUserId(userId: string): Promise<void> {
    await this.executeQuery(
      `
        MERGE (n:${this.userLabelExpr} {\`~id\`: $userNodeId})
        SET n.user_id = $userId
        RETURN n
      `,
      {
        userNodeId: this.userNodeId,
        userId,
      },
    );
    this.cachedUserId = userId;
  }

  private async findExistingIds(nodeIds: string[]): Promise<Set<string>> {
    if (nodeIds.length === 0) {
      return new Set();
    }

    const results = await this.executeQuery(
      `
        UNWIND $nodeIds AS nodeId
        MATCH (n:${this.collectionLabelExpr} {\`~id\`: nodeId})
        RETURN nodeId
      `,
      {
        nodeIds,
      },
    );

    return new Set(
      results
        .map((record) => record.nodeId)
        .filter((nodeId): nodeId is string => typeof nodeId === "string"),
    );
  }

  private async cleanupFailedInsert(nodeIds: string[]): Promise<void> {
    if (nodeIds.length === 0) {
      return;
    }

    try {
      await this.executeQuery(
        `
          UNWIND $nodeIds AS nodeId
          MATCH (n:${this.collectionLabelExpr} {\`~id\`: nodeId})
          DETACH DELETE n
        `,
        {
          nodeIds,
        },
      );
    } catch (error) {
      console.error(
        "Neptune Analytics: failed to clean up node(s) after a failed insert",
        error,
      );
    }
  }

  private resolveGraphIdentifier(config: NeptuneAnalyticsConfig): string {
    if (config.graphIdentifier) {
      return config.graphIdentifier;
    }

    const rawIdentifier = config.endpoint;

    if (!rawIdentifier) {
      throw new Error(
        "Neptune Analytics vector store requires graphIdentifier or endpoint.",
      );
    }

    if (/^https?:\/\//i.test(rawIdentifier)) {
      throw new Error(
        "Neptune Analytics HTTPS endpoints require graphIdentifier; pass graphIdentifier separately or use neptune-graph://<graph-id>.",
      );
    }

    if (rawIdentifier.startsWith("neptune-graph://")) {
      return rawIdentifier.slice("neptune-graph://".length);
    }

    return rawIdentifier;
  }

  private buildClientConfig(config: NeptuneAnalyticsConfig): {
    [key: string]: any;
    endpoint?: string;
  } {
    const {
      client: _client,
      collectionName: _collectionName,
      dimension: _dimension,
      graphIdentifier: _graphIdentifier,
      endpoint,
      ...clientConfig
    } = config;

    if (endpoint && /^https?:\/\//i.test(endpoint)) {
      return {
        ...clientConfig,
        endpoint,
      };
    }

    return clientConfig;
  }

  private escapeLabel(label: string): string {
    return `\`${label.replace(/`/g, "``")}\``;
  }

  private buildStoredPayload(
    payload: Record<string, any>,
  ): Record<string, any> {
    return {
      ...payload,
      updatedAt: new Date().toISOString(),
    };
  }

  private buildVertexFilter(filters?: SearchFilters): NeptuneVertexFilter {
    const conditions: NeptuneVertexFilter[] = [
      {
        equals: {
          property: "~label",
          value: this.collectionLabel,
        },
      },
    ];

    const metadataFilter = this.buildMetadataVertexFilter(filters);
    if (metadataFilter) {
      conditions.push(metadataFilter);
    }

    return this.combineVertexFilters("andAll", conditions)!;
  }

  private buildMetadataVertexFilter(
    filters?: SearchFilters,
  ): NeptuneVertexFilter | undefined {
    const operations: NeptuneVertexFilter[] = [];

    for (const [key, value] of Object.entries(filters || {})) {
      if (value === undefined) {
        continue;
      }

      if (key === "$and" || key === "$or") {
        if (!Array.isArray(value)) {
          throw new Error(`${key} filter value must be an array.`);
        }

        const nested = value
          .map((entry) => this.buildMetadataVertexFilter(entry))
          .filter((entry): entry is NeptuneVertexFilter => !!entry);
        const joiner = key === "$and" ? "andAll" : "orAll";
        const combined = this.combineVertexFilters(joiner, nested);
        if (combined) {
          operations.push(combined);
        }
        continue;
      }

      if (key === "$not") {
        if (!Array.isArray(value)) {
          throw new Error("$not filter value must be an array.");
        }

        const nested = value
          .map((entry) => this.buildMetadataVertexFilter(entry))
          .filter((entry): entry is NeptuneVertexFilter => !!entry)
          .map((entry) => this.negateVertexFilter(entry));
        const combined = this.combineVertexFilters("andAll", nested);
        if (combined) {
          operations.push(combined);
        }
        continue;
      }

      operations.push(this.buildFieldVertexFilter(key, value));
    }

    return this.combineVertexFilters("andAll", operations);
  }

  private combineVertexFilters(
    joiner: "andAll" | "orAll",
    operations: NeptuneVertexFilter[],
  ): NeptuneVertexFilter | undefined {
    if (operations.length === 0) {
      return undefined;
    }

    if (operations.length === 1) {
      return operations[0];
    }

    return {
      [joiner]: operations,
    };
  }

  private buildFieldVertexFilter(key: string, value: any): NeptuneVertexFilter {
    if (value === "*") {
      throw new Error(
        "Neptune Analytics vector search does not support property-existence filters.",
      );
    }

    if (Array.isArray(value)) {
      return {
        in: {
          property: key,
          value,
        },
      };
    }

    if (typeof value !== "object" || value === null) {
      return {
        equals: {
          property: key,
          value,
        },
      };
    }

    const operations = Object.entries(value).map(([operator, operand]) =>
      this.buildSingleVertexFilter(key, operator, operand),
    );

    return this.combineVertexFilters("andAll", operations)!;
  }

  private buildSingleVertexFilter(
    key: string,
    operator: string,
    operand: any,
  ): NeptuneVertexFilter {
    switch (operator) {
      case "eq":
        return {
          equals: {
            property: key,
            value: operand,
          },
        };
      case "ne":
        return {
          notEquals: {
            property: key,
            value: operand,
          },
        };
      case "gt":
        return {
          greaterThan: {
            property: key,
            value: operand,
          },
        };
      case "gte":
        return {
          greaterThanOrEquals: {
            property: key,
            value: operand,
          },
        };
      case "lt":
        return {
          lessThan: {
            property: key,
            value: operand,
          },
        };
      case "lte":
        return {
          lessThanOrEquals: {
            property: key,
            value: operand,
          },
        };
      case "in":
        return {
          in: {
            property: key,
            value: operand,
          },
        };
      case "nin":
        return {
          notIn: {
            property: key,
            value: operand,
          },
        };
      case "contains":
        return {
          stringContains: {
            property: key,
            value: operand,
          },
        };
      case "startsWith":
        return {
          startsWith: {
            property: key,
            value: operand,
          },
        };
      case "icontains":
        throw new Error(
          "Neptune Analytics vector search does not support case-insensitive contains filters.",
        );
      default:
        throw new Error(
          `Unsupported Neptune Analytics filter operator: ${operator}`,
        );
    }
  }

  private negateVertexFilter(filter: NeptuneVertexFilter): NeptuneVertexFilter {
    if (Array.isArray(filter.andAll)) {
      return this.combineVertexFilters(
        "orAll",
        filter.andAll.map((entry: NeptuneVertexFilter) =>
          this.negateVertexFilter(entry),
        ),
      )!;
    }

    if (Array.isArray(filter.orAll)) {
      return this.combineVertexFilters(
        "andAll",
        filter.orAll.map((entry: NeptuneVertexFilter) =>
          this.negateVertexFilter(entry),
        ),
      )!;
    }

    if (filter.equals) {
      return {
        notEquals: filter.equals,
      };
    }

    if (filter.notEquals) {
      return {
        equals: filter.notEquals,
      };
    }

    if (filter.greaterThan) {
      return {
        lessThanOrEquals: filter.greaterThan,
      };
    }

    if (filter.greaterThanOrEquals) {
      return {
        lessThan: filter.greaterThanOrEquals,
      };
    }

    if (filter.lessThan) {
      return {
        greaterThanOrEquals: filter.lessThan,
      };
    }

    if (filter.lessThanOrEquals) {
      return {
        greaterThan: filter.lessThanOrEquals,
      };
    }

    if (filter.in) {
      return {
        notIn: filter.in,
      };
    }

    if (filter.notIn) {
      return {
        in: filter.notIn,
      };
    }

    throw new Error(
      "Neptune Analytics cannot negate this filter shape for vector search.",
    );
  }

  private buildWhereClause(
    filters?: SearchFilters,
    startIndex: number = 1,
  ): WhereClauseResult {
    const clauses: string[] = [];
    const parameters: Record<string, any> = {};
    let nextIndex = startIndex;

    for (const [key, value] of Object.entries(filters || {})) {
      if (value === undefined) {
        continue;
      }

      if (key === "$and" || key === "$or") {
        if (!Array.isArray(value)) {
          throw new Error(`${key} filter value must be an array.`);
        }

        const nestedClauses: string[] = [];
        for (const entry of value) {
          const nested = this.buildWhereClause(entry, nextIndex);
          nextIndex = nested.nextIndex;
          Object.assign(parameters, nested.parameters);
          if (nested.clause) {
            nestedClauses.push(nested.clause);
          }
        }

        if (nestedClauses.length > 0) {
          const joiner = key === "$and" ? " AND " : " OR ";
          clauses.push(`(${nestedClauses.join(joiner)})`);
        }
        continue;
      }

      if (key === "$not") {
        if (!Array.isArray(value)) {
          throw new Error("$not filter value must be an array.");
        }

        const nestedClauses: string[] = [];
        for (const entry of value) {
          const nested = this.buildWhereClause(entry, nextIndex);
          nextIndex = nested.nextIndex;
          Object.assign(parameters, nested.parameters);
          if (nested.clause) {
            nestedClauses.push(nested.clause);
          }
        }

        if (nestedClauses.length > 0) {
          clauses.push(`NOT (${nestedClauses.join(" OR ")})`);
        }
        continue;
      }

      const fieldResult = this.buildFieldWhereClauses(key, value, nextIndex);
      nextIndex = fieldResult.nextIndex;
      Object.assign(parameters, fieldResult.parameters);
      clauses.push(...fieldResult.clauses);
    }

    return {
      clause: clauses.join(" AND "),
      parameters,
      nextIndex,
    };
  }

  private buildFieldWhereClauses(
    key: string,
    value: any,
    startIndex: number,
  ): {
    clauses: string[];
    parameters: Record<string, any>;
    nextIndex: number;
  } {
    const field = `n.${this.escapeProperty(key)}`;
    const parameters: Record<string, any> = {};
    const clauses: string[] = [];
    let nextIndex = startIndex;

    const addParameter = (prefix: string, rawValue: any) => {
      const parameterName = `${prefix}_${key.replace(/[^\w]/g, "_")}_${nextIndex}`;
      parameters[parameterName] = rawValue;
      nextIndex += 1;
      return parameterName;
    };

    if (value === "*") {
      return {
        clauses: [`${field} IS NOT NULL`],
        parameters,
        nextIndex,
      };
    }

    if (Array.isArray(value)) {
      const parameterName = addParameter("filter_in", value);
      return {
        clauses: [`${field} IN $${parameterName}`],
        parameters,
        nextIndex,
      };
    }

    if (typeof value !== "object" || value === null) {
      const parameterName = addParameter("filter", value);
      return {
        clauses: [`${field} = $${parameterName}`],
        parameters,
        nextIndex,
      };
    }

    for (const [operator, operand] of Object.entries(value)) {
      const parameterName = addParameter(`filter_${operator}`, operand);
      switch (operator) {
        case "eq":
          clauses.push(`${field} = $${parameterName}`);
          break;
        case "ne":
          clauses.push(`${field} <> $${parameterName}`);
          break;
        case "gt":
          clauses.push(`${field} > $${parameterName}`);
          break;
        case "gte":
          clauses.push(`${field} >= $${parameterName}`);
          break;
        case "lt":
          clauses.push(`${field} < $${parameterName}`);
          break;
        case "lte":
          clauses.push(`${field} <= $${parameterName}`);
          break;
        case "in":
          clauses.push(`${field} IN $${parameterName}`);
          break;
        case "nin":
          clauses.push(`NOT ${field} IN $${parameterName}`);
          break;
        case "contains":
          clauses.push(`toString(${field}) CONTAINS $${parameterName}`);
          break;
        case "icontains":
          throw new Error(
            "Neptune Analytics list filters do not support case-insensitive contains filters.",
          );
        case "startsWith":
          clauses.push(`toString(${field}) STARTS WITH $${parameterName}`);
          break;
        default:
          throw new Error(
            `Unsupported Neptune Analytics filter operator: ${operator}`,
          );
      }
    }

    return {
      clauses,
      parameters,
      nextIndex,
    };
  }

  private escapeProperty(key: string): string {
    return `\`${key.replace(/`/g, "``")}\``;
  }

  private serializeAlgorithmInput(value: any): string {
    if (Array.isArray(value)) {
      return `[${value.map((entry) => this.serializeAlgorithmInput(entry)).join(", ")}]`;
    }

    if (value === null) {
      return "null";
    }

    if (typeof value === "string") {
      return JSON.stringify(value);
    }

    if (typeof value === "number" || typeof value === "boolean") {
      return String(value);
    }

    if (typeof value === "object") {
      return `{ ${Object.entries(value)
        .map(
          ([key, entry]) =>
            `${this.serializeAlgorithmKey(key)}: ${this.serializeAlgorithmInput(entry)}`,
        )
        .join(", ")} }`;
    }

    throw new Error(
      `Unsupported Neptune Analytics algorithm value type: ${typeof value}`,
    );
  }

  private serializeAlgorithmKey(key: string): string {
    if (/^[A-Za-z_][A-Za-z0-9_]*$/.test(key)) {
      return key;
    }

    return JSON.stringify(key);
  }

  private assertVectorDimension(vector: number[], context: string): void {
    if (vector.length !== this.dimension) {
      throw new Error(
        `${context} dimension mismatch. Expected ${this.dimension}, got ${vector.length}`,
      );
    }
  }

  private assertBatchDimensions(vectors: number[][], context: string): void {
    for (const vector of vectors) {
      this.assertVectorDimension(vector, context);
    }
  }

  private normalizeNodeResult(record: NeptuneQueryRecord): VectorStoreResult {
    const node = this.extractNode(record);
    const payload = this.normalizePayload(this.extractPayload(node));

    return {
      id: this.extractId(node, record),
      payload,
    };
  }

  private normalizeSearchResult(record: NeptuneQueryRecord): VectorStoreResult {
    const base = this.normalizeNodeResult(record);
    const score = this.normalizeScore(record.score);

    return {
      ...base,
      score,
    };
  }

  private extractNode(record: NeptuneQueryRecord): Record<string, any> {
    return (
      record.n || record.node || record.m || record.item || record.v || record
    );
  }

  private extractPayload(node: Record<string, any>): Record<string, any> {
    return node["~properties"] || node.properties || node.payload || {};
  }

  private extractId(
    node: Record<string, any>,
    record: NeptuneQueryRecord,
  ): string {
    const rawId = node["~id"] || node.id || record.id;
    return String(rawId);
  }

  private extractUserId(record: NeptuneQueryRecord): string | undefined {
    const node = this.extractNode(record);
    const payload = this.extractPayload(node);
    const userId = payload.user_id || payload.userId;
    return userId ? String(userId) : undefined;
  }

  private normalizePayload(payload: Record<string, any>): Record<string, any> {
    return { ...payload };
  }

  private normalizeScore(score: unknown): number | undefined {
    if (score === undefined || score === null) {
      return undefined;
    }

    const numericScore = Number(score);
    if (!Number.isFinite(numericScore)) {
      return undefined;
    }

    // Neptune returns squared Euclidean distance, while Memory search expects higher-is-better scores.
    return 1 / (1 + Math.max(0, numericScore));
  }

  private assertSuccessfulResults(
    results: NeptuneQueryRecord[],
    context: string,
  ): void {
    for (const record of results) {
      if ("success" in record && record.success !== true) {
        throw new Error(`${context} failed in Neptune Analytics`);
      }
    }
  }

  /**
   * Load the optional AWS SDK on first use.
   *
   * This MUST be a dynamic `import()`, never `require()`: tsup/esbuild rewrite
   * `require()` in the published ESM bundle (`dist/oss/index.mjs`) into a
   * `__require` shim that throws `Dynamic require of "..." is not supported`,
   * so every ESM consumer would hit a dead provider even with the SDK installed.
   */
  private async getSDK(): Promise<NeptuneSDK> {
    if (!this.sdkPromise) {
      this.sdkPromise = import("@aws-sdk/client-neptune-graph").then(
        (sdk) => sdk as unknown as NeptuneSDK,
        (err) => {
          // Let a later call retry rather than caching the rejection forever.
          this.sdkPromise = undefined;
          const detail = err instanceof Error ? err.message : String(err);
          throw new Error(
            "The '@aws-sdk/client-neptune-graph' package is required to use the Neptune Analytics vector store. " +
              `Install it with: npm install @aws-sdk/client-neptune-graph (original error: ${detail})`,
          );
        },
      );
    }
    return this.sdkPromise;
  }

  /** Memoized Neptune client; an injected `config.client` short-circuits the SDK. */
  private async getClient(): Promise<NeptuneGraphClientLike> {
    if (this.clientOverride) return this.clientOverride;
    if (!this.clientPromise) {
      this.clientPromise = this.getSDK()
        .then(
          ({ NeptuneGraphClient }) => new NeptuneGraphClient(this.clientConfig),
        )
        .catch((err) => {
          // Mirror getSDK(): drop the rejected promise so a later call retries rather than
          // replaying a cached rejection forever (a rejected promise is still truthy, so the
          // `!this.clientPromise` guard above would otherwise never re-enter).
          this.clientPromise = undefined;
          throw err;
        });
    }
    return this.clientPromise;
  }

  private async executeQuery(
    queryString: string,
    parameters: Record<string, any> = {},
  ): Promise<NeptuneQueryRecord[]> {
    const [client, sdk] = await Promise.all([this.getClient(), this.getSDK()]);
    const response = await client.send(
      new sdk.ExecuteQueryCommand({
        graphIdentifier: this.graphIdentifier,
        language: "OPEN_CYPHER",
        queryString,
        parameters: Object.keys(parameters).length > 0 ? parameters : undefined,
      }),
    );

    const rawPayload = response.payload
      ? await response.payload.transformToString("utf-8")
      : "";

    if (!rawPayload.trim()) {
      return [];
    }

    const parsed = JSON.parse(rawPayload) as
      | NeptuneQueryRecord[]
      | { results?: NeptuneQueryRecord[]; result?: NeptuneQueryRecord[] };

    if (Array.isArray(parsed)) {
      return parsed;
    }

    if (Array.isArray(parsed.results)) {
      return parsed.results;
    }

    if (Array.isArray(parsed.result)) {
      return parsed.result;
    }

    return [];
  }
}
