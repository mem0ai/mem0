import type {
  BaiduClient as BaiduSdkClient,
  BaiduConfigurationOptions,
  BaiduDatabase as BaiduSdkDatabase,
  BaiduRow,
  BaiduSearchEnvelope,
  BaiduSearchItem,
  BaiduSdkModule as BaiduSdkModuleType,
  BaiduTable as BaiduSdkTable,
} from "@baiducloud/sdk";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

export interface BaiduConfig extends VectorStoreConfig {
  endpoint: string;
  account: string;
  apiKey: string;
  databaseName: string;
  tableName: string;
  embeddingModelDims: number;
  metricType?: string;
}

type BaiduClient = BaiduSdkClient;
type BaiduDatabase = BaiduSdkDatabase;
type BaiduTable = BaiduSdkTable;
type BaiduSdkModule = BaiduSdkModuleType & { default?: BaiduSdkModuleType };
type BaiduSearchResult =
  | BaiduSearchEnvelope
  | BaiduSearchItem[]
  | null
  | undefined;

const SAFE_FILTER_KEY = /^[a-zA-Z_][a-zA-Z0-9_]*$/;

function escapeFilterString(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

function isAlreadyExistsError(error: unknown): boolean {
  if (typeof error !== "object" || error === null) {
    return false;
  }

  const err = error as { code?: unknown; status?: unknown; message?: unknown };
  return (
    err.code === 409 ||
    err.status === 409 ||
    (typeof err.message === "string" &&
      /already exists|exists/i.test(err.message))
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function toRow(value: unknown): BaiduRow | null {
  if (!isRecord(value) || typeof value.id !== "string") {
    return null;
  }

  return value as BaiduRow;
}

function firstRow(result: BaiduSearchResult): BaiduRow | null {
  if (!result) {
    return null;
  }

  if (Array.isArray(result)) {
    return result.length > 0 ? toRow(result[0].row ?? result[0]) : null;
  }

  if (result.row) {
    return toRow(result.row);
  }

  const rows = result.rows ?? result.points ?? result.items ?? result.data;
  if (Array.isArray(rows) && rows.length > 0) {
    return toRow(rows[0].row ?? rows[0]);
  }

  return null;
}

function normalizeRows(result: BaiduSearchResult): BaiduSearchItem[] {
  if (!result) {
    return [];
  }

  if (Array.isArray(result)) {
    return result;
  }

  const rows = result.rows ?? result.points ?? result.items ?? result.data;
  return Array.isArray(rows) ? rows : [];
}

function isOptionalTextField(value: unknown, fieldName: string): boolean {
  return (
    isRecord(value) &&
    value.name === fieldName &&
    (value.type === "TEXT" ||
      value.type === "TEXT_GBK" ||
      value.type === "TEXT_GB18030")
  );
}

function buildSearchTextFields(payload: Record<string, any>): {
  data: string;
  textLemmatized: string;
} {
  const data = typeof payload.data === "string" ? payload.data : "";
  const textLemmatized =
    typeof payload.textLemmatized === "string" &&
    payload.textLemmatized.length > 0
      ? payload.textLemmatized
      : data;

  return { data, textLemmatized };
}

function isUnsupportedKeywordSearchError(error: unknown): boolean {
  if (typeof error !== "object" || error === null) {
    return false;
  }

  const err = error as { code?: unknown; status?: unknown; message?: unknown };
  const message = typeof err.message === "string" ? err.message : "";

  return (
    err.code === 400 ||
    err.status === 400 ||
    /bm25|inverted index|keyword search|search unavailable|not supported/i.test(
      message,
    )
  );
}

function hasMethod<T extends (...args: any[]) => unknown>(
  target: unknown,
  methodName: string,
): target is Record<string, T> {
  return isRecord(target) && typeof target[methodName] === "function";
}

function getMethod<T extends (...args: any[]) => unknown>(
  target: unknown,
  methodNames: readonly string[],
): T {
  for (const methodName of methodNames) {
    if (hasMethod<T>(target, methodName)) {
      return target[methodName];
    }
  }

  throw new Error(
    `Baidu SDK is missing expected method(s): ${methodNames.join(", ")}`,
  );
}

export class BaiduDB implements VectorStore {
  private client: BaiduClient | null = null;
  private database: BaiduDatabase | null = null;
  private table: BaiduTable | null = null;
  private readonly endpoint: string;
  private readonly account: string;
  private readonly apiKey: string;
  private readonly databaseName: string;
  private readonly tableName: string;
  private readonly embeddingModelDims: number;
  private readonly metricType: string;
  private storeUserId = "anonymous-baidu-user";
  private _initPromise?: Promise<void>;

  constructor(config: BaiduConfig) {
    this.endpoint = config.endpoint;
    this.account = config.account;
    this.apiKey = config.apiKey;
    this.databaseName = config.databaseName;
    this.tableName = config.tableName;
    this.embeddingModelDims = config.embeddingModelDims;
    this.metricType = config.metricType || "COSINE";
    this.client = config.client || null;

    const requiredFields: Array<
      readonly [string, string | number | undefined]
    > = [
      ["databaseName", this.databaseName],
      ["tableName", this.tableName],
      ["embeddingModelDims", this.embeddingModelDims],
    ];

    if (!this.client) {
      requiredFields.unshift(
        ["endpoint", this.endpoint],
        ["account", this.account],
        ["apiKey", this.apiKey],
      );
    }

    for (const [name, value] of requiredFields) {
      if (value === undefined || value === null || value === "") {
        throw new Error(
          `Baidu vector store requires a non-empty '${name}' config value.`,
        );
      }
    }

    this.initialize().catch(console.error);
  }

  private async loadSdkClient(): Promise<BaiduClient> {
    const sdkModule = (await import("@baiducloud/sdk")) as BaiduSdkModule;
    // Baidu's SDK surface has shipped in multiple export shapes, so accept both
    // the direct module and a default wrapper.
    const sdk = sdkModule.default ?? sdkModule;
    const Configuration = sdk.Configuration ?? sdk.configuration;
    const BceCredentials = sdk.BceCredentials ?? sdk.bceCredentials;
    const MochowClient = sdk.MochowClient ?? sdk.mochowClient;

    if (!Configuration || !BceCredentials || !MochowClient) {
      throw new Error(
        "The @baiducloud/sdk package does not expose the expected Mochow client exports.",
      );
    }

    const credentials = new BceCredentials(this.account, this.apiKey);
    const sdkConfig: BaiduConfigurationOptions = {
      credentials,
      endpoint: this.endpoint,
    };
    const configuration = new Configuration(sdkConfig);
    return new MochowClient(configuration);
  }

  private async ensureClient(): Promise<BaiduClient> {
    if (!this.client) {
      this.client = await this.loadSdkClient();
    }
    return this.client;
  }

  private async createDatabase(client: BaiduClient): Promise<BaiduDatabase> {
    const method = getMethod<(name: string) => Promise<BaiduDatabase>>(client, [
      "createDatabase",
      "create_database",
    ]);
    return method.call(client, this.databaseName);
  }

  private async getDatabase(client: BaiduClient): Promise<BaiduDatabase> {
    const method = getMethod<(name: string) => BaiduDatabase>(client, [
      "database",
    ]);
    return method.call(client, this.databaseName);
  }

  private async createTable(database: BaiduDatabase): Promise<BaiduTable> {
    const method = getMethod<
      (spec: Record<string, unknown>) => Promise<BaiduTable>
    >(database, ["createTable", "create_table"]);
    return method.call(database, this.buildTableSpec());
  }

  private async getExistingTable(database: BaiduDatabase): Promise<BaiduTable> {
    const method = getMethod<(tableName: string) => Promise<BaiduTable>>(
      database,
      ["describeTable", "describe_table", "table"],
    );
    return method.call(database, this.tableName);
  }

  private async dropTable(database: BaiduDatabase): Promise<void> {
    const method = getMethod<(tableName: string) => Promise<unknown>>(
      database,
      ["dropTable", "drop_table"],
    );
    await method.call(database, this.tableName);
  }

  private async vectorSearch(
    table: BaiduTable,
    query: number[],
    topK: number,
    filter?: string,
  ): Promise<BaiduSearchResult> {
    const method = getMethod<
      (payload: {
        vectorField: string;
        vector_field: string;
        vector: number[];
        limit: number;
        filter?: string;
        config: { ef: number };
      }) => Promise<BaiduSearchResult>
    >(table, ["vectorSearch", "vector_search"]);
    return method.call(table, {
      vectorField: "vector",
      vector_field: "vector",
      vector: query,
      limit: topK,
      filter,
      config: { ef: 200 },
    });
  }

  private async keywordSearchRows(
    table: BaiduTable,
    query: string,
    topK: number,
    filter?: string,
  ): Promise<BaiduSearchResult> {
    // Best-effort BM25 lookup; if the backend does not support this shape, the
    // public keywordSearch() path will fall back to the warning/null branch.
    const method = getMethod<
      (payload: {
        indexName: string;
        index_name: string;
        searchText: string;
        search_text: string;
        limit: number;
        filter?: string;
      }) => Promise<BaiduSearchResult>
    >(table, ["bm25Search", "bm25_search"]);
    return method.call(table, {
      indexName: "data_bm25_idx",
      index_name: "data_bm25_idx",
      searchText: query,
      search_text: query,
      limit: topK,
      filter,
    });
  }

  private async selectRows(
    table: BaiduTable,
    filter?: string,
    topK = 100,
  ): Promise<BaiduSearchResult> {
    const method = getMethod<
      (payload: {
        filter?: string;
        projections: string[];
        limit: number;
      }) => Promise<BaiduSearchEnvelope>
    >(table, ["select"]);
    return method.call(table, {
      filter,
      projections: ["id", "metadata"],
      limit: topK,
    });
  }

  private buildTableSpec(): Record<string, unknown> {
    // Emit both camelCase and snake_case keys because the Mochow SDK surface is
    // inconsistent across versions and environments.
    return {
      tableName: this.tableName,
      table_name: this.tableName,
      replication: 3,
      partition: { partitionNum: 1, partition_num: 1 },
      schema: {
        fields: [
          {
            name: "id",
            type: "STRING",
            primaryKey: true,
            primary_key: true,
            partitionKey: true,
            partition_key: true,
            autoIncrement: false,
            auto_increment: false,
            notNull: true,
            not_null: true,
          },
          {
            name: "vector",
            type: "FLOAT_VECTOR",
            dimension: this.embeddingModelDims,
          },
          {
            name: "data",
            type: "TEXT",
          },
          {
            name: "textLemmatized",
            type: "TEXT",
          },
          {
            name: "metadata",
            type: "JSON",
          },
        ],
        indexes: [
          {
            indexName: "vector_idx",
            index_name: "vector_idx",
            indexType: "HNSW",
            index_type: "HNSW",
            field: "vector",
            metricType: this.metricType,
            metric_type: this.metricType,
            params: {
              m: 16,
              efConstruction: 200,
              ef_construction: 200,
            },
            autoBuild: true,
            auto_build: true,
            autoBuildIndexPolicy: {
              rowCountIncrement: 10000,
              row_count_increment: 10000,
            },
            auto_build_index_policy: {
              rowCountIncrement: 10000,
              row_count_increment: 10000,
            },
          },
          {
            indexName: "metadata_filtering_idx",
            index_name: "metadata_filtering_idx",
            fields: ["metadata"],
          },
          {
            indexName: "data_bm25_idx",
            index_name: "data_bm25_idx",
            indexType: "INVERTED",
            index_type: "INVERTED",
            fields: ["data", "textLemmatized"],
          },
        ],
      },
    };
  }

  private buildFilter(filters: SearchFilters): string {
    const conditions: string[] = [];

    for (const [key, value] of Object.entries(filters)) {
      if (!SAFE_FILTER_KEY.test(key)) {
        throw new Error(`Invalid filter key: ${key}`);
      }

      if (typeof value === "string") {
        conditions.push(`metadata["${key}"] = "${escapeFilterString(value)}"`);
        continue;
      }

      if (typeof value === "number" || typeof value === "boolean") {
        conditions.push(`metadata["${key}"] = ${value}`);
        continue;
      }

      throw new Error(
        `Filter value for ${key} must be str, int, float, or bool, got ${Array.isArray(value) ? "array" : typeof value}`,
      );
    }

    return conditions.join(" AND ");
  }

  private async ensureDatabase(): Promise<BaiduDatabase> {
    if (this.database) {
      return this.database;
    }

    const client = await this.ensureClient();
    try {
      this.database = await this.createDatabase(client);
    } catch (error) {
      if (!isAlreadyExistsError(error)) {
        throw error;
      }
      this.database = await this.getDatabase(client);
    }

    return this.database;
  }

  private async ensureTable(): Promise<BaiduTable> {
    if (this.table) {
      return this.table;
    }

    const database = await this.ensureDatabase();

    try {
      this.table = await this.createTable(database);
    } catch (error) {
      if (!isAlreadyExistsError(error)) {
        throw error;
      }
      this.table = await this.getExistingTable(database);
    }

    if (!this.table) {
      this.table = await this.getExistingTable(database);
    }

    await this.validateExistingTableSchema(this.table);

    return this.table;
  }

  private async validateExistingTableSchema(table: BaiduTable): Promise<void> {
    const statsMethod = getMethod<() => Promise<unknown> | unknown>(table, [
      "stats",
    ]);
    const stats = await statsMethod.call(table);

    if (!isRecord(stats) || !isRecord(stats.schema)) {
      return;
    }

    const fields = Array.isArray(stats.schema.fields)
      ? stats.schema.fields
      : [];
    const indexes = Array.isArray(stats.schema.indexes)
      ? stats.schema.indexes
      : [];

    const hasDataField = fields.some((field) =>
      isOptionalTextField(field, "data"),
    );
    const hasTextLemmatizedField = fields.some((field) =>
      isOptionalTextField(field, "textLemmatized"),
    );
    const hasBm25Index = indexes.some(
      (index) =>
        isRecord(index) &&
        (index.indexName === "data_bm25_idx" ||
          index.index_name === "data_bm25_idx"),
    );

    if (!hasDataField || !hasTextLemmatizedField || !hasBm25Index) {
      throw new Error(
        "Baidu table exists but is missing the BM25 text fields or inverted index. Recreate the table so keywordSearch() can work.",
      );
    }
  }

  async initialize(): Promise<void> {
    if (!this._initPromise) {
      this._initPromise = this.ensureTable().then(() => undefined);
    }

    return this._initPromise;
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    const table = await this.ensureTable();

    for (const [index, vector] of vectors.entries()) {
      await table.upsert({
        rows: [
          {
            id: ids[index],
            vector,
            ...buildSearchTextFields(payloads[index] || {}),
            metadata: payloads[index] || {},
          },
        ],
      });
    }
  }

  async keywordSearch(
    query: string,
    topK = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[] | null> {
    try {
      const table = await this.ensureTable();
      const filter =
        filters && Object.keys(filters).length > 0
          ? this.buildFilter(filters)
          : undefined;
      const result = await this.keywordSearchRows(table, query, topK, filter);

      return normalizeRows(result).map((row) => ({
        id: String(firstRow(row)?.id ?? row.id),
        payload: firstRow(row)?.metadata ?? row.metadata ?? {},
        score: row.score,
      }));
    } catch (error) {
      if (!isUnsupportedKeywordSearchError(error)) {
        throw error;
      }

      console.warn(`Baidu keyword search failed for query '${query}':`, error);
      return null;
    }
  }

  async search(
    query: number[],
    topK = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    const table = await this.ensureTable();
    const filter =
      filters && Object.keys(filters).length > 0
        ? this.buildFilter(filters)
        : undefined;
    const result = await this.vectorSearch(table, query, topK, filter);

    return normalizeRows(result).map((row) => {
      const rowData = firstRow(row) ?? row;
      return {
        id: String(rowData.id),
        payload: rowData.metadata || {},
        score: row.score,
      };
    });
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    const table = await this.ensureTable();
    const result = await table.query({
      primaryKey: { id: vectorId },
      primary_key: { id: vectorId },
      projections: ["id", "metadata"],
    });

    const row = firstRow(result);
    if (!row) {
      return null;
    }

    return {
      id: String(row.id ?? vectorId),
      payload: row.metadata || {},
    };
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    const table = await this.ensureTable();
    await table.upsert({
      rows: [
        {
          id: vectorId,
          vector,
          ...buildSearchTextFields(payload),
          metadata: payload,
        },
      ],
    });
  }

  async delete(vectorId: string): Promise<void> {
    const table = await this.ensureTable();
    await table.delete({
      primaryKey: { id: vectorId },
      primary_key: { id: vectorId },
    });
  }

  async deleteCol(): Promise<void> {
    const database = await this.ensureDatabase();
    await this.dropTable(database);
    this.table = null;
  }

  async reset(): Promise<void> {
    await this.deleteCol();
    await this.ensureTable();
  }

  async list(
    filters?: SearchFilters,
    topK = 100,
  ): Promise<[VectorStoreResult[], number]> {
    const table = await this.ensureTable();
    const filter =
      filters && Object.keys(filters).length > 0
        ? this.buildFilter(filters)
        : undefined;
    const result = await this.selectRows(table, filter, topK);

    const memories = normalizeRows(result).map((row) => {
      const rowData = firstRow(row) ?? row;
      return {
        id: String(rowData.id),
        payload: rowData.metadata || {},
      };
    });

    const total =
      isRecord(result) && typeof result.total === "number"
        ? result.total
        : memories.length;
    return [memories, total];
  }

  async getUserId(): Promise<string> {
    return this.storeUserId;
  }

  async setUserId(userId: string): Promise<void> {
    this.storeUserId = userId;
  }
}
