import type { BindParameters, Connection, Pool } from "oracledb";
import { v4 as uuidv4 } from "uuid";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";
import { loadPeer } from "../utils/load_peer";

const DISTANCE_METRICS = [
  "COSINE",
  "EUCLIDEAN",
  "EUCLIDEAN_SQUARED",
  "DOT",
  "HAMMING",
  "MANHATTAN",
] as const;

type DistanceMetric = (typeof DISTANCE_METRICS)[number];
type IndexType = "HNSW" | "IVF";

const SCORE_FROM_DISTANCE: Record<DistanceMetric, (d: number) => number> = {
  COSINE: (d) => Math.max(0, Math.min(1, 1 - d)),
  EUCLIDEAN: (d) => 1 / (1 + Math.max(0, d)),
  EUCLIDEAN_SQUARED: (d) => 1 / (1 + Math.sqrt(Math.max(0, d))),
  HAMMING: (d) => 1 / (1 + Math.max(0, d)),
  MANHATTAN: (d) => 1 / (1 + Math.max(0, d)),
  DOT: (d) => -d,
};

const INDEX_PARAMETER_RANGES: Record<
  IndexType,
  Record<string, [number, number]>
> = {
  HNSW: {
    neighbors: [2, 2048],
    efconstruction: [1, 65535],
  },
  IVF: {
    "neighbor partitions": [1, 10_000_000],
    samples_per_partition: [1, Number.MAX_SAFE_INTEGER],
    min_vectors_per_partition: [0, Number.MAX_SAFE_INTEGER],
  },
};

const IDENTIFIER_RE = /^(?:"[^"]+"|[^".]+)(?:\.(?:"[^"]+"|[^".]+))*$/;
const METADATA_KEY_RE = /^[a-zA-Z0-9_.[\],\s*]+$/;

export function quoteIdentifier(name: string): string {
  const trimmed = name.trim();
  if (!IDENTIFIER_RE.test(trimmed)) {
    throw new Error(`Identifier name ${name} is not valid.`);
  }
  return [...trimmed.matchAll(/"([^"]+)"|([^".]+)/g)]
    .map((m) => `"${m[1] ?? m[2]}"`)
    .join(".");
}

function jsonPath(metadataKey: string): string {
  if (!METADATA_KEY_RE.test(metadataKey)) {
    throw new Error(
      `Invalid metadata key '${metadataKey}'. Only letters, numbers, underscores, ` +
        `nesting via '.', and array wildcards '[*]' are allowed.`,
    );
  }
  return metadataKey
    .split(".")
    .map((part) =>
      part.endsWith("[*]") ? `."${part.slice(0, -3)}"[*]` : `."${part}"`,
    )
    .join("");
}

const COMPARISON_OPERATORS: Record<string, string> = {
  eq: "==",
  ne: "!=",
  gt: ">",
  gte: ">=",
  lt: "<",
  lte: "<=",
};

const FIELD_OPERATORS = new Set([
  ...Object.keys(COMPARISON_OPERATORS),
  "in",
  "nin",
  "contains",
  "icontains",
]);

const LOGICAL_OPERATORS: Record<string, "and" | "or" | "not"> = {
  $and: "and",
  $or: "or",
  $not: "not",
  AND: "and",
  OR: "or",
  NOT: "not",
};

function isScalar(value: any): boolean {
  return value === null || (typeof value !== "object" && !Array.isArray(value));
}

function bindFilterValue(
  value: any,
  binds: Record<string, any>,
): [string, string] {
  const name = `f_${Object.keys(binds).length}`;
  binds[name] = value;
  return [`$${name}`, `:${name} AS "${name}"`];
}

function jsonExists(
  path: string,
  predicate: string,
  passings: string[],
): string {
  const passingClause =
    passings.length > 0 ? ` PASSING ${passings.join(", ")}` : "";
  return `JSON_EXISTS(payload, '$${path}?(${predicate})'${passingClause})`;
}

function buildFieldCondition(
  metadataKey: string,
  value: any,
  binds: Record<string, any>,
): string {
  const path = jsonPath(metadataKey);

  if (value === "*") {
    return `JSON_EXISTS(payload, '$${path}')`;
  }

  if (isScalar(value)) {
    if (value === null) {
      return jsonExists(path, "@ == null", []);
    }
    const [variable, passing] = bindFilterValue(value, binds);
    return jsonExists(path, `@ == ${variable}`, [passing]);
  }

  if (Array.isArray(value)) {
    throw new Error(
      `Oracle filter for field '${metadataKey}' must be a scalar or an operator object`,
    );
  }

  const operators = Object.entries(value);
  if (operators.length === 0) {
    throw new Error(
      `Operator filter for field '${metadataKey}' must not be empty`,
    );
  }

  const unsupported = operators
    .map(([op]) => op)
    .filter((op) => !FIELD_OPERATORS.has(op));
  if (unsupported.length > 0) {
    throw new Error(
      `Unsupported Oracle filter operator(s) for field '${metadataKey}': ${unsupported.sort().join(", ")}`,
    );
  }

  const predicates: string[] = [];
  const passings: string[] = [];
  const additionalClauses: string[] = [];

  for (const [operator, operand] of operators) {
    if (operator in COMPARISON_OPERATORS) {
      if (!isScalar(operand)) {
        throw new Error(
          `Oracle filter operator '${operator}' requires a scalar value`,
        );
      }
      if (operand === null) {
        if (operator !== "eq" && operator !== "ne") {
          throw new Error(
            `Oracle filter operator '${operator}' does not support null`,
          );
        }
        predicates.push(`@ ${COMPARISON_OPERATORS[operator]} null`);
        continue;
      }
      const [variable, passing] = bindFilterValue(operand, binds);
      predicates.push(`@ ${COMPARISON_OPERATORS[operator]} ${variable}`);
      passings.push(passing);
      continue;
    }

    if (operator === "in" || operator === "nin") {
      if (!Array.isArray(operand) || operand.length === 0) {
        throw new Error(
          `Oracle filter operator '${operator}' requires a non-empty array`,
        );
      }

      const variables: string[] = [];
      const listPassings: string[] = [];
      for (const item of operand) {
        if (!isScalar(item)) {
          throw new Error(
            `Oracle filter operator '${operator}' requires scalar values`,
          );
        }
        if (item === null) {
          variables.push("null");
          continue;
        }
        const [variable, passing] = bindFilterValue(item, binds);
        variables.push(variable);
        listPassings.push(passing);
      }

      const membership = jsonExists(
        path,
        `@ in (${variables.join(", ")})`,
        listPassings,
      );
      additionalClauses.push(
        operator === "in" ? membership : `NOT (${membership})`,
      );
      continue;
    }

    if (typeof operand !== "string") {
      throw new Error(
        `Oracle filter operator '${operator}' requires a string value`,
      );
    }

    if (operator === "contains") {
      const [variable, passing] = bindFilterValue(operand, binds);
      predicates.push(`@ has substring ${variable}`);
      passings.push(passing);
    } else {
      const [variable, passing] = bindFilterValue(operand.toLowerCase(), binds);
      predicates.push(`@.lower() has substring ${variable}`);
      passings.push(passing);
    }
  }

  const clauses = [...additionalClauses];
  if (predicates.length > 0) {
    clauses.unshift(jsonExists(path, predicates.join(" && "), passings));
  }

  return clauses.length === 1 ? clauses[0] : `(${clauses.join(" AND ")})`;
}

export function buildFilterGroup(
  filters: Record<string, any>,
  binds: Record<string, any>,
): string {
  const entries = Object.entries(filters ?? {});
  if (entries.length === 0) {
    throw new Error("Oracle filter groups must be non-empty objects");
  }

  const clauses: string[] = [];
  for (const [key, value] of entries) {
    const logicalOperator = LOGICAL_OPERATORS[key];
    if (logicalOperator) {
      if (!Array.isArray(value) || value.length === 0) {
        throw new Error(
          `Logical filter operator '${key}' requires a non-empty array`,
        );
      }
      const nested = value.map((condition) =>
        buildFilterGroup(condition, binds),
      );
      if (logicalOperator === "not") {
        clauses.push(`NOT (${nested.join(" OR ")})`);
      } else {
        clauses.push(
          `(${nested.join(logicalOperator === "and" ? " AND " : " OR ")})`,
        );
      }
      continue;
    }

    if (key.startsWith("$")) {
      throw new Error(`Unsupported Oracle logical filter operator: ${key}`);
    }

    clauses.push(buildFieldCondition(key, value, binds));
  }

  return clauses.length === 1 ? clauses[0] : `(${clauses.join(" AND ")})`;
}

export function buildWhereClause(
  filters?: SearchFilters,
): [string, Record<string, any>] {
  if (!filters || Object.keys(filters).length === 0) {
    return ["", {}];
  }
  const binds: Record<string, any> = {};
  return [`WHERE ${buildFilterGroup(filters, binds)}`, binds];
}

interface OracleDBConfig extends VectorStoreConfig {
  connectionParams?: Record<string, any>;
  useConnectionPool?: boolean;
  client?: Connection | Pool;
  collectionName?: string;
  embeddingModelDims?: number;
  distanceMetric?: DistanceMetric;
  doCreateIndex?: boolean;
  indexType?: IndexType;
  indexName?: string;
  indexParameters?: Record<string, number>;
  indexAccuracy?: number;
}

export class OracleAIVectorSearch implements VectorStore {
  private readonly collectionName: string;
  private readonly indexName: string;
  private readonly embeddingModelDims: number;
  private readonly distanceMetric: DistanceMetric;
  private readonly indexType: IndexType;
  private readonly indexParameters: Record<string, number>;
  private readonly indexAccuracy?: number;
  private readonly doCreateIndex: boolean;
  private readonly config: OracleDBConfig;
  private oracledb: any;
  private client?: Connection | Pool;
  private ownsClient = false;
  private _initPromise?: Promise<void>;

  constructor(config: OracleDBConfig) {
    if (!config.connectionParams && !config.client) {
      throw new Error(
        "Must provide at least one of `connectionParams` and `client`",
      );
    }

    this.collectionName = quoteIdentifier(config.collectionName || "mem0");
    this.indexName = quoteIdentifier(
      config.indexName || `${config.collectionName || "mem0"}_VEC_IDX`,
    );

    this.embeddingModelDims = config.embeddingModelDims ?? 1536;
    if (
      !Number.isInteger(this.embeddingModelDims) ||
      this.embeddingModelDims <= 0
    ) {
      throw new Error("`embeddingModelDims` must be a positive integer");
    }

    const distanceMetric = (config.distanceMetric ??
      "COSINE") as string as DistanceMetric;
    this.distanceMetric = distanceMetric.toUpperCase() as DistanceMetric;
    if (!DISTANCE_METRICS.includes(this.distanceMetric)) {
      throw new Error(`Unsupported distance metric: ${config.distanceMetric}`);
    }

    const indexType = (config.indexType ?? "HNSW") as string;
    this.indexType = indexType.toUpperCase() as IndexType;
    if (this.indexType !== "HNSW" && this.indexType !== "IVF") {
      throw new Error(`Unsupported index type: ${config.indexType}`);
    }

    this.indexAccuracy = config.indexAccuracy;
    if (
      this.indexAccuracy !== undefined &&
      (!Number.isInteger(this.indexAccuracy) ||
        this.indexAccuracy <= 0 ||
        this.indexAccuracy > 100)
    ) {
      throw new Error("`indexAccuracy` must be an integer between 1 and 100");
    }

    this.indexParameters = this.validateIndexParameters(config.indexParameters);
    this.doCreateIndex = config.doCreateIndex ?? true;
    this.config = config;
  }

  private validateIndexParameters(
    parameters?: Record<string, number>,
  ): Record<string, number> {
    if (!parameters) return {};

    const allowed = INDEX_PARAMETER_RANGES[this.indexType];
    const validated: Record<string, number> = {};

    for (const [key, value] of Object.entries(parameters)) {
      const range = allowed[key];
      if (!range) {
        throw new Error(
          `Unsupported ${this.indexType} index parameter '${key}'. ` +
            `Allowed: ${Object.keys(allowed).join(", ")}`,
        );
      }
      if (!Number.isInteger(value) || value < range[0] || value > range[1]) {
        throw new Error(
          `Index parameter '${key}' must be an integer between ${range[0]} and ${range[1]}`,
        );
      }
      validated[key] = value;
    }

    return validated;
  }

  async initialize(): Promise<void> {
    if (!this._initPromise) {
      this._initPromise = this._doInitialize().catch(async (error) => {
        if (this.ownsClient && this.client) {
          await Promise.resolve(this.client.close()).catch(() => {});
          this.client = undefined;
          this.ownsClient = false;
        }
        this._initPromise = undefined;
        throw error;
      });
    }
    return this._initPromise;
  }

  private async _doInitialize(): Promise<void> {
    const sdk = await loadPeer(
      "oracledb",
      "Oracle AI Vector Search",
      () => import("oracledb"),
    );
    this.oracledb = sdk.default ?? sdk;

    if (this.config.client) {
      this.client = this.config.client;
    } else if (this.config.useConnectionPool ?? true) {
      this.client = await this.oracledb.createPool({
        poolMin: 1,
        poolMax: 4,
        ...this.config.connectionParams,
      });
      this.ownsClient = true;
    } else {
      this.client = await this.oracledb.getConnection(
        this.config.connectionParams,
      );
      this.ownsClient = true;
    }

    await this.assertVectorSupport();
    await this.createCol();
  }

  private isPool(client: Connection | Pool): client is Pool {
    return typeof (client as Pool).getConnection === "function";
  }

  private async withConnection<T>(
    fn: (connection: Connection) => Promise<T>,
    commit = false,
  ): Promise<T> {
    const client = this.client!;

    if (!this.isPool(client)) {
      const connection = client as Connection;
      try {
        const result = await fn(connection);
        if (commit) await connection.commit();
        return result;
      } catch (err) {
        await connection.rollback();
        throw err;
      }
    }

    const connection = await client.getConnection();
    try {
      const result = await fn(connection);
      if (commit) await connection.commit();
      return result;
    } catch (err) {
      await connection.rollback();
      throw err;
    } finally {
      await connection.close();
    }
  }

  private async assertVectorSupport(): Promise<void> {
    if (!this.oracledb.thin) {
      const [major, minor] = [
        Math.floor(this.oracledb.oracleClientVersion / 100000000),
        Math.floor(this.oracledb.oracleClientVersion / 100000) % 100,
      ];
      if (major < 23 || (major === 23 && minor < 4)) {
        throw new Error(
          `Oracle DB client driver version ${this.oracledb.oracleClientVersionString} ` +
            "not supported, must be >=23.4 for vector support",
        );
      }
    }

    const version = await this.withConnection(
      async (connection) => connection.oracleServerVersionString,
    );
    const [major, minor] = version.split(".").map(Number);
    if (major < 23 || (major === 23 && minor < 4)) {
      throw new Error(
        `Oracle DB version ${version} not supported, must be >=23.4 for vector support`,
      );
    }
  }

  private createIndexDdl(): string {
    const accuracy = this.indexAccuracy
      ? `WITH TARGET ACCURACY ${this.indexAccuracy}`
      : "";

    const parameterEntries = Object.entries(this.indexParameters);
    const parameters =
      parameterEntries.length > 0
        ? `PARAMETERS (${[
            `type ${this.indexType}`,
            ...parameterEntries.map(([key, value]) => `${key} ${value}`),
          ].join(", ")})`
        : "";

    const organization =
      this.indexType === "HNSW"
        ? "INMEMORY NEIGHBOR GRAPH"
        : "NEIGHBOR PARTITIONS";

    return (
      `CREATE VECTOR INDEX IF NOT EXISTS ${this.indexName} ON ${this.collectionName} (vector) ` +
      `ORGANIZATION ${organization} DISTANCE ${this.distanceMetric} ${accuracy} ${parameters}`
    );
  }

  private async createCol(): Promise<void> {
    await this.withConnection(async (connection) => {
      await connection.execute(`
        CREATE TABLE IF NOT EXISTS ${this.collectionName} (
          id VARCHAR2(36) PRIMARY KEY,
          vector VECTOR(${this.embeddingModelDims}),
          payload JSON
        )
      `);

      await connection.execute(`
        CREATE TABLE IF NOT EXISTS memory_migrations (
          id NUMBER PRIMARY KEY,
          user_id VARCHAR2(255) NOT NULL
        )
      `);

      if (this.doCreateIndex) {
        await connection.execute(this.createIndexDdl());
      }
    }, true);
  }

  private loadPayload(value: any): Record<string, any> {
    if (value === null || value === undefined) return {};
    if (typeof value === "string") return JSON.parse(value);
    if (Buffer.isBuffer(value)) return JSON.parse(value.toString("utf-8"));
    return value;
  }

  private vectorBind(vector: number[]) {
    return {
      type: this.oracledb.DB_TYPE_VECTOR,
      val: new Float32Array(vector),
    };
  }

  private payloadBind(payload: Record<string, any>) {
    return { type: this.oracledb.DB_TYPE_JSON, val: payload };
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    if (ids.length !== vectors.length) {
      throw new Error("ids and vectors must have the same length");
    }
    if (payloads.length !== vectors.length) {
      throw new Error("payloads and vectors must have the same length");
    }

    if (vectors.length === 0) return;

    await this.initialize();

    await this.withConnection(async (connection) => {
      await connection.executeMany(
        `INSERT INTO ${this.collectionName} (id, vector, payload) VALUES (:id, :vector, :payload)`,
        vectors.map((vector, i) => ({
          id: ids[i],
          vector: new Float32Array(vector),
          payload: payloads[i] ?? {},
        })) as BindParameters[],
        {
          bindDefs: {
            id: { type: this.oracledb.DB_TYPE_VARCHAR, maxSize: 36 },
            vector: { type: this.oracledb.DB_TYPE_VECTOR },
            payload: { type: this.oracledb.DB_TYPE_JSON },
          },
        },
      );
    }, true);
  }

  async search(
    query: number[],
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    await this.initialize();

    const [whereClause, filterBinds] = buildWhereClause(filters);
    const hasFilter = whereClause.length > 0;
    const selectClause = hasFilter
      ? "SELECT"
      : `SELECT /*+ VECTOR_INDEX_TRANSFORM(${this.collectionName}) */`;
    const sql =
      `${selectClause} id, payload, VECTOR_DISTANCE(vector, :query_vec, ${this.distanceMetric}) distance ` +
      `FROM ${this.collectionName} ${whereClause} ORDER BY distance FETCH APPROX FIRST :max_rows ROWS ONLY`;

    const rows = await this.withConnection(async (connection) => {
      const result = await connection.execute<any[]>(sql, {
        query_vec: this.vectorBind(query),
        max_rows: topK,
        ...filterBinds,
      });
      return result.rows ?? [];
    });

    return rows.map((row) => ({
      id: row[0],
      payload: this.loadPayload(row[1]),
      score: SCORE_FROM_DISTANCE[this.distanceMetric](Number(row[2])),
    }));
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    await this.initialize();

    const rows = await this.withConnection(async (connection) => {
      const result = await connection.execute<any[]>(
        `SELECT id, payload FROM ${this.collectionName} WHERE id = :vector_id`,
        { vector_id: vectorId },
      );
      return result.rows ?? [];
    });

    if (rows.length === 0) return null;
    return { id: rows[0][0], payload: this.loadPayload(rows[0][1]) };
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    await this.initialize();

    const assignments: string[] = [];
    const binds: Record<string, any> = { vector_id: vectorId };

    if (vector) {
      assignments.push("vector = :vector");
      binds.vector = this.vectorBind(vector);
    }
    if (payload) {
      assignments.push("payload = :payload");
      binds.payload = this.payloadBind(payload);
    }
    if (assignments.length === 0) return;

    await this.withConnection(
      (connection) =>
        connection.execute(
          `UPDATE ${this.collectionName} SET ${assignments.join(", ")} WHERE id = :vector_id`,
          binds,
        ),
      true,
    );
  }

  async delete(vectorId: string): Promise<void> {
    await this.initialize();

    await this.withConnection(
      (connection) =>
        connection.execute(
          `DELETE FROM ${this.collectionName} WHERE id = :vector_id`,
          { vector_id: vectorId },
        ),
      true,
    );
  }

  async deleteCol(): Promise<void> {
    await this.initialize();

    await this.withConnection(
      (connection) =>
        connection.execute(`DROP TABLE ${this.collectionName} PURGE`),
      true,
    );
  }

  async list(
    filters?: SearchFilters,
    topK: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    await this.initialize();

    const [whereClause, filterBinds] = buildWhereClause(filters);

    return this.withConnection(async (connection) => {
      const listResult = await connection.execute<any[]>(
        `SELECT id, payload, COUNT(*) OVER () total FROM ${this.collectionName} ${whereClause} FETCH FIRST :max_rows ROWS ONLY`,
        { ...filterBinds, max_rows: topK },
      );

      const rows = listResult.rows ?? [];
      const results = rows.map((row) => ({
        id: row[0],
        payload: this.loadPayload(row[1]),
      }));

      return [results, Number(rows[0]?.[2] ?? 0)];
    });
  }

  async getUserId(): Promise<string> {
    await this.initialize();

    const rows = await this.withConnection(async (connection) => {
      const result = await connection.execute<any[]>(
        "SELECT user_id FROM memory_migrations WHERE id = 1",
      );
      return result.rows ?? [];
    });

    if (rows.length > 0) return rows[0][0];

    const generatedUserId = uuidv4();
    await this.setUserId(generatedUserId);
    return generatedUserId;
  }

  async setUserId(userId: string): Promise<void> {
    await this.initialize();

    await this.withConnection(async (connection) => {
      await connection.execute("DELETE FROM memory_migrations WHERE id = 1");
      await connection.execute(
        "INSERT INTO memory_migrations (id, user_id) VALUES (1, :user_id)",
        { user_id: userId },
      );
    }, true);
  }

  async close(): Promise<void> {
    if (this.client && this.ownsClient) {
      await this.client.close();
    }
  }
}
