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

    const rows = vectors.map((vector, index) => ({
      node_id: ids[index],
      properties: this.buildStoredPayload(payloads[index] || {}),
      embedding: vector,
    }));

    const insertQuery = `
      UNWIND $rows AS row
      MERGE (n:${this.collectionLabelExpr} {\`~id\`: row.node_id})
      ON CREATE SET n = row.properties
      ON MATCH SET n += row.properties
    `;

    await this.executeQuery(insertQuery, { rows });

    const upsertQuery = `
      UNWIND $rows AS row
      MATCH (n:${this.collectionLabelExpr} {\`~id\`: row.node_id})
      WITH n, row.embedding AS embedding
      CALL neptune.algo.vectors.upsert(n, embedding)
      YIELD success
      RETURN success
    `;

    const results = await this.executeQuery(upsertQuery, { rows });
    this.assertSuccessfulResults(results, "Insert");
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

    if (payload && Object.keys(payload).length > 0) {
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

    if (vector.length > 0) {
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
    const results = await this.executeQuery(
      `
        MATCH (n:${this.collectionLabelExpr})
        ${clause}
        RETURN n
        LIMIT $limit
      `,
      {
        ...parameters,
        limit: topK,
      },
    );

    const items = results.map((record) => this.normalizeNodeResult(record));
    return [items, items.length];
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

  async listCols(): Promise<string[]> {
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
      label: this.collectionLabel,
      updated_at: new Date().toISOString(),
    };
  }

  private buildVertexFilter(
    filters?: SearchFilters,
  ): Record<string, any> | undefined {
    const conditions = [
      {
        equals: {
          property: "~label",
          value: this.collectionLabel,
        },
      },
    ];

    for (const [key, value] of Object.entries(filters || {})) {
      if (value === undefined) {
        continue;
      }

      conditions.push({
        equals: {
          property: key,
          value,
        },
      });
    }

    if (conditions.length === 1) {
      return conditions[0];
    }

    return {
      andAll: conditions,
    };
  }

  private buildWhereClause(filters?: SearchFilters): {
    clause: string;
    parameters: Record<string, any>;
  } {
    const clauses: string[] = [];
    const parameters: Record<string, any> = {};

    for (const [key, value] of Object.entries(filters || {})) {
      if (value === undefined) {
        continue;
      }

      const parameterName = `filter_${key.replace(/[^\w]/g, "_")}`;
      clauses.push(`n.${this.escapeProperty(key)} = $${parameterName}`);
      parameters[parameterName] = value;
    }

    return {
      clause: clauses.length > 0 ? `WHERE ${clauses.join(" AND ")}` : "",
      parameters,
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
    const normalized = { ...payload };
    delete normalized.label;
    return normalized;
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
