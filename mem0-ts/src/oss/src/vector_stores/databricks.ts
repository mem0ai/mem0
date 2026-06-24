import axios, { AxiosInstance } from "axios";
import { DBSQLClient } from "@databricks/sql";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

const SAFE_IDENTIFIER_RE = /^[A-Za-z_][A-Za-z0-9_]{0,127}$/;
const DEFAULT_PAGE_SIZE = 100;
const DATBRICKS_SERVER_FILTER_KEYS = new Set([
  "memory_id",
  "user_id",
  "agent_id",
  "run_id",
]);

interface DatabricksConfig extends VectorStoreConfig {
  workspaceUrl?: string;
  host?: string;
  httpPath: string;
  accessToken?: string;
  clientId?: string;
  clientSecret?: string;
  endpointName?: string;
  endpointType?: "STANDARD" | "STORAGE_OPTIMIZED";
  pipelineType?: "TRIGGERED" | "CONTINUOUS";
  queryType?: "ANN" | "HYBRID";
  catalog?: string;
  schema?: string;
  tableName?: string;
  embeddingModelDims?: number;
  sqlClient?: DatabricksSqlClientLike;
  httpClient?: DatabricksHttpClientLike;
}

interface DatabricksSqlClientLike {
  connect(options: Record<string, any>): Promise<DatabricksSqlClientLike>;
  openSession(): Promise<DatabricksSqlSessionLike>;
  close?(): Promise<any>;
}

interface DatabricksSqlSessionLike {
  executeStatement(statement: string): Promise<DatabricksSqlOperationLike>;
  close?(): Promise<any>;
}

interface DatabricksSqlOperationLike {
  fetchAll(): Promise<Array<Record<string, any>>>;
  close?(): Promise<any>;
}

interface DatabricksHttpClientLike {
  get(url: string, config?: Record<string, any>): Promise<{ data: any }>;
  post(
    url: string,
    data?: any,
    config?: Record<string, any>,
  ): Promise<{ data: any }>;
  delete(url: string, config?: Record<string, any>): Promise<{ data: any }>;
}

interface DatabricksVector {
  id: string;
  payload: Record<string, any>;
}

function validateIdentifier(
  name: string,
  label: string = "identifier",
): string {
  if (!SAFE_IDENTIFIER_RE.test(name)) {
    throw new Error(
      `Invalid ${label} '${name}': only letters, digits, and underscores are allowed, ` +
        `must start with a letter or underscore, and be at most 128 characters.`,
    );
  }
  return name;
}

function extractHostAndWorkspaceUrl(config: DatabricksConfig): {
  host: string;
  workspaceUrl: string;
} {
  if (config.workspaceUrl) {
    const url = new URL(config.workspaceUrl);
    return {
      host: url.host,
      workspaceUrl: `${url.protocol}//${url.host}`,
    };
  }

  if (config.host) {
    return {
      host: config.host,
      workspaceUrl: `https://${config.host}`,
    };
  }

  throw new Error(
    "Databricks vector store requires either workspaceUrl or host.",
  );
}

function formatSqlValue(value: any): string {
  if (value === null || value === undefined) {
    return "NULL";
  }
  if (typeof value === "boolean") {
    return value ? "TRUE" : "FALSE";
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      throw new Error("Databricks vector store only accepts finite numbers.");
    }
    return String(value);
  }
  if (Array.isArray(value)) {
    return `array(${value.map((entry) => formatSqlValue(entry)).join(", ")})`;
  }
  const json =
    typeof value === "string" ? value : JSON.stringify(value ?? {}) || "{}";
  return `'${json.replace(/'/g, "''")}'`;
}

function extractRowValue(row: Record<string, any>, keys: string[]): any {
  for (const key of keys) {
    if (key in row) {
      return row[key];
    }
    const upper = key.toUpperCase();
    if (upper in row) {
      return row[upper];
    }
  }
  return undefined;
}

function isPlainObject(value: any): value is Record<string, any> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function normalizeFilterValue(value: any): any {
  if (Array.isArray(value)) {
    return value.map((entry) => normalizeFilterValue(entry));
  }
  return value;
}

function isDatabricksServerFilterKey(key: string): boolean {
  return DATBRICKS_SERVER_FILTER_KEYS.has(key);
}

function mergeDatabricksFilters(
  target: Record<string, any>,
  source: Record<string, any>,
): boolean {
  for (const [key, value] of Object.entries(source)) {
    if (
      key in target &&
      JSON.stringify(target[key]) !== JSON.stringify(value)
    ) {
      return false;
    }
    target[key] = value;
  }
  return true;
}

function buildSimpleDatabricksFilter(
  key: string,
  value: any,
): Record<string, any> | null {
  if (!isDatabricksServerFilterKey(key)) {
    return null;
  }

  const safeKey = validateIdentifier(key, "filter key");

  if (!isPlainObject(value)) {
    return {
      [safeKey]: normalizeFilterValue(value),
    };
  }

  const entries = Object.entries(value);
  if (entries.length !== 1) {
    return null;
  }

  const [operator, operand] = entries[0];
  switch (operator) {
    case "eq":
      return { [safeKey]: normalizeFilterValue(operand) };
    case "ne":
      return { [`${safeKey} NOT`]: normalizeFilterValue(operand) };
    case "gt":
      return { [`${safeKey} >`]: normalizeFilterValue(operand) };
    case "gte":
      return { [`${safeKey} >=`]: normalizeFilterValue(operand) };
    case "lt":
      return { [`${safeKey} <`]: normalizeFilterValue(operand) };
    case "lte":
      return { [`${safeKey} <=`]: normalizeFilterValue(operand) };
    case "in":
      return Array.isArray(operand)
        ? { [safeKey]: normalizeFilterValue(operand) }
        : null;
    case "nin":
      return Array.isArray(operand) && operand.length === 1
        ? { [`${safeKey} NOT`]: normalizeFilterValue(operand[0]) }
        : null;
    default:
      return null;
  }
}

function buildDatabricksFilters(
  filters?: SearchFilters,
): Record<string, any> | undefined {
  if (!filters || Object.keys(filters).length === 0) {
    return undefined;
  }

  const result: Record<string, any> = {};

  for (const [key, value] of Object.entries(filters)) {
    if (key === "$and") {
      if (!Array.isArray(value)) {
        return undefined;
      }
      for (const entry of value) {
        if (!isPlainObject(entry)) {
          return undefined;
        }
        const nested = buildDatabricksFilters(entry as SearchFilters);
        if (!nested || !mergeDatabricksFilters(result, nested)) {
          return undefined;
        }
      }
      continue;
    }

    const converted = buildSimpleDatabricksFilter(key, value);
    if (!converted || !mergeDatabricksFilters(result, converted)) {
      return undefined;
    }
  }

  return Object.keys(result).length > 0 ? result : undefined;
}

function buildStandardDatabricksFiltersFromClauses(
  clauses: Array<[string, any]>,
): Record<string, any> | undefined {
  const result: Record<string, any> = {};

  for (const [key, value] of clauses) {
    const translated = buildSimpleDatabricksFilter(key, value);
    if (!translated) {
      continue;
    }
    if (!mergeDatabricksFilters(result, translated)) {
      return undefined;
    }
  }

  return Object.keys(result).length > 0 ? result : undefined;
}

function buildStorageOptimizedDatabricksFilterClause(
  key: string,
  value: any,
): string | null {
  if (!isDatabricksServerFilterKey(key)) {
    return null;
  }

  const safeKey = validateIdentifier(key, "filter key");

  if (!isPlainObject(value)) {
    return `${safeKey} = ${formatSqlValue(normalizeFilterValue(value))}`;
  }

  const entries = Object.entries(value);
  if (entries.length !== 1) {
    return null;
  }

  const [operator, operand] = entries[0];
  switch (operator) {
    case "eq":
      return `${safeKey} = ${formatSqlValue(normalizeFilterValue(operand))}`;
    case "ne":
      return `${safeKey} != ${formatSqlValue(normalizeFilterValue(operand))}`;
    case "gt":
      return `${safeKey} > ${formatSqlValue(normalizeFilterValue(operand))}`;
    case "gte":
      return `${safeKey} >= ${formatSqlValue(normalizeFilterValue(operand))}`;
    case "lt":
      return `${safeKey} < ${formatSqlValue(normalizeFilterValue(operand))}`;
    case "lte":
      return `${safeKey} <= ${formatSqlValue(normalizeFilterValue(operand))}`;
    case "in":
      return Array.isArray(operand) && operand.length > 0
        ? `${safeKey} IN (${operand
            .map((entry) => formatSqlValue(normalizeFilterValue(entry)))
            .join(", ")})`
        : null;
    case "nin":
      return Array.isArray(operand) && operand.length > 0
        ? `${safeKey} NOT IN (${operand
            .map((entry) => formatSqlValue(normalizeFilterValue(entry)))
            .join(", ")})`
        : null;
    default:
      return null;
  }
}

function collectConjunctiveDatabricksFilters(
  filters?: SearchFilters,
): Array<[string, any]> {
  if (!filters || Object.keys(filters).length === 0) {
    return [];
  }

  const clauses: Array<[string, any]> = [];

  for (const [key, value] of Object.entries(filters)) {
    if (key === "$and") {
      if (!Array.isArray(value)) {
        continue;
      }
      for (const entry of value) {
        if (!isPlainObject(entry)) {
          continue;
        }
        clauses.push(...collectConjunctiveDatabricksFilters(entry));
      }
      continue;
    }

    if (key === "$or" || key === "$not") {
      continue;
    }

    clauses.push([key, value]);
  }

  return clauses;
}

function buildDatabricksServerFilters(
  endpointType: "STANDARD" | "STORAGE_OPTIMIZED",
  filters?: SearchFilters,
): { filters?: string; filters_json?: string } {
  const clauses = collectConjunctiveDatabricksFilters(filters);

  if (clauses.length === 0) {
    return {};
  }

  if (endpointType === "STORAGE_OPTIMIZED") {
    const translatedClauses = clauses
      .map(([key, value]) =>
        buildStorageOptimizedDatabricksFilterClause(key, value),
      )
      .filter((clause): clause is string => Boolean(clause));

    return translatedClauses.length > 0
      ? { filters: translatedClauses.join(" AND ") }
      : {};
  }

  const translatedFilters = buildStandardDatabricksFiltersFromClauses(clauses);

  return translatedFilters
    ? { filters_json: JSON.stringify(translatedFilters) }
    : {};
}

export class DatabricksVectorStore implements VectorStore {
  private readonly host: string;
  private readonly workspaceUrl: string;
  private readonly httpPath: string;
  private readonly accessToken?: string;
  private readonly clientId?: string;
  private readonly clientSecret?: string;
  private readonly endpointName: string;
  private readonly endpointType: "STANDARD" | "STORAGE_OPTIMIZED";
  private readonly pipelineType: "TRIGGERED" | "CONTINUOUS";
  private readonly queryType: "ANN" | "HYBRID";
  private readonly dimension: number;
  private readonly catalog: string;
  private readonly schema: string;
  private readonly tableName: string;
  private readonly indexName: string;
  private readonly fullTableName: string;
  private readonly fullIndexName: string;
  private readonly sqlClient: DatabricksSqlClientLike;
  private readonly httpClient: DatabricksHttpClientLike;
  private session?: DatabricksSqlSessionLike;
  private _sessionPromise?: Promise<DatabricksSqlSessionLike>;
  private _initPromise?: Promise<void>;

  constructor(config: DatabricksConfig) {
    const { host, workspaceUrl } = extractHostAndWorkspaceUrl(config);

    this.host = host;
    this.workspaceUrl = workspaceUrl;
    this.httpPath = config.httpPath;
    this.accessToken = config.accessToken;
    this.clientId = config.clientId;
    this.clientSecret = config.clientSecret;
    this.endpointName = config.endpointName || "mem0_vector_search";
    this.endpointType = config.endpointType || "STANDARD";
    this.pipelineType = config.pipelineType || "TRIGGERED";
    this.queryType = config.queryType || "ANN";
    this.dimension = config.embeddingModelDims || config.dimension || 1536;
    this.catalog = validateIdentifier(config.catalog || "main", "catalog");
    this.schema = validateIdentifier(config.schema || "default", "schema");
    this.indexName = validateIdentifier(
      config.collectionName || "mem0",
      "collectionName",
    );
    this.tableName = validateIdentifier(
      config.tableName || this.indexName,
      "tableName",
    );
    this.fullTableName = `${this.catalog}.${this.schema}.${this.tableName}`;
    this.fullIndexName = `${this.catalog}.${this.schema}.${this.indexName}`;
    this.sqlClient = config.sqlClient || new DBSQLClient();
    this.httpClient = config.httpClient || this.createHttpClient();

    if (
      this.endpointType === "STORAGE_OPTIMIZED" &&
      this.pipelineType !== "TRIGGERED"
    ) {
      throw new Error(
        "Databricks storage-optimized endpoints only support TRIGGERED pipelineType.",
      );
    }

    this.initialize().catch(console.error);
  }

  async initialize(): Promise<void> {
    if (!this._initPromise) {
      this._initPromise = this._doInitialize();
    }
    return this._initPromise;
  }

  private async _doInitialize(): Promise<void> {
    await this.executeSql(
      `CREATE SCHEMA IF NOT EXISTS ${this.catalog}.${this.schema}`,
    );
    await this.executeSql(`
      CREATE TABLE IF NOT EXISTS ${this.fullTableName} (
        memory_id STRING,
        embedding ARRAY<FLOAT>,
        payload STRING,
        user_id STRING,
        agent_id STRING,
        run_id STRING
      ) USING DELTA
      TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
    `);
    await this.ensureChangeDataFeedEnabled();
    await this.executeSql(`
      CREATE TABLE IF NOT EXISTS ${this.catalog}.${this.schema}.memory_migrations (
        user_id STRING
      ) USING DELTA
    `);

    await this.ensureEndpointExists();
    await this.ensureIndexExists();
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    await this.initialize();

    const values = vectors.map((vector, index) => {
      this.assertVectorDimension(vector, "Vector");
      const payload = payloads[index] || {};
      const sessionValues = this.extractSessionValues(payload);
      return `(
        ${formatSqlValue(ids[index])},
        ${formatSqlValue(vector)},
        ${formatSqlValue(JSON.stringify(payload))},
        ${formatSqlValue(sessionValues.user_id)},
        ${formatSqlValue(sessionValues.agent_id)},
        ${formatSqlValue(sessionValues.run_id)}
      )`;
    });

    await this.executeSql(`
      INSERT INTO ${this.fullTableName}
        (memory_id, embedding, payload, user_id, agent_id, run_id)
      VALUES ${values.join(", ")}
    `);
    await this.syncIndexIfTriggered();
  }

  async search(
    query: number[],
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    await this.initialize();
    this.assertVectorDimension(query, "Query");

    if (this.queryType === "HYBRID") {
      throw new Error(
        "Databricks HYBRID search requires query_text, but search() only receives query vectors.",
      );
    }

    const requestFilters = buildDatabricksServerFilters(
      this.endpointType,
      filters,
    );

    const response = await this.httpClient.post(
      `/indexes/${encodeURIComponent(this.fullIndexName)}/query`,
      {
        columns: ["memory_id", "payload"],
        num_results: Math.max(topK, DEFAULT_PAGE_SIZE),
        query_type: this.queryType,
        query_vector: query,
        ...requestFilters,
      },
    );

    return this.normalizeQueryResults(
      response.data,
      ["memory_id", "payload"],
      filters,
      topK,
    );
  }

  async keywordSearch(
    query: string,
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[] | null> {
    await this.initialize();
    const requestFilters = buildDatabricksServerFilters(
      this.endpointType,
      filters,
    );

    const response = await this.httpClient.post(
      `/indexes/${encodeURIComponent(this.fullIndexName)}/query`,
      {
        columns: ["memory_id", "payload"],
        num_results: Math.max(topK, DEFAULT_PAGE_SIZE),
        query_type: "FULL_TEXT",
        query_text: query,
        ...requestFilters,
      },
    );

    return this.normalizeQueryResults(
      response.data,
      ["memory_id", "payload"],
      filters,
      topK,
    );
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    await this.initialize();

    const rows = await this.executeSql(`
      SELECT memory_id, payload
      FROM ${this.fullTableName}
      WHERE memory_id = ${formatSqlValue(vectorId)}
      LIMIT 1
    `);
    const row = rows[0];

    if (!row) {
      return null;
    }

    return {
      id: String(extractRowValue(row, ["memory_id"]) || vectorId),
      payload: this.parsePayload(extractRowValue(row, ["payload"])),
    };
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    await this.initialize();
    this.assertVectorDimension(vector, "Vector");

    const sessionValues = this.extractSessionValues(payload || {});
    await this.executeSql(`
      UPDATE ${this.fullTableName}
      SET embedding = ${formatSqlValue(vector)},
          payload = ${formatSqlValue(JSON.stringify(payload || {}))},
          user_id = ${formatSqlValue(sessionValues.user_id)},
          agent_id = ${formatSqlValue(sessionValues.agent_id)},
          run_id = ${formatSqlValue(sessionValues.run_id)}
      WHERE memory_id = ${formatSqlValue(vectorId)}
    `);
    await this.syncIndexIfTriggered();
  }

  async delete(vectorId: string): Promise<void> {
    await this.initialize();

    await this.executeSql(`
      DELETE FROM ${this.fullTableName}
      WHERE memory_id = ${formatSqlValue(vectorId)}
    `);
    await this.syncIndexIfTriggered();
  }

  async deleteCol(): Promise<void> {
    await this.initialize();

    try {
      await this.httpClient.delete(
        `/indexes/${encodeURIComponent(this.fullIndexName)}`,
      );
    } catch (error: any) {
      if (error?.response?.status !== 404) {
        throw error;
      }
    }

    await this.executeSql(`DROP TABLE IF EXISTS ${this.fullTableName}`);
  }

  async list(
    filters?: SearchFilters,
    topK: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    await this.initialize();

    const rows = await this.executeSql(`
      SELECT memory_id, payload
      FROM ${this.fullTableName}
    `);
    const results: VectorStoreResult[] = [];

    for (const row of rows) {
      const item: DatabricksVector = {
        id: String(extractRowValue(row, ["memory_id"])),
        payload: this.parsePayload(extractRowValue(row, ["payload"])),
      };
      if (!this.filterVector(item, filters)) {
        continue;
      }
      results.push({
        id: item.id,
        payload: item.payload,
      });
    }

    return [results.slice(0, topK), results.length];
  }

  async getUserId(): Promise<string> {
    await this.initialize();

    const rows = await this.executeSql(`
      SELECT user_id
      FROM ${this.catalog}.${this.schema}.memory_migrations
      LIMIT 1
    `);
    const existing = rows[0]
      ? extractRowValue(rows[0], ["user_id"])
      : undefined;

    if (typeof existing === "string" && existing.length > 0) {
      return existing;
    }

    const userId =
      Math.random().toString(36).substring(2, 15) +
      Math.random().toString(36).substring(2, 15);
    await this.setUserId(userId);
    return userId;
  }

  async setUserId(userId: string): Promise<void> {
    await this.initialize();

    await this.executeSql(
      `DELETE FROM ${this.catalog}.${this.schema}.memory_migrations`,
    );
    await this.executeSql(`
      INSERT INTO ${this.catalog}.${this.schema}.memory_migrations (user_id)
      VALUES (${formatSqlValue(userId)})
    `);
  }

  private async ensureEndpointExists(): Promise<void> {
    try {
      await this.httpClient.get(
        `/endpoints/${encodeURIComponent(this.endpointName)}`,
      );
    } catch (error: any) {
      if (error?.response?.status !== 404) {
        throw error;
      }

      await this.httpClient.post("/endpoints", {
        name: this.endpointName,
        endpoint_type: this.endpointType,
      });
    }
  }

  private async ensureIndexExists(): Promise<void> {
    try {
      await this.httpClient.get(
        `/indexes/${encodeURIComponent(this.fullIndexName)}`,
      );
    } catch (error: any) {
      if (error?.response?.status !== 404) {
        throw error;
      }

      await this.httpClient.post("/indexes", {
        name: this.fullIndexName,
        endpoint_name: this.endpointName,
        primary_key: "memory_id",
        index_type: "DELTA_SYNC",
        delta_sync_index_spec: {
          source_table: this.fullTableName,
          pipeline_type: this.pipelineType,
          columns_to_sync:
            this.endpointType === "STANDARD"
              ? ["memory_id", "payload", "user_id", "agent_id", "run_id"]
              : undefined,
          embedding_vector_columns: [
            {
              name: "embedding",
              embedding_dimension: this.dimension,
            },
          ],
        },
      });
    }
  }

  private async ensureChangeDataFeedEnabled(): Promise<void> {
    if (this.endpointType !== "STANDARD") {
      return;
    }

    await this.executeSql(`
      ALTER TABLE ${this.fullTableName}
      SET TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
    `);
  }

  private createHttpClient(): AxiosInstance {
    if (!this.accessToken) {
      throw new Error(
        "Databricks vector store requires accessToken when httpClient is not provided.",
      );
    }

    return axios.create({
      baseURL: `${this.workspaceUrl}/api/2.0/vector-search`,
      headers: {
        Authorization: `Bearer ${this.accessToken}`,
      },
    });
  }

  private async getSession(): Promise<DatabricksSqlSessionLike> {
    if (this.session) {
      return this.session;
    }

    if (!this._sessionPromise) {
      this._sessionPromise = this.openSession();
    }

    this.session = await this._sessionPromise;
    return this.session;
  }

  private async openSession(): Promise<DatabricksSqlSessionLike> {
    const connected = await this.sqlClient.connect(
      this.buildSqlConnectionOptions(),
    );
    return connected.openSession();
  }

  private buildSqlConnectionOptions(): Record<string, any> {
    const base = {
      host: this.host,
      path: this.httpPath,
    } as Record<string, any>;

    if (this.clientId && this.clientSecret) {
      return {
        ...base,
        authType: "databricks-oauth",
        oauthClientId: this.clientId,
        oauthClientSecret: this.clientSecret,
      };
    }

    if (!this.accessToken) {
      throw new Error(
        "Databricks vector store requires accessToken or clientId/clientSecret for SQL connections.",
      );
    }

    return {
      ...base,
      token: this.accessToken,
    };
  }

  private async executeSql(
    statement: string,
  ): Promise<Array<Record<string, any>>> {
    const session = await this.getSession();
    const operation = await session.executeStatement(statement);
    try {
      return await operation.fetchAll();
    } finally {
      if (typeof operation.close === "function") {
        await operation.close();
      }
    }
  }

  private async syncIndexIfTriggered(): Promise<void> {
    if (this.pipelineType !== "TRIGGERED") {
      return;
    }

    await this.httpClient.post(
      `/indexes/${encodeURIComponent(this.fullIndexName)}/sync`,
    );
  }

  private normalizeQueryResults(
    responseData: any,
    fallbackColumns: string[],
    filters: SearchFilters | undefined,
    topK: number,
  ): VectorStoreResult[] {
    const resultData = responseData?.result || responseData;
    const dataArray = Array.isArray(resultData?.data_array)
      ? resultData.data_array
      : [];
    const manifestColumns = Array.isArray(resultData?.manifest?.columns)
      ? resultData.manifest.columns.map((column: any) =>
          typeof column === "string" ? column : column.name,
        )
      : fallbackColumns;
    const results: VectorStoreResult[] = [];

    for (const row of dataArray) {
      const rowDict = this.rowToObject(row, manifestColumns);
      const item: DatabricksVector = {
        id: String(rowDict.memory_id || rowDict.id || rowDict.vector_id),
        payload: this.parsePayload(rowDict.payload),
      };
      if (!this.filterVector(item, filters)) {
        continue;
      }
      const rawScore =
        rowDict.score ??
        (Array.isArray(row) && row.length > manifestColumns.length
          ? row[row.length - 1]
          : undefined);
      results.push({
        id: item.id,
        payload: item.payload,
        score:
          rawScore === undefined || rawScore === null
            ? undefined
            : Number(rawScore),
      });
    }

    return results.slice(0, topK);
  }

  private rowToObject(row: any, columns: string[]): Record<string, any> {
    if (!Array.isArray(row)) {
      return row || {};
    }

    return Object.fromEntries(
      columns.map((column, index) => [column, row[index]]),
    );
  }

  private parsePayload(rawValue: any): Record<string, any> {
    if (typeof rawValue === "string") {
      try {
        const parsed = JSON.parse(rawValue);
        if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
          return parsed;
        }
      } catch {
        return {};
      }
    }

    if (rawValue && typeof rawValue === "object" && !Array.isArray(rawValue)) {
      return rawValue;
    }

    return {};
  }

  private extractSessionValues(payload: Record<string, any>): {
    user_id: any;
    agent_id: any;
    run_id: any;
  } {
    return {
      user_id: payload.user_id,
      agent_id: payload.agent_id,
      run_id: payload.run_id,
    };
  }

  private assertVectorDimension(vector: number[], label: string): void {
    if (vector.length !== this.dimension) {
      throw new Error(
        `${label} dimension mismatch. Expected ${this.dimension}, got ${vector.length}`,
      );
    }
    for (const value of vector) {
      if (!Number.isFinite(value)) {
        throw new Error(
          `${label} values must be finite numbers for Databricks vector search.`,
        );
      }
    }
  }

  private matchFieldCondition(
    payload: Record<string, any>,
    key: string,
    value: any,
  ): boolean {
    const payloadValue = payload[key];

    if (typeof value !== "object" || value === null) {
      if (value === "*") {
        return true;
      }
      return payloadValue === value;
    }

    if (Array.isArray(value)) {
      return value.includes(payloadValue);
    }

    if ("eq" in value) {
      return payloadValue === value.eq;
    }
    if ("ne" in value) {
      return payloadValue !== value.ne;
    }
    if ("gt" in value) {
      return payloadValue > value.gt;
    }
    if ("gte" in value) {
      return payloadValue >= value.gte;
    }
    if ("lt" in value) {
      return payloadValue < value.lt;
    }
    if ("lte" in value) {
      return payloadValue <= value.lte;
    }
    if ("in" in value) {
      return Array.isArray(value.in) && value.in.includes(payloadValue);
    }
    if ("nin" in value) {
      return !Array.isArray(value.nin) || !value.nin.includes(payloadValue);
    }
    if ("contains" in value) {
      return (
        typeof payloadValue === "string" &&
        payloadValue.includes(value.contains)
      );
    }
    if ("icontains" in value) {
      return (
        typeof payloadValue === "string" &&
        payloadValue.toLowerCase().includes(value.icontains.toLowerCase())
      );
    }

    return payloadValue === value;
  }

  private filterVector(
    vector: DatabricksVector,
    filters?: SearchFilters,
  ): boolean {
    if (!filters || Object.keys(filters).length === 0) {
      return true;
    }

    const keyMap: Record<string, string> = {
      $and: "AND",
      $or: "OR",
      $not: "NOT",
    };
    const normalized: Record<string, any> = {};
    for (const [key, value] of Object.entries(filters)) {
      const normalizedKey = keyMap[key] || key;
      if (!(normalizedKey in normalized)) {
        normalized[normalizedKey] = value;
      }
    }

    for (const [key, value] of Object.entries(normalized)) {
      if (key === "AND") {
        if (!Array.isArray(value)) {
          throw new Error(
            `AND filter value must be a list of filter dicts, got ${typeof value}`,
          );
        }
        if (
          !value.every((entry: SearchFilters) =>
            this.filterVector(vector, entry),
          )
        ) {
          return false;
        }
      } else if (key === "OR") {
        if (!Array.isArray(value)) {
          throw new Error(
            `OR filter value must be a list of filter dicts, got ${typeof value}`,
          );
        }
        if (
          !value.some((entry: SearchFilters) =>
            this.filterVector(vector, entry),
          )
        ) {
          return false;
        }
      } else if (key === "NOT") {
        if (!Array.isArray(value)) {
          throw new Error(
            `NOT filter value must be a list of filter dicts, got ${typeof value}`,
          );
        }
        if (
          !value.every(
            (entry: SearchFilters) => !this.filterVector(vector, entry),
          )
        ) {
          return false;
        }
      } else if (!this.matchFieldCondition(vector.payload, key, value)) {
        return false;
      }
    }

    return true;
  }
}
