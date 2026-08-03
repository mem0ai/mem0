/*
 * Copyright (c) 2026, Oracle and/or its affiliates.
 */

import { v4 as uuidv4 } from "uuid";
import type oracledb from "oracledb";

import type {
  SearchFilters,
  VectorStoreConfig,
  VectorStoreResult,
} from "../types";
import { loadPeer } from "../utils/load_peer";
import type { VectorStore } from "./base";

// Keep this allowlist aligned with the Python Oracle vector store.
const METADATA_KEY_PATTERN = /^[a-zA-Z0-9_.[\],\s*]*$/;
const MIGRATIONS_TABLE = "mem0_oracle_migrations";
const MINIMUM_ORACLE_VECTOR_VERSION = 2_304_000_000;
type DistanceMetric = NonNullable<OracleAIVectorSearchConfig["distanceMetric"]>;
type IndexType = NonNullable<OracleAIVectorSearchConfig["indexType"]>;
type IndexParameterRange = readonly [min: number, max: number];

const VALID_DISTANCE_METRICS = new Set<DistanceMetric>([
  "EUCLIDEAN",
  "EUCLIDEAN_SQUARED",
  "COSINE",
  "DOT",
  "HAMMING",
  "MANHATTAN",
]);
const VALID_INDEX_TYPES = new Set<IndexType>(["HNSW", "IVF"]);
const SCORE_FROM_DISTANCE: Readonly<
  Record<DistanceMetric, (distance: number) => number>
> = {
  COSINE: (distance) => Math.max(0, Math.min(1, 1 - distance)),
  EUCLIDEAN: (distance) => 1 / (1 + Math.max(0, distance)),
  EUCLIDEAN_SQUARED: (distance) => 1 / (1 + Math.sqrt(Math.max(0, distance))),
  HAMMING: (distance) => 1 / (1 + Math.max(0, distance)),
  MANHATTAN: (distance) => 1 / (1 + Math.max(0, distance)),
  DOT: (distance) => -distance,
};
const INDEX_PARAMETER_RANGES: Readonly<
  Record<IndexType, Readonly<Record<string, IndexParameterRange>>>
> = {
  HNSW: {
    neighbors: [2, 2048],
    efconstruction: [1, 65535],
  },
  IVF: {
    neighbor_partitions: [1, 10_000_000],
    // Match Python validation: enforce only the documented lower bound.
    // Oracle validates any dataset-dependent upper limits.
    samples_per_partition: [1, Infinity],
    min_vectors_per_partition: [0, Infinity],
  },
};

type OracleDriver = typeof import("oracledb");
type OracleModule = OracleDriver & { default?: OracleDriver };
type OracleConnection = oracledb.Connection;
type OraclePool = oracledb.Pool;

/** Configuration for the Oracle Database AI Vector Search vector store. */
interface OracleAIVectorSearchConfig extends VectorStoreConfig {
  /**
   * `node-oracledb` connection or pool attributes, such as user, password,
   * connectString, poolMin, and poolMax.
   */
  connectionParams?: oracledb.ConnectionAttributes | oracledb.PoolAttributes;

  /** Existing `node-oracledb` Connection or Pool. */
  client?: oracledb.Connection | oracledb.Pool;
  useConnectionPool?: boolean;
  /** Oracle vector distance metric. Search results use higher-is-better scores. */
  distanceMetric?:
    | "EUCLIDEAN"
    | "EUCLIDEAN_SQUARED"
    | "COSINE"
    | "DOT"
    | "HAMMING"
    | "MANHATTAN";
  doCreateIndex?: boolean;
  /**
   * Update existing records with the same ID using MERGE. Defaults to false,
   * so inserts use the faster INSERT statement and reject duplicate IDs.
   */
  mutateOnDuplicate?: boolean;
  indexType?: "HNSW" | "IVF";
  indexName?: string;
  indexParameters?: Record<string, number>;
  indexAccuracy?: number;
}

/** Oracle Database AI Vector Search implementation for the OSS SDK. */
export class OracleAIVectorSearch implements VectorStore {
  private readonly config: OracleAIVectorSearchConfig;
  private readonly collectionName: string;
  private readonly indexName: string;
  private readonly dimension: number;
  private readonly distanceMetric: DistanceMetric;
  private readonly indexType: IndexType;
  private driver?: OracleDriver;
  private pool?: OraclePool;
  private connection?: OracleConnection;
  private ownsClient = false;
  private initPromise?: Promise<void>;
  private closePromise?: Promise<void>;

  constructor(config: OracleAIVectorSearchConfig = {}) {
    this.config = config;

    if (
      !config.client &&
      (!config.connectionParams ||
        Object.keys(config.connectionParams).length === 0)
    ) {
      throw new Error(
        "Must provide at least one of `connectionParams` and `client`",
      );
    }

    const collectionName = config.collectionName?.trim();
    if (collectionName === "") {
      throw new Error("collectionName cannot be empty");
    }

    const normalizedCollectionName = collectionName ?? "mem0";

    const rawMetric = String(config.distanceMetric ?? "COSINE").toUpperCase();
    const rawIndexType = String(config.indexType ?? "HNSW").toUpperCase();

    if (!VALID_DISTANCE_METRICS.has(rawMetric as DistanceMetric)) {
      throw new Error(
        `Unsupported Oracle distance metric: ${rawMetric}. Must be one of: ${Array.from(VALID_DISTANCE_METRICS).join(", ")}`,
      );
    }

    if (!VALID_INDEX_TYPES.has(rawIndexType as IndexType)) {
      throw new Error(
        `Unsupported Oracle index type: ${rawIndexType}. Must be one of: ${Array.from(VALID_INDEX_TYPES).join(", ")}`,
      );
    }

    this.collectionName = quoteIdentifier(normalizedCollectionName);
    this.indexName = quoteIdentifier(
      config.indexName ?? `${normalizedCollectionName}_VEC_IDX`,
    );
    this.dimension = config.embeddingModelDims ?? config.dimension ?? 1536;
    this.distanceMetric = rawMetric as DistanceMetric;
    this.indexType = rawIndexType as IndexType;

    validateIndexParameters(this.indexType, config.indexParameters);

    if (
      config.indexAccuracy !== undefined &&
      (!Number.isInteger(config.indexAccuracy) ||
        config.indexAccuracy < 1 ||
        config.indexAccuracy > 100)
    ) {
      throw new Error("indexAccuracy must be an integer between 1 and 100");
    }

    if (!Number.isInteger(this.dimension) || this.dimension <= 0) {
      throw new Error("dimension must be a positive integer");
    }
  }

  async initialize(): Promise<void> {
    if (!this.initPromise) {
      this.initPromise = this.doInitialize().catch((error) => {
        this.initPromise = undefined;
        throw error;
      });
    }
    return this.initPromise;
  }

  private async doInitialize(): Promise<void> {
    const driver = await loadOracleDriver();
    this.driver = driver;
    try {
      if (this.config.client) {
        if ("getConnection" in this.config.client) {
          this.pool = this.config.client;
        } else {
          this.connection = this.config.client;
        }
      } else if (this.config.useConnectionPool !== false) {
        this.pool = await driver.createPool(
          this.config.connectionParams as oracledb.PoolAttributes,
        );
        this.ownsClient = true;
      } else {
        this.connection = await driver.getConnection(
          this.config.connectionParams as oracledb.ConnectionAttributes,
        );
        this.ownsClient = true;
      }
      await this.validateDatabaseVersion();
      await this.createCol();
      await this.createMigrationTable();
    } catch (error) {
      if (this.ownsClient) await this.close();
      throw error;
    }
  }

  private async validateDatabaseVersion(): Promise<void> {
    await this.withConnection(
      (connection) => {
        if (connection.oracleServerVersion < MINIMUM_ORACLE_VECTOR_VERSION) {
          throw new Error(
            `Oracle DB version ${connection.oracleServerVersionString} not supported, must be >=23.4 for vector support`,
          );
        }
      },
      false,
      true,
    );
  }

  private async withConnection<T>(
    operation: (connection: OracleConnection) => Promise<T> | T,
    commit = false,
    skipInitialize = false,
  ): Promise<T> {
    if (!skipInitialize) {
      await this.initialize();
    }

    const connection = this.pool
      ? await this.pool.getConnection()
      : this.connection;
    if (!connection) {
      throw new Error("Oracle connection is not initialized");
    }

    try {
      const result = await operation(connection);
      if (commit) {
        await connection.commit();
      }
      return result;
    } catch (error) {
      if (!this.pool) {
        // Pooled connections roll back when released, but a direct connection is
        // retained for the store's lifetime. Roll back explicitly so a later
        // successful operation cannot commit a partially failed write.
        try {
          await connection.rollback();
        } catch (rollbackError) {
          console.error(
            "[OracleAIVectorSearch] Failed to roll back transaction:",
            rollbackError,
          );
        }
      }

      throw error;
    } finally {
      // Releasing a pooled connection also rolls back uncommitted work. This
      // must happen on both success and failure so the pool cannot leak one.
      if (this.pool) await connection.close();
    }
  }

  private async createCol(): Promise<void> {
    await this.withConnection(
      async (connection) => {
        await connection.execute(
          `CREATE TABLE IF NOT EXISTS ${this.collectionName} (
          id VARCHAR2(36) PRIMARY KEY,
          vector VECTOR(${this.dimension}),
          payload JSON
        )`,
        );
        if (this.config.doCreateIndex !== false) {
          await connection.execute(this.createIndexDdl());
        }
      },
      false,
      true,
    );
  }

  private async createMigrationTable(): Promise<void> {
    await this.withConnection(
      async (connection) => {
        await connection.execute(
          `CREATE TABLE IF NOT EXISTS ${MIGRATIONS_TABLE} (
        id NUMBER DEFAULT 1 PRIMARY KEY CHECK (id = 1),
        user_id VARCHAR2(255) NOT NULL
      )`,
        );
      },
      false,
      true,
    );
  }

  private createIndexDdl(): string {
    const organization =
      this.indexType === "HNSW"
        ? "INMEMORY NEIGHBOR GRAPH"
        : "NEIGHBOR PARTITIONS";
    const accuracy = this.config.indexAccuracy
      ? ` WITH TARGET ACCURACY ${this.config.indexAccuracy}`
      : "";
    const parameters = this.buildIndexParameterClause();
    const parameterClause = parameters ? ` PARAMETERS (${parameters})` : "";
    return (
      `CREATE VECTOR INDEX IF NOT EXISTS ${this.indexName} ON ${this.collectionName} (vector) ` +
      `ORGANIZATION ${organization} DISTANCE ${this.distanceMetric}${accuracy}${parameterClause}`
    );
  }

  private buildIndexParameterClause(): string {
    const parameters = this.config.indexParameters;
    if (!parameters || Object.keys(parameters).length === 0) return "";
    // Config is caller-owned and can be mutated after construction, so validate
    // again immediately before producing DDL.
    validateIndexParameters(this.indexType, parameters);

    const allowed =
      this.indexType === "HNSW"
        ? ["neighbors", "efconstruction"]
        : [
            "neighbor_partitions",
            "samples_per_partition",
            "min_vectors_per_partition",
          ];
    const parts = [`type ${this.indexType}`];
    for (const key of allowed) {
      const value = parameters[key];
      if (value === undefined) continue;
      const label = key === "neighbor_partitions" ? "neighbor partitions" : key;
      parts.push(`${label} ${value}`);
    }
    return parts.join(", ");
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[] = [],
  ): Promise<void> {
    if (!vectors.length) return;
    if (ids.length !== vectors.length) {
      throw new Error("ids and vectors must have the same length");
    }
    if (payloads.length > 0 && payloads.length !== vectors.length) {
      throw new Error("payloads must be empty or match vectors length");
    }

    await this.initialize();

    const insertSql = `
      INSERT INTO ${this.collectionName} (id, vector, payload)
      VALUES (:1, :2, :3)`;
    const mergeSql = `
    MERGE INTO ${this.collectionName} target
    USING (
      SELECT
        :1 AS id,
        :2 AS vector,
        :3 AS payload
      FROM dual
    ) src
    ON (target.id = src.id)
    WHEN MATCHED THEN
      UPDATE SET
        target.vector = src.vector,
        target.payload = src.payload
    WHEN NOT MATCHED THEN
      INSERT (id, vector, payload)
      VALUES (src.id, src.vector, src.payload)
  `;
    const sql = this.config.mutateOnDuplicate ? mergeSql : insertSql;

    // Explicit bindDefs prevent driver type scanning across batch elements
    const bindDefs = [
      { type: this.driver!.STRING, maxSize: 36 },
      { type: this.driver!.DB_TYPE_VECTOR },
      { type: this.driver!.DB_TYPE_JSON },
    ];

    // Map positional arguments into arrays matching :1, :2, :3
    const binds = vectors.map((vec, i) => [
      ids[i],
      Float32Array.from(vec),
      payloads[i] ?? {},
    ]);

    await this.withConnection(async (connection) => {
      const result = await connection.executeMany(sql, binds, {
        autoCommit: false,
        batchErrors: true,
        bindDefs,
      });

      // Handle partial row failures -> Strict All-or-None
      if (result.batchErrors && result.batchErrors.length > 0) {
        console.error(
          `[OracleAIVectorSearch] Batch insert failed with ${result.batchErrors.length} row error(s). Rolling back transaction.`,
        );

        for (const err of result.batchErrors) {
          const failedId =
            typeof err.offset === "number"
              ? (ids[err.offset] ?? "unknown")
              : "unknown";
          console.error(
            `  - Row index [${err.offset}] (ID: ${failedId}): ${err.message}`,
          );
        }

        // Throwing aborts the callback -> withConnection performs connection.rollback()
        throw new Error(
          `Batch insert failed on ${result.batchErrors.length} record(s). Transaction rolled back.`,
        );
      }
    }, true);
  }

  async search(
    query: number[],
    topK = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    const { clause, binds, hasFilter } = buildFilters(filters);
    // Oracle's vector index transform can be used only when there is no
    // metadata predicate. Applying it to a filtered query may select the
    // approximate top-k rows before the filter is evaluated.
    const selectClause = hasFilter
      ? "SELECT"
      : `SELECT /*+ VECTOR_INDEX_TRANSFORM(${this.collectionName}) */`;
    const sql = `${selectClause} id, payload, VECTOR_DISTANCE(vector, :query_vector, ${this.distanceMetric}) AS distance
      FROM ${this.collectionName} ${clause}
      ORDER BY distance
      FETCH APPROX FIRST :limit ROWS ONLY`;
    return this.withConnection(async (connection) => {
      const result = await connection.execute<[string, unknown, number]>(
        sql,
        oracleBindParameters({
          query_vector: Float32Array.from(query),
          limit: topK,
          ...binds,
        }),
        { outFormat: this.driver!.OUT_FORMAT_ARRAY },
      );
      return (result.rows || []).map((row) => {
        const distance = Number(row[2]);
        return {
          id: row[0],
          payload: parsePayload(row[1]),
          // Keep score semantics aligned with the Python Oracle vector store.
          score: SCORE_FROM_DISTANCE[this.distanceMetric](distance),
        };
      });
    });
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    return this.withConnection(async (connection) => {
      const result = await connection.execute<[string, unknown]>(
        `SELECT id, payload FROM ${this.collectionName} WHERE id = :id`,
        { id: vectorId },
        { outFormat: this.driver!.OUT_FORMAT_ARRAY },
      );
      const row = result.rows?.[0] as [string, unknown] | undefined;
      return row ? { id: row[0], payload: parsePayload(row[1]) } : null;
    });
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    await this.withConnection(async (connection) => {
      await connection.execute(
        `UPDATE ${this.collectionName} SET vector = :vector, payload = :payload WHERE id = :id`,
        oracleBindParameters({
          vector: {
            val: Float32Array.from(vector),
            type: this.driver!.DB_TYPE_VECTOR,
          },
          payload: { val: payload, type: this.driver!.DB_TYPE_JSON },
          id: vectorId,
        }),
      );
    }, true);
  }

  async delete(vectorId: string): Promise<void> {
    await this.withConnection(
      (connection) =>
        connection.execute(
          `DELETE FROM ${this.collectionName} WHERE id = :id`,
          {
            id: vectorId,
          },
        ),
      true,
    );
  }

  async deleteCol(): Promise<void> {
    await this.withConnection((connection) =>
      connection.execute(`DROP TABLE IF EXISTS ${this.collectionName} PURGE`),
    );
  }

  async list(
    filters?: SearchFilters,
    topK = 100,
  ): Promise<[VectorStoreResult[], number]> {
    const { clause, binds } = buildFilters(filters);
    return this.withConnection(async (connection) => {
      const result = await connection.execute<[string, unknown, number]>(
        `SELECT id, payload, COUNT(*) OVER() AS total_count
         FROM (
           SELECT id, payload
           FROM ${this.collectionName} ${clause}
         )
         FETCH FIRST :limit ROWS ONLY`,
        oracleBindParameters({ limit: topK, ...binds }),
        { outFormat: this.driver!.OUT_FORMAT_ARRAY },
      );
      const rows = (result.rows || []).map((row) => ({
        id: row[0],
        payload: parsePayload(row[1]),
      }));
      const total = result.rows?.length ? Number(result.rows[0][2]) : 0;
      return [rows, total];
    });
  }

  async getUserId(): Promise<string> {
    const generated = uuidv4();
    try {
      return await this.withConnection(async (connection) => {
        await connection.execute(
          `MERGE INTO ${MIGRATIONS_TABLE} m
       USING (SELECT 1 AS id, :generated_id AS user_id FROM dual) src
       ON (m.id = src.id)
       WHEN NOT MATCHED THEN
         INSERT (id, user_id) VALUES (src.id, src.user_id)`,
          { generated_id: generated },
        );

        return this.readUserId(connection);
      }, true);
    } catch (error) {
      // Concurrent MERGE statements can both observe a missing row before one
      // insert wins. The losing transaction rolls back in withConnection;
      // reading the winner's committed value completes initialization.
      if (!isUniqueConstraintError(error)) throw error;
      return this.withConnection((connection) => this.readUserId(connection));
    }
  }

  private async readUserId(connection: OracleConnection): Promise<string> {
    const result = await connection.execute<[string]>(
      `SELECT user_id FROM ${MIGRATIONS_TABLE} WHERE id = 1`,
      [],
      { outFormat: this.driver!.OUT_FORMAT_ARRAY },
    );
    const row = result.rows?.[0];
    if (!row)
      throw new Error("Failed to retrieve user_id from migration table");
    return String(row[0]);
  }

  async setUserId(userId: string): Promise<void> {
    await this.withConnection(async (connection) => {
      await connection.execute(
        `MERGE INTO ${MIGRATIONS_TABLE} m
       USING (SELECT 1 AS id, :user_id AS user_id FROM dual) src
       ON (m.id = src.id)
       WHEN MATCHED THEN
         UPDATE SET m.user_id = src.user_id
       WHEN NOT MATCHED THEN
         INSERT (id, user_id) VALUES (src.id, src.user_id)`,
        { user_id: userId },
      );
    }, true);
  }

  /**
   * Closes only connections or pools created by this store. Caller-provided
   * clients remain the caller's responsibility. This method is idempotent;
   * concurrent callers await the same in-flight close operation.
   */
  async close(): Promise<void> {
    if (this.closePromise) return this.closePromise;
    if (!this.ownsClient) return;

    const pool = this.pool;
    const connection = this.connection;
    this.pool = undefined;
    this.connection = undefined;
    this.ownsClient = false;
    this.closePromise = (async () => {
      if (pool) await pool.close();
      if (connection) await connection.close();
    })();

    try {
      await this.closePromise;
    } finally {
      this.closePromise = undefined;
    }
  }
}

function quoteIdentifier(identifier: string): string {
  const name = identifier.trim();

  const validateRegex =
    /^(?:"[^"]+"|[A-Za-z][A-Za-z0-9_$#]*)(?:\.(?:"[^"]+"|[A-Za-z][A-Za-z0-9_$#]*))*$/;
  if (!validateRegex.test(name)) {
    throw new Error(`Invalid Oracle identifier: ${identifier}`);
  }

  // extracts parts of the identifier with quoted and unquoted.
  const matchRegex = /"([^"]+)"|([A-Za-z][A-Za-z0-9_$#]*)/g;
  const groups = [];

  for (const match of name.matchAll(matchRegex)) {
    groups.push(match[1] || match[2]);
  }
  const quotedParts = groups.map((g) => `"${g}"`);
  return quotedParts.join(".");
}

type FilterState = {
  binds: Record<string, unknown>;
  nextParameter: number;
};

function buildFilters(filters?: SearchFilters): {
  clause: string;
  binds: Record<string, unknown>;
  hasFilter: boolean;
} {
  if (!filters || Object.keys(filters).length === 0) {
    return { clause: "", binds: {}, hasFilter: false };
  }

  const state: FilterState = { binds: {}, nextParameter: 0 };
  return {
    clause: `WHERE ${buildFilterConditions(filters, state)}`,
    binds: state.binds,
    hasFilter: true,
  };
}

function buildFilterConditions(
  filters: Record<string, any>,
  state: FilterState,
): string {
  const clauses: string[] = [];

  for (const [key, value] of Object.entries(filters)) {
    if (key === "$or" || key === "$and" || key === "$not") {
      if (!Array.isArray(value) || value.some((item) => !isPlainObject(item))) {
        throw new Error(`${key} filter must be an array of filter objects`);
      }
      const children = value.map((item) => buildFilterConditions(item, state));
      if (children.length === 0) continue;
      if (key === "$or") clauses.push(`(${children.join(" OR ")})`);
      else if (key === "$and") clauses.push(`(${children.join(" AND ")})`);
      else clauses.push(`NOT (${children.join(" OR ")})`);
      continue;
    }

    validateMetadataKey(key);

    // mem0 uses { key: "*" } to mean "key exists with any value".
    // Check for property presence instead of comparing literal value == "*".
    if (value === "*") {
      clauses.push(`JSON_EXISTS(payload, '${jsonPath(key)}')`);
    } else if (Array.isArray(value)) {
      clauses.push(buildInCondition(key, value, false, state));
    } else if (isPlainObject(value)) {
      for (const [operator, operand] of Object.entries(value)) {
        clauses.push(buildOperatorCondition(key, operator, operand, state));
      }
    } else {
      clauses.push(buildComparison(key, "==", value, state));
    }
  }

  if (clauses.length === 0) throw new Error("Filter object must not be empty");
  return clauses.length === 1 ? clauses[0] : `(${clauses.join(" AND ")})`;
}

function buildOperatorCondition(
  key: string,
  operator: string,
  value: unknown,
  state: FilterState,
): string {
  const normalized = operator.startsWith("$") ? operator.slice(1) : operator;
  switch (normalized) {
    case "eq":
      return buildComparison(key, "==", value, state);
    case "ne":
      return buildComparison(key, "!=", value, state);
    case "gt":
    case "gte":
    case "lt":
    case "lte":
      return buildComparison(
        key,
        comparisonOperator(normalized as "gt" | "gte" | "lt" | "lte"),
        value,
        state,
      );
    case "in":
      if (!Array.isArray(value)) throw new Error("$in requires an array value");
      return buildInCondition(key, value, false, state);
    case "nin":
      if (!Array.isArray(value))
        throw new Error("$nin requires an array value");
      return buildInCondition(key, value, true, state);
    case "between":
      if (!Array.isArray(value) || value.length !== 2) {
        throw new Error("$between requires a two-element array");
      }
      return `(${buildComparison(key, ">=", value[0], state)} AND ${buildComparison(key, "<=", value[1], state)})`;
    case "exists":
      if (typeof value !== "boolean")
        throw new Error("$exists requires a boolean value");
      return `${value ? "" : "NOT "}JSON_EXISTS(payload, '${jsonPath(key)}')`;
    case "contains":
    case "icontains":
      return buildContainsCondition(
        key,
        value,
        normalized === "icontains",
        state,
      );
    default:
      throw new Error(`Unsupported filter operator: ${operator}`);
  }
}

function comparisonOperator(
  operator: "gt" | "gte" | "lt" | "lte",
): ">" | ">=" | "<" | "<=" {
  const operators = { gt: ">", gte: ">=", lt: "<", lte: "<=" } as const;
  return operators[operator];
}

function validateIndexParameters(
  indexType: "HNSW" | "IVF",
  parameters?: Record<string, number>,
): void {
  if (parameters == null) return;

  const ranges = INDEX_PARAMETER_RANGES[indexType];
  for (const [key, value] of Object.entries(parameters)) {
    const range = ranges[key];
    if (!range) {
      throw new Error(`Unsupported ${indexType} index parameter: ${key}`);
    }

    const [min, max] = range;
    if (!Number.isInteger(value) || value < min || value > max) {
      const boundsText =
        max === Infinity ? `>= ${min}` : `between ${min} and ${max}`;
      throw new Error(
        `indexParameters.${key} must be an integer ${boundsText}`,
      );
    }
  }
}

function buildComparison(
  key: string,
  operator: "==" | "!=" | ">" | ">=" | "<" | "<=",
  value: unknown,
  state: FilterState,
): string {
  const parameter = addBind(value, state);
  return `JSON_EXISTS(payload, '${jsonPath(key)}?(@ ${operator} $${parameter})' PASSING :${parameter} AS "${parameter}")`;
}

function buildInCondition(
  key: string,
  values: unknown[],
  negate: boolean,
  state: FilterState,
): string {
  if (values.length === 0) return negate ? "1 = 1" : "1 = 0";
  const comparisons = values.map((value) =>
    buildComparison(key, "==", value, state),
  );
  return `(${comparisons.map((condition) => (negate ? `NOT (${condition})` : condition)).join(negate ? " AND " : " OR ")})`;
}

function buildContainsCondition(
  key: string,
  value: unknown,
  insensitive: boolean,
  state: FilterState,
): string {
  const escaped = String(value)
    .replace(/\\/g, "\\\\")
    .replace(/%/g, "\\%")
    .replace(/_/g, "\\_");
  const parameter = addBind(`%${escaped}%`, state);
  const expression = `JSON_VALUE(payload, '${jsonPath(key)}' RETURNING VARCHAR2(4000))`;
  return insensitive
    ? `LOWER(${expression}) LIKE LOWER(:${parameter}) ESCAPE '\\'`
    : `${expression} LIKE :${parameter} ESCAPE '\\'`;
}

function addBind(value: unknown, state: FilterState): string {
  const parameter = `filter_${state.nextParameter++}`;
  state.binds[parameter] = value;
  return parameter;
}

function validateMetadataKey(key: string): void {
  if (!METADATA_KEY_PATTERN.test(key)) {
    throw new Error(`Invalid Oracle metadata filter key: ${key}`);
  }
}

function jsonPath(key: string): string {
  return (
    "$" +
    key
      .split(".")
      .map((part) =>
        part.endsWith("[*]") ? `."${part.slice(0, -3)}"[*]` : `."${part}"`,
      )
      .join("")
  );
}

function isPlainObject(value: unknown): value is Record<string, any> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isUniqueConstraintError(error: unknown): boolean {
  if (typeof error !== "object" || error === null) {
    return false;
  }

  const oracleError = error as Partial<oracledb.DBError>;

  return (
    oracleError.errorNum === 1 ||
    (typeof oracleError.message === "string" &&
      oracleError.message.includes("ORA-00001"))
  );
}

function parsePayload(payload: unknown): Record<string, any> {
  if (payload === null || payload === undefined) return {};
  if (typeof payload === "object" && !Buffer.isBuffer(payload)) {
    return payload as Record<string, any>;
  }
  return JSON.parse(
    Buffer.isBuffer(payload) ? payload.toString("utf8") : String(payload),
  );
}

function oracleBindParameters(
  values: Record<string, unknown>,
): oracledb.BindParameters {
  // @types/oracledb does not yet include Float32Array as a VECTOR bind value.
  return values as unknown as oracledb.BindParameters;
}

async function loadOracleDriver(): Promise<OracleDriver> {
  // Keep the optional peer lazy-loaded until the Oracle store is initialized.
  const module = (await loadPeer(
    "oracledb",
    "Oracle AI Vector Search",
    () => import("oracledb"),
  )) as OracleModule;
  return module.default || module;
}
