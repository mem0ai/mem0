import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

interface DatabricksConfig extends VectorStoreConfig {
  workspaceUrl: string;
  accessToken?: string;
  clientId?: string;
  clientSecret?: string;
  endpointName: string;
  catalog: string;
  schema: string;
  tableName: string;
  collectionName?: string;
  indexType?: "DELTA_SYNC" | "DIRECT_ACCESS";
  embeddingModelEndpointName?: string;
  embeddingDimension?: number;
  endpointType?: "STANDARD" | "STORAGE_OPTIMIZED";
  pipelineType?: "TRIGGERED" | "CONTINUOUS";
  warehouseName?: string;
  queryType?: "ANN" | "HYBRID";
}

const EXCLUDED_KEYS = new Set([
  "user_id",
  "agent_id",
  "run_id",
  "hash",
  "data",
  "created_at",
  "updated_at",
]);

const VALID_SQL_IDENTIFIER = /^[A-Za-z_][A-Za-z0-9_]*$/;

const COLUMN_DEFINITIONS = [
  { name: "memory_id", type: "STRING" },
  { name: "hash", type: "STRING" },
  { name: "agent_id", type: "STRING" },
  { name: "run_id", type: "STRING" },
  { name: "user_id", type: "STRING" },
  { name: "memory", type: "STRING" },
  { name: "metadata", type: "STRING" },
  { name: "created_at", type: "TIMESTAMP" },
  { name: "updated_at", type: "TIMESTAMP" },
];

export class DatabricksVectorStore implements VectorStore {
  private readonly workspaceUrl: string;
  private readonly accessToken?: string;
  private readonly clientId?: string;
  private readonly clientSecret?: string;
  private readonly endpointName: string;
  private readonly catalog: string;
  private readonly schema: string;
  private readonly tableName: string;
  private readonly indexName: string;
  private readonly fullyQualifiedTableName: string;
  private readonly fullyQualifiedIndexName: string;
  private readonly indexType: "DELTA_SYNC" | "DIRECT_ACCESS";
  private readonly embeddingModelEndpointName?: string;
  private readonly embeddingDimension: number;
  private readonly endpointType: string;
  private readonly pipelineType: string;
  private readonly queryType: string;
  private readonly columnNames: string[];
  private readonly warehouseName?: string;
  private warehouseId?: string;
  private _initPromise?: Promise<void>;
  private _oauthToken?: string;
  private _oauthTokenExpiry?: number;

  constructor(config: DatabricksConfig) {
    this.workspaceUrl = config.workspaceUrl.replace(/\/$/, "");
    this.accessToken = config.accessToken;
    this.clientId = config.clientId;
    this.clientSecret = config.clientSecret;
    this.endpointName = config.endpointName;
    this.catalog = config.catalog;
    this.schema = config.schema;
    this.tableName = config.tableName;
    this.indexName = config.collectionName || "mem0";
    this.fullyQualifiedTableName = `${this.catalog}.${this.schema}.${this.tableName}`;
    this.fullyQualifiedIndexName = `${this.catalog}.${this.schema}.${this.indexName}`;
    this.indexType = config.indexType || "DELTA_SYNC";
    this.embeddingModelEndpointName = config.embeddingModelEndpointName;
    this.embeddingDimension = config.embeddingDimension || 1536;
    this.endpointType = config.endpointType || "STANDARD";
    this.pipelineType = config.pipelineType || "TRIGGERED";
    this.queryType = config.queryType || "ANN";
    this.warehouseName = config.warehouseName;

    const columns = [...COLUMN_DEFINITIONS];
    if (this.indexType === "DIRECT_ACCESS") {
      columns.push({ name: "embedding", type: "ARRAY" });
    }
    this.columnNames = columns.map((c) => c.name);

    this.initialize().catch(console.error);
  }

  private async getAuthHeaders(): Promise<Record<string, string>> {
    if (this.accessToken) {
      return {
        Authorization: `Bearer ${this.accessToken}`,
        "Content-Type": "application/json",
      };
    }

    if (this.clientId && this.clientSecret) {
      // Use OAuth M2M token if not cached or expired
      if (!this._oauthToken || (this._oauthTokenExpiry && Date.now() >= this._oauthTokenExpiry)) {
        const tokenUrl = `${this.workspaceUrl}/oidc/v1/token`;
        const body = new URLSearchParams({
          grant_type: "client_credentials",
          scope: "all-apis",
        });

        const response = await fetch(tokenUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
            Authorization: `Basic ${Buffer.from(`${this.clientId}:${this.clientSecret}`).toString("base64")}`,
          },
          body: body.toString(),
        });

        if (!response.ok) {
          throw new Error(
            `OAuth token request failed: ${response.status} ${response.statusText}`,
          );
        }

        const data = (await response.json()) as {
          access_token: string;
          expires_in: number;
        };
        this._oauthToken = data.access_token;
        // Expire 60s early to avoid edge cases
        this._oauthTokenExpiry = Date.now() + (data.expires_in - 60) * 1000;
      }

      return {
        Authorization: `Bearer ${this._oauthToken}`,
        "Content-Type": "application/json",
      };
    }

    throw new Error(
      "Databricks authentication requires either accessToken or clientId + clientSecret",
    );
  }

  private async request(
    path: string,
    options: RequestInit = {},
  ): Promise<any> {
    const headers = await this.getAuthHeaders();
    const url = `${this.workspaceUrl}${path}`;

    const response = await fetch(url, {
      ...options,
      headers: { ...headers, ...options.headers },
    });

    if (!response.ok) {
      const errorBody = await response.text();
      throw new Error(
        `Databricks API error (${response.status}): ${errorBody}`,
      );
    }

    const text = await response.text();
    return text ? JSON.parse(text) : undefined;
  }

  async initialize(): Promise<void> {
    if (!this._initPromise) {
      this._initPromise = this._doInitialize();
    }
    return this._initPromise;
  }

  private async _doInitialize(): Promise<void> {
    // Resolve warehouse ID by name (matches Python: filters by warehouse_name)
    if (!this.warehouseId) {
      const warehouses = await this.request("/api/2.0/sql/warehouses");
      const warehouseList: Array<{ id: string; name: string }> =
        warehouses.warehouses || [];

      if (this.warehouseName) {
        const match = warehouseList.find(
          (w) => w.name === this.warehouseName,
        );
        this.warehouseId = match?.id;
      } else {
        this.warehouseId = warehouseList[0]?.id;
      }

      if (!this.warehouseId) {
        const detail = this.warehouseName
          ? `No warehouse named '${this.warehouseName}' found`
          : "No warehouses found in workspace";
        throw new Error(
          `Databricks initialization failed: ${detail}. ` +
            `Available warehouses: ${warehouseList.map((w) => w.name).join(", ") || "(none)"}`,
        );
      }
    }

    await this.ensureEndpointExists();

    const collections = await this.listCols();
    if (!collections.includes(this.fullyQualifiedIndexName)) {
      await this.createCol();
    }
  }

  private async ensureEndpointExists(): Promise<void> {
    try {
      await this.request(
        `/api/2.0/vector-search/endpoints/${this.endpointName}`,
      );
    } catch {
      // Endpoint doesn't exist, create it
      await this.request("/api/2.0/vector-search/endpoints", {
        method: "POST",
        body: JSON.stringify({
          name: this.endpointName,
          endpoint_type: this.endpointType,
        }),
      });
    }
  }

  private async ensureSourceTableExists(): Promise<void> {
    try {
      const check = await this.request(
        `/api/2.1/unity-catalog/tables/${this.fullyQualifiedTableName}`,
      );
      if (check) return; // Table exists
    } catch {
      // Table doesn't exist, create it
    }

    const columns = COLUMN_DEFINITIONS.map((col, i) => ({
      name: col.name,
      type_name: col.type,
      type_text: col.type.toLowerCase(),
      position: i,
      nullable: col.name !== "memory_id",
    }));

    if (this.indexType === "DIRECT_ACCESS") {
      columns.push({
        name: "embedding",
        type_name: "ARRAY",
        type_text: "array<float>",
        position: columns.length,
        nullable: true,
      });
    }

    await this.request("/api/2.1/unity-catalog/tables", {
      method: "POST",
      body: JSON.stringify({
        name: this.tableName,
        catalog_name: this.catalog,
        schema_name: this.schema,
        table_type: "MANAGED",
        data_source_format: "DELTA",
        columns,
        properties: { "delta.enableChangeDataFeed": "true" },
      }),
    });

    // Add primary key constraint
    await this.executeSQL(
      `ALTER TABLE ${this.fullyQualifiedTableName} ADD CONSTRAINT pk_${this.tableName} PRIMARY KEY (memory_id)`,
    );
  }

  private async createCol(): Promise<void> {
    await this.ensureSourceTableExists();

    const embeddingSourceColumns = [
      {
        name: "memory",
        embedding_model_endpoint_name: this.embeddingModelEndpointName,
      },
    ];

    if (this.indexType === "DELTA_SYNC") {
      await this.request("/api/2.0/vector-search/indexes", {
        method: "POST",
        body: JSON.stringify({
          name: this.fullyQualifiedIndexName,
          endpoint_name: this.endpointName,
          primary_key: "memory_id",
          index_type: "DELTA_SYNC",
          delta_sync_index_spec: {
            source_table: this.fullyQualifiedTableName,
            pipeline_type: this.pipelineType,
            columns_to_sync: this.columnNames,
            embedding_source_columns: embeddingSourceColumns,
          },
        }),
      });
    } else {
      await this.request("/api/2.0/vector-search/indexes", {
        method: "POST",
        body: JSON.stringify({
          name: this.fullyQualifiedIndexName,
          endpoint_name: this.endpointName,
          primary_key: "memory_id",
          index_type: "DIRECT_ACCESS",
          direct_access_index_spec: {
            embedding_source_columns: embeddingSourceColumns,
            embedding_vector_columns: [
              {
                name: "embedding",
                embedding_dimension: this.embeddingDimension,
              },
            ],
          },
        }),
      });
    }
  }

  private async listCols(): Promise<string[]> {
    const result = await this.request(
      `/api/2.0/vector-search/indexes?endpoint_name=${encodeURIComponent(this.endpointName)}`,
    );
    const indexes = result.vector_indexes || [];
    return indexes.map((idx: any) => idx.name);
  }

  private formatSqlValue(v: any): string {
    if (v === null || v === undefined) return "NULL";
    if (typeof v === "boolean") return v ? "TRUE" : "FALSE";
    if (typeof v === "number") return String(v);
    if (v instanceof Date) return `'${v.toISOString()}'`;
    if (Array.isArray(v)) {
      const elems = v.map((x) => {
        if (x === null || x === undefined) return "NULL";
        if (typeof x === "number") return String(x);
        return `'${String(x).replace(/'/g, "''")}'`;
      });
      return `array(${elems.join(", ")})`;
    }
    if (typeof v === "object") {
      const s = JSON.stringify(v).replace(/'/g, "''");
      return `'${s}'`;
    }
    return `'${String(v).replace(/'/g, "''")}'`;
  }

  private async executeSQL(
    statement: string,
    parameters?: Array<{ name: string; value: string; type?: string }>,
  ): Promise<any> {
    const body: any = {
      statement,
      warehouse_id: this.warehouseId,
      wait_timeout: "30s",
    };
    if (parameters && parameters.length > 0) {
      body.parameters = parameters;
    }

    const result = await this.request("/api/2.0/sql/statements", {
      method: "POST",
      body: JSON.stringify(body),
    });

    if (result.status?.state !== "SUCCEEDED") {
      throw new Error(
        `SQL execution failed: ${JSON.stringify(result.status?.error || result.status)}`,
      );
    }

    return result;
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    const numItems = payloads?.length || vectors?.length || 0;
    const params: Array<{ name: string; value: string; type?: string }> = [];
    const valueTuples: string[] = [];

    for (let i = 0; i < numItems; i++) {
      const placeholders: string[] = [];

      for (const colName of this.columnNames) {
        const paramName = `${colName}_${i}`;

        if (colName === "memory_id") {
          const val = ids?.[i] || crypto.randomUUID();
          placeholders.push(`:${paramName}`);
          params.push({ name: paramName, value: String(val) });
        } else if (colName === "embedding") {
          const val = vectors?.[i] || [];
          placeholders.push(this.formatSqlValue(val));
        } else if (colName === "memory") {
          const val = payloads?.[i]?.data;
          if (val == null) {
            placeholders.push("NULL");
          } else {
            placeholders.push(`:${paramName}`);
            params.push({ name: paramName, value: String(val) });
          }
        } else {
          const val = payloads?.[i]?.[colName];
          if (val == null) {
            placeholders.push("NULL");
          } else {
            placeholders.push(`:${paramName}`);
            const strVal =
              typeof val === "object" ? JSON.stringify(val) : String(val);
            const param: { name: string; value: string; type?: string } = {
              name: paramName,
              value: strVal,
            };
            if (colName === "created_at" || colName === "updated_at") {
              param.type = "TIMESTAMP";
            }
            params.push(param);
          }
        }
      }

      valueTuples.push(`(${placeholders.join(", ")})`);
    }

    const sql = `INSERT INTO ${this.fullyQualifiedTableName} (${this.columnNames.join(", ")}) VALUES ${valueTuples.join(", ")}`;
    await this.executeSQL(sql, params);
  }

  async search(
    query: number[],
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    const queryBody: any = {
      columns: this.columnNames,
      num_results: topK,
      query_type: this.queryType,
    };

    if (filters && Object.keys(filters).length > 0) {
      queryBody.filters_json = JSON.stringify(filters);
    }

    const usesModelEndpoint =
      this.indexType === "DELTA_SYNC" && this.embeddingModelEndpointName;
    if (usesModelEndpoint) {
      throw new Error(
        "DELTA_SYNC indexes with embeddingModelEndpointName require query text for search, " +
          "but the TypeScript VectorStore interface only provides embedding vectors. " +
          "Use DIRECT_ACCESS or DELTA_SYNC without embeddingModelEndpointName instead.",
      );
    } else if (query && query.length > 0) {
      queryBody.query_vector = query;
    } else {
      throw new Error("Must provide query vector for search");
    }

    const result = await this.request(
      `/api/2.0/vector-search/indexes/${encodeURIComponent(this.fullyQualifiedIndexName)}/query`,
      {
        method: "POST",
        body: JSON.stringify(queryBody),
      },
    );

    return this.parseQueryResults(result);
  }

  async keywordSearch(
    query: string,
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[] | null> {
    if (this.indexType === "DIRECT_ACCESS") {
      return null;
    }

    const queryBody: any = {
      columns: this.columnNames,
      query_text: query,
      num_results: topK,
      query_type: "FULL_TEXT",
    };

    if (filters && Object.keys(filters).length > 0) {
      queryBody.filters_json = JSON.stringify(filters);
    }

    const result = await this.request(
      `/api/2.0/vector-search/indexes/${encodeURIComponent(this.fullyQualifiedIndexName)}/query`,
      {
        method: "POST",
        body: JSON.stringify(queryBody),
      },
    );

    return this.parseQueryResults(result);
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    const queryBody: any = {
      columns: this.columnNames,
      num_results: 1,
      query_type: this.queryType,
      filters_json: JSON.stringify({ memory_id: vectorId }),
    };

    const usesModelEndpoint =
      this.indexType === "DELTA_SYNC" && this.embeddingModelEndpointName;
    if (usesModelEndpoint) {
      queryBody.query_text = " ";
    } else {
      queryBody.query_vector = new Array(this.embeddingDimension).fill(0.0);
    }

    const result = await this.request(
      `/api/2.0/vector-search/indexes/${encodeURIComponent(this.fullyQualifiedIndexName)}/query`,
      {
        method: "POST",
        body: JSON.stringify(queryBody),
      },
    );

    const dataArray = result?.result?.data_array || [];
    if (dataArray.length === 0) return null;

    const columns =
      result?.manifest?.columns?.map((c: any) => c.name) || this.columnNames;
    const row = dataArray[0];
    const rowDict: Record<string, any> = {};
    columns.forEach((col: string, idx: number) => {
      rowDict[col] = row[idx];
    });

    const payload: Record<string, any> = {
      hash: rowDict.hash || "unknown",
      data: rowDict.memory || rowDict.data || "unknown",
      created_at: rowDict.created_at,
    };

    if (rowDict.updated_at) payload.updated_at = rowDict.updated_at;
    for (const field of ["agent_id", "run_id", "user_id"]) {
      if (rowDict[field]) payload[field] = rowDict[field];
    }

    if (rowDict.metadata) {
      try {
        const metadata = JSON.parse(rowDict.metadata);
        Object.assign(payload, metadata);
      } catch {
        // Ignore parse errors
      }
    }

    return {
      id: rowDict.memory_id || vectorId,
      payload,
    };
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    const setClauses: string[] = [];
    const params: Array<{ name: string; value: string; type?: string }> = [];

    if (vector) {
      setClauses.push(`embedding = ${this.formatSqlValue(vector)}`);
    }

    if (payload) {
      for (const [key, value] of Object.entries(payload)) {
        if (EXCLUDED_KEYS.has(key)) continue;
        if (!VALID_SQL_IDENTIFIER.test(key)) continue;
        const paramName = `payload_${key}`;
        setClauses.push(`${key} = :${paramName}`);
        params.push({ name: paramName, value: String(value) });
      }
    }

    if (setClauses.length === 0) return;

    const sql = `UPDATE ${this.fullyQualifiedTableName} SET ${setClauses.join(", ")} WHERE memory_id = :vector_id`;
    params.push({ name: "vector_id", value: String(vectorId) });
    await this.executeSQL(sql, params);
  }

  async delete(vectorId: string): Promise<void> {
    const sql = `DELETE FROM ${this.fullyQualifiedTableName} WHERE memory_id = :vector_id`;
    await this.executeSQL(sql, [
      { name: "vector_id", value: String(vectorId) },
    ]);
  }

  async deleteCol(): Promise<void> {
    try {
      await this.request(
        `/api/2.0/vector-search/indexes/${encodeURIComponent(this.fullyQualifiedIndexName)}`,
        { method: "DELETE" },
      );
    } catch {
      // Fallback to short index name (mirrors Python's delete_col behavior)
      await this.request(
        `/api/2.0/vector-search/indexes/${encodeURIComponent(this.indexName)}`,
        { method: "DELETE" },
      );
    }
  }

  async list(
    filters?: SearchFilters,
    topK: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    const queryBody: any = {
      columns: this.columnNames,
      num_results: topK,
      query_type: this.queryType,
    };

    if (filters && Object.keys(filters).length > 0) {
      queryBody.filters_json = JSON.stringify(filters);
    }

    const usesModelEndpoint =
      this.indexType === "DELTA_SYNC" && this.embeddingModelEndpointName;
    if (usesModelEndpoint) {
      queryBody.query_text = " ";
    } else {
      queryBody.query_vector = new Array(this.embeddingDimension).fill(0.0);
    }

    const result = await this.request(
      `/api/2.0/vector-search/indexes/${encodeURIComponent(this.fullyQualifiedIndexName)}/query`,
      {
        method: "POST",
        body: JSON.stringify(queryBody),
      },
    );

    const results = this.parseQueryResults(result);
    return [results, results.length];
  }

  async getUserId(): Promise<string> {
    try {
      const result = await this.executeSQL(
        `SELECT user_id FROM ${this.catalog}.${this.schema}.memory_migrations LIMIT 1`,
      );

      const dataArray = result?.result?.data_array || [];
      if (dataArray.length > 0) {
        return dataArray[0][0];
      }
    } catch {
      // Table might not exist, create it
      await this.executeSQL(
        `CREATE TABLE IF NOT EXISTS ${this.catalog}.${this.schema}.memory_migrations (user_id STRING)`,
      );
    }

    const randomUserId =
      Math.random().toString(36).substring(2, 15) +
      Math.random().toString(36).substring(2, 15);
    await this.executeSQL(
      `INSERT INTO ${this.catalog}.${this.schema}.memory_migrations (user_id) VALUES (:user_id)`,
      [{ name: "user_id", value: randomUserId }],
    );
    return randomUserId;
  }

  async setUserId(userId: string): Promise<void> {
    try {
      await this.executeSQL(
        `DELETE FROM ${this.catalog}.${this.schema}.memory_migrations`,
      );
    } catch {
      await this.executeSQL(
        `CREATE TABLE IF NOT EXISTS ${this.catalog}.${this.schema}.memory_migrations (user_id STRING)`,
      );
    }
    await this.executeSQL(
      `INSERT INTO ${this.catalog}.${this.schema}.memory_migrations (user_id) VALUES (:user_id)`,
      [{ name: "user_id", value: userId }],
    );
  }

  private parseQueryResults(result: any): VectorStoreResult[] {
    const dataArray = result?.result?.data_array || [];
    const columns =
      result?.manifest?.columns?.map((c: any) => c.name) || this.columnNames;

    return dataArray.map((row: any[]) => {
      const rowDict: Record<string, any> = {};
      columns.forEach((col: string, idx: number) => {
        rowDict[col] = row[idx];
      });

      const score =
        rowDict.score ??
        (row.length > columns.length ? row[row.length - 1] : undefined);

      const payload: Record<string, any> = {};
      for (const col of this.columnNames) {
        payload[col] = rowDict[col];
      }
      payload.data = payload.memory || "";

      if (payload.metadata) {
        try {
          Object.assign(payload, JSON.parse(payload.metadata));
        } catch {
          // Ignore parse errors
        }
      }

      return {
        id: rowDict.memory_id || rowDict.id,
        payload,
        score: score != null ? Number(score) : undefined,
      };
    });
  }
}
