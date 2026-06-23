import {
  ExecuteQueryCommand,
  NeptuneGraphClient,
} from "@aws-sdk/client-neptune-graph";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

interface NeptuneAnalyticsConfig extends VectorStoreConfig {
  graphIdentifier?: string;
  endpoint?: string;
  collectionName: string;
  dimension?: number;
  client?: NeptuneGraphClientLike;
}

interface NeptuneGraphClientLike {
  send(command: ExecuteQueryCommand): Promise<NeptuneExecuteQueryOutput>;
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
  private readonly client: NeptuneGraphClientLike;
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
    this.client = config.client || new NeptuneGraphClient({});

    void this.initialize();
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

    const insertQuery = `
      UNWIND $rows AS row
      OPTIONAL MATCH (existing:${this.collectionLabelExpr} {\`~id\`: row.node_id})
      MERGE (n:${this.collectionLabelExpr} {\`~id\`: row.node_id})
      WITH n, row, existing IS NULL AS created
      CALL neptune.algo.vectors.upsert(n, row.embedding)
      YIELD success
      FOREACH (_ IN CASE WHEN success THEN [1] ELSE [] END | SET n += row.properties)
      FOREACH (_ IN CASE WHEN success OR NOT created THEN [] ELSE [1] END | DETACH DELETE n)
      RETURN success
    `;

    try {
      const results = await this.executeQuery(insertQuery, { rows });
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
        CALL neptune.algo.vectors.topK.byEmbedding({
          topK: $topK,
          embedding: $embedding,
          vertexFilter: $vertexFilter
        })
        YIELD node, score
        RETURN node, score
      `,
      {
        topK,
        embedding: query,
        vertexFilter,
      },
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

    if (hasPayload && hasVector) {
      const properties = this.buildStoredPayload(payload);
      const results = await this.executeQuery(
        `
          MATCH (n:${this.collectionLabelExpr} {\`~id\`: $vectorId})
          WITH n, $embedding AS embedding, $properties AS properties
          CALL neptune.algo.vectors.upsert(n, embedding)
          YIELD success
          FOREACH (_ IN CASE WHEN success THEN [1] ELSE [] END | SET n = properties)
          RETURN success
        `,
        {
          vectorId,
          embedding: vector,
          properties,
        },
      );
      this.assertSuccessfulResults(results, "Update");
      return;
    }

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

  private async listCols(): Promise<string[]> {
    const results = await this.executeQuery(
      `
        CALL neptune.graph.pg_schema()
        YIELD schema
        RETURN [label IN schema.nodeLabels WHERE label STARTS WITH $prefix] AS result
      `,
      {
        prefix: "MEM0_VECTOR_",
      },
    );

    const labels = results[0]?.result;
    if (Array.isArray(labels)) {
      return labels.map((label) => String(label));
    }

    return [];
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
    } catch {
      return;
    }
  }

  private resolveGraphIdentifier(config: NeptuneAnalyticsConfig): string {
    const rawIdentifier = config.graphIdentifier || config.endpoint;

    if (!rawIdentifier) {
      throw new Error(
        "Neptune Analytics vector store requires graphIdentifier or endpoint.",
      );
    }

    if (rawIdentifier.startsWith("neptune-graph://")) {
      return rawIdentifier.slice("neptune-graph://".length);
    }

    return rawIdentifier;
  }

  private escapeLabel(label: string): string {
    return `\`${label.replace(/`/g, "``")}\``;
  }

  private buildStoredPayload(
    payload: Record<string, any>,
  ): Record<string, any> {
    return {
      ...payload,
      updated_at: new Date().toISOString(),
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

  private async executeQuery(
    queryString: string,
    parameters: Record<string, any> = {},
  ): Promise<NeptuneQueryRecord[]> {
    const response = await this.client.send(
      new ExecuteQueryCommand({
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
