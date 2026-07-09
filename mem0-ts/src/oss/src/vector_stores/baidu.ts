import type {
  AutoBuildIncrementPolicy,
  CommonResponse,
  DescTableResponse,
  FieldType,
  IndexSchema,
  MochowClient,
  QueryResponse,
  SearchResponse,
  SelectResponse,
  TableSchema,
} from "@mochow/mochow-sdk-node";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

type MochowSdk = typeof import("@mochow/mochow-sdk-node");

export interface BaiduConfig extends VectorStoreConfig {
  endpoint: string;
  account: string;
  apiKey: string;
  databaseName: string;
  tableName: string;
  embeddingModelDims: number;
  metricType?: "L2" | "IP" | "COSINE";
  client?: MochowClient;
}

const VECTOR_INDEX = "vector_idx";
const FILTERING_INDEX = "metadata_filtering_idx";
// Named after the column it actually indexes, and deliberately not Python's "data_bm25_idx".
// This index holds Porter-stemmed text, but mem0/vector_stores/baidu.py's keyword_search()
// sends a raw, unstemmed query to that name. Sharing it would let Python find an index whose
// contents it cannot match properly, silently returning degraded hits instead of None.
const BM25_INDEX = "text_lemmatized_bm25_idx";
const PROJECTIONS = ["id", "data", "metadata"];
const TABLE_POLL_INTERVAL_MS = 2000;
const TABLE_POLL_ATTEMPTS = 60;

// Mochow's server accepts JSON columns, but the Node SDK's FieldType enum predates them
// (pymochow 2.4.1 ships FieldType.JSON == "JSON"). The wire value is the bare string.
const JSON_FIELD_TYPE = "JSON" as unknown as FieldType;

// Querying a primary key that isn't there answers with this code, not an empty row. The Node
// SDK's ServerErrCode stops at 100, but its siblings against the same server name it:
// pymochow ROW_KEY_NOT_FOUND = 101, mochow-sdk-go RowKeyNotFound = 101.
const ROW_KEY_NOT_FOUND = 101;

const SAFE_FILTER_KEY = /^[a-zA-Z_][a-zA-Z0-9_]*$/;

function escapeFilterString(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Mochow resolves with a {code, msg} envelope instead of rejecting, so every call site
// has to inspect the code. `tolerated` lets callers accept the idempotent outcomes
// (database/table already exists, table already dropped).
function check(
  response: CommonResponse,
  action: string,
  ...tolerated: number[]
): number {
  if (response.code !== 0 && !tolerated.includes(response.code)) {
    throw new Error(
      `Baidu Mochow ${action} failed (code ${response.code}): ${response.msg}`,
    );
  }
  return response.code;
}

function lemmatizedText(payload: Record<string, any>): string {
  const data = typeof payload.data === "string" ? payload.data : "";
  return typeof payload.textLemmatized === "string" &&
    payload.textLemmatized.length > 0
    ? payload.textLemmatized
    : data;
}

function memoryData(payload: Record<string, any>): string {
  return typeof payload.data === "string" ? payload.data : "";
}

function metadataPayload(payload: Record<string, any>): Record<string, any> {
  const { data: _data, textLemmatized: _textLemmatized, ...metadata } = payload;
  return metadata;
}

function resultPayload(row: Record<string, any>): Record<string, any> {
  return {
    ...(row.metadata || {}),
    ...(typeof row.data === "string" ? { data: row.data } : {}),
  };
}

export class BaiduDB implements VectorStore {
  private client: MochowClient | null = null;
  private sdk: MochowSdk | null = null;
  private readonly endpoint: string;
  private readonly account: string;
  private readonly apiKey: string;
  private readonly databaseName: string;
  private readonly tableName: string;
  private readonly embeddingModelDims: number;
  private readonly metricType: "L2" | "IP" | "COSINE";
  // Fails closed: keyword search stays off until an inverted index is observed.
  private supportsKeywordSearch = false;
  private storeUserId = "anonymous-baidu-user";
  private _initPromise?: Promise<void>;

  constructor(config: BaiduConfig) {
    this.endpoint = config.endpoint;
    this.account = config.account;
    this.apiKey = config.apiKey;
    this.databaseName = config.databaseName;
    this.tableName = config.tableName;
    this.embeddingModelDims = config.embeddingModelDims;
    this.metricType = config.metricType || "L2";
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

  private get ns(): { database: string; table: string } {
    return { database: this.databaseName, table: this.tableName };
  }

  // Loaded dynamically: @mochow/mochow-sdk-node is an optional peer dependency, so a static
  // value import would break `import { Memory } from "mem0ai/oss"` for everyone else.
  private async loadSdk(): Promise<MochowSdk> {
    if (!this.sdk) {
      let module: MochowSdk & { default?: MochowSdk };
      try {
        module = await import("@mochow/mochow-sdk-node");
      } catch {
        throw new Error(
          "The Baidu vector store requires the '@mochow/mochow-sdk-node' package. Install it with: npm install @mochow/mochow-sdk-node",
        );
      }
      this.sdk = module.default ?? module;
    }
    return this.sdk;
  }

  private async ensureClient(): Promise<MochowClient> {
    if (!this.client) {
      const sdk = await this.loadSdk();
      this.client = new sdk.MochowClient({
        endpoint: this.endpoint,
        credential: { account: this.account, apiKey: this.apiKey },
      });
    }
    return this.client;
  }

  private async ready(): Promise<{ client: MochowClient; sdk: MochowSdk }> {
    await this.initialize();
    return { client: await this.ensureClient(), sdk: await this.loadSdk() };
  }

  private buildSchema(sdk: MochowSdk): TableSchema {
    const {
      AutoBuildPolicyType,
      FieldType,
      IndexType,
      InvertedIndexAnalyzer,
      InvertedIndexFieldAttribute,
      InvertedIndexParseMode,
      MetricType,
    } = sdk;

    // sdk.AutoBuildIncrement() stamps policyType "TIMING" (bug in 2.1.5), so build the
    // increment policy by hand.
    const autoBuildPolicy: AutoBuildIncrementPolicy = {
      policyType: AutoBuildPolicyType.Increment,
      rowCountIncrement: 10000,
    };

    const vectorIndex: IndexSchema = {
      indexName: VECTOR_INDEX,
      indexType: IndexType.HNSW,
      field: "vector",
      metricType: MetricType[this.metricType],
      params: { M: 16, efConstruction: 200 },
      autoBuild: true,
      autoBuildPolicy,
    };

    return {
      fields: [
        {
          fieldName: "id",
          fieldType: FieldType.String,
          primaryKey: true,
          partitionKey: true,
          autoIncrement: false,
          notNull: true,
        },
        {
          fieldName: "data",
          fieldType: FieldType.Text,
        },
        {
          fieldName: "vector",
          fieldType: FieldType.FloatVector,
          notNull: true,
          dimension: this.embeddingModelDims,
        },
        // Stored outside `metadata` because Mochow cannot build an inverted index on a
        // field inside a JSON column. Memory.search() passes an already-lemmatized query,
        // so only the lemmatized form is worth indexing.
        { fieldName: "textLemmatized", fieldType: FieldType.Text },
        { fieldName: "metadata", fieldType: JSON_FIELD_TYPE },
      ],
      indexes: [
        vectorIndex,
        {
          indexName: FILTERING_INDEX,
          indexType: IndexType.FilteringIndex,
          fields: ["metadata"],
        },
        {
          indexName: BM25_INDEX,
          indexType: IndexType.InvertedIndex,
          fields: ["textLemmatized"],
          fieldAttributes: [InvertedIndexFieldAttribute.Analyzed],
          params: {
            analyzer: InvertedIndexAnalyzer.EnglishAnalyzer,
            parseMode: InvertedIndexParseMode.FineMode,
          },
        },
      ],
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

  private filterOf(filters?: SearchFilters): string | undefined {
    return filters && Object.keys(filters).length > 0
      ? this.buildFilter(filters)
      : undefined;
  }

  private async pollTable(
    client: MochowClient,
    settled: (response: DescTableResponse) => boolean,
    what: string,
  ): Promise<void> {
    for (let attempt = 0; attempt < TABLE_POLL_ATTEMPTS; attempt++) {
      if (settled(await client.descTable(this.databaseName, this.tableName))) {
        return;
      }
      await sleep(TABLE_POLL_INTERVAL_MS);
    }

    throw new Error(
      `Baidu Mochow table '${this.tableName}' was not ${what} after ${(TABLE_POLL_ATTEMPTS * TABLE_POLL_INTERVAL_MS) / 1000}s.`,
    );
  }

  private async ensureTable(): Promise<void> {
    const sdk = await this.loadSdk();
    const client = await this.ensureClient();
    const { ServerErrCode, TableState } = sdk;

    check(
      await client.createDatabase(this.databaseName),
      `createDatabase '${this.databaseName}'`,
      ServerErrCode.DBAlreadyExist,
    );

    const created = check(
      await client.createTable({
        ...this.ns,
        description: "mem0 memories",
        replication: 3,
        partition: { partitionType: sdk.PartitionType.HASH, partitionNum: 1 },
        enableDynamicField: false,
        schema: this.buildSchema(sdk),
      }),
      `createTable '${this.tableName}'`,
      ServerErrCode.TableAlreadyExist,
    );

    // A table is CREATING until its indexes are built; writing to it before then fails.
    let description: DescTableResponse | undefined;
    await this.pollTable(
      client,
      (response) => {
        check(response, `descTable '${this.tableName}'`);
        description = response;
        return response.table.state === TableState.Normal;
      },
      "ready",
    );

    this.applySchema(
      created === ServerErrCode.TableAlreadyExist,
      description!.table.schema,
    );
  }

  private applySchema(preexisting: boolean, schema: TableSchema): void {
    if (!preexisting) {
      this.supportsKeywordSearch = true;
      return;
    }

    const fields = schema?.fields ?? [];
    const indexes = schema?.indexes ?? [];
    const field = (name: string) => fields.find((f) => f.fieldName === name);
    const typeOf = (name: string) => String(field(name)?.fieldType ?? "");
    const label = `${this.databaseName}.${this.tableName}`;

    if (
      typeOf("id") !== "STRING" ||
      !typeOf("data").startsWith("TEXT") ||
      typeOf("vector") !== "FLOAT_VECTOR" ||
      typeOf("metadata") !== "JSON"
    ) {
      throw new Error(
        `Baidu Mochow table '${label}' exists but is missing the id/data/vector/metadata schema mem0 requires. Drop it, or point 'tableName' at an unused table.`,
      );
    }

    const dimension = field("vector")?.dimension;
    if (dimension !== undefined && dimension !== this.embeddingModelDims) {
      throw new Error(
        `Baidu Mochow table '${label}' stores ${dimension}-dimensional vectors, but 'embeddingModelDims' is ${this.embeddingModelDims}.`,
      );
    }

    this.supportsKeywordSearch =
      typeOf("textLemmatized").startsWith("TEXT") &&
      indexes.some((index) => index.indexName === BM25_INDEX);

    if (!this.supportsKeywordSearch) {
      console.warn(
        `Baidu Mochow table '${label}' has no '${BM25_INDEX}' inverted index. keywordSearch() will return null until the table is recreated.`,
      );
    }
  }

  async initialize(): Promise<void> {
    if (!this._initPromise) {
      this._initPromise = this.ensureTable().catch((error) => {
        this._initPromise = undefined;
        throw error;
      });
    }

    return this._initPromise;
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    const { client } = await this.ready();

    if (vectors.length !== ids.length || vectors.length !== payloads.length) {
      throw new Error(
        `Baidu insert requires vectors, ids, and payloads of equal length (got ${vectors.length}/${ids.length}/${payloads.length}).`,
      );
    }

    const rows = vectors.map((vector, index) => ({
      id: ids[index],
      data: memoryData(payloads[index] || {}),
      vector,
      textLemmatized: lemmatizedText(payloads[index] || {}),
      metadata: metadataPayload(payloads[index] || {}),
    }));

    check(await client.upsert({ ...this.ns, rows }), "upsert");
  }

  async search(
    query: number[],
    topK = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    const { client, sdk } = await this.ready();
    const filter = this.filterOf(filters);

    const request = new sdk.VectorTopkSearchRequest(
      "vector",
      new sdk.Vector(query),
      topK,
    )
      .Projections(PROJECTIONS)
      .Config(new sdk.VectorSearchConfig().Ef(200));
    if (filter) {
      request.Filter(filter);
    }

    const response = (await client.vectorSearch({
      ...this.ns,
      request,
    })) as SearchResponse;
    check(response, "vectorSearch");

    return (response.rows ?? []).map((result) => ({
      id: String(result.row.id),
      payload: resultPayload(result.row),
      score: result.score,
    }));
  }

  async keywordSearch(
    query: string,
    topK = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[] | null> {
    const { client, sdk } = await this.ready();

    if (!this.supportsKeywordSearch) {
      return null;
    }

    const filter = this.filterOf(filters);
    const request = new sdk.BM25SearchRequest(BM25_INDEX, query)
      .Projections(PROJECTIONS)
      .Limit(topK);
    if (filter) {
      request.Filter(filter);
    }

    const response = (await client.bm25Search({
      ...this.ns,
      request,
    })) as SearchResponse;
    check(response, "bm25Search");

    return (response.rows ?? []).map((result) => ({
      id: String(result.row.id),
      payload: resultPayload(result.row),
      score: result.score,
    }));
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    const { client } = await this.ready();

    const response: QueryResponse = await client.query({
      ...this.ns,
      primaryKey: { id: vectorId },
      projections: PROJECTIONS,
    });
    check(response, `query '${vectorId}'`, ROW_KEY_NOT_FOUND);

    if (!response.row || response.row.id === undefined) {
      return null;
    }

    return {
      id: String(response.row.id),
      payload: resultPayload(response.row),
    };
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    const { client } = await this.ready();

    check(
      await client.upsert({
        ...this.ns,
        rows: [
          {
            id: vectorId,
            data: memoryData(payload),
            vector,
            textLemmatized: lemmatizedText(payload),
            metadata: metadataPayload(payload),
          },
        ],
      }),
      `upsert '${vectorId}'`,
    );
  }

  async delete(vectorId: string): Promise<void> {
    const { client } = await this.ready();

    check(
      await client.delete({ ...this.ns, primaryKey: { id: vectorId } }),
      `delete '${vectorId}'`,
    );
  }

  async deleteCol(): Promise<void> {
    // The constructor starts initialize() without awaiting it. Let any in-flight run land
    // first, otherwise it recreates the table after dropTable() and reset() is a no-op.
    await this._initPromise?.catch(() => undefined);
    this._initPromise = undefined;
    this.supportsKeywordSearch = false;

    const sdk = await this.loadSdk();
    const client = await this.ensureClient();
    const { ServerErrCode } = sdk;

    const dropped = check(
      await client.dropTable(this.databaseName, this.tableName),
      `dropTable '${this.tableName}'`,
      ServerErrCode.TableNotExist,
    );
    if (dropped === ServerErrCode.TableNotExist) {
      return;
    }

    // Drops are asynchronous; recreating the table before it is gone fails.
    await this.pollTable(
      client,
      (response) =>
        check(
          response,
          `descTable '${this.tableName}'`,
          ServerErrCode.TableNotExist,
        ) === ServerErrCode.TableNotExist,
      "dropped",
    );
  }

  async reset(): Promise<void> {
    await this.deleteCol();
    await this.initialize();
  }

  async list(
    filters?: SearchFilters,
    topK = 100,
  ): Promise<[VectorStoreResult[], number]> {
    const { client } = await this.ready();

    const response: SelectResponse = await client.select({
      ...this.ns,
      filter: this.filterOf(filters),
      projections: PROJECTIONS,
      limit: topK,
    });
    check(response, "select");

    const memories = (response.rows ?? []).map((row) => ({
      id: String(row.id),
      payload: resultPayload(row),
    }));
    return [memories, memories.length];
  }

  async getUserId(): Promise<string> {
    return this.storeUserId;
  }

  async setUserId(userId: string): Promise<void> {
    this.storeUserId = userId;
  }
}
