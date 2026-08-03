/*
 * Copyright (c) 2026, Oracle and/or its affiliates.
 */

/// <reference types="jest" />

import type { SearchFilters } from "../src/types";

const oracleConfig = {
  user: process.env.ORACLE_USERNAME,
  password: process.env.ORACLE_PASSWORD,
  connectString: process.env.ORACLE_DSN,
};
const hasOracleCredentials = Object.values(oracleConfig).every(Boolean);
const hasOracleDriver = (() => {
  try {
    require.resolve("oracledb");
    return true;
  } catch {
    return false;
  }
})();
const mockLoadPeer = jest.fn();
let mockUseDriver = true;

jest.mock("../src/utils/load_peer", () => ({
  loadPeer: (...args: any[]) =>
    mockUseDriver
      ? mockLoadPeer(...args)
      : jest.requireActual("../src/utils/load_peer").loadPeer(...args),
}));

const { OracleAIVectorSearch } = require("../src/vector_stores/oracledb");

const mockExecute = jest.fn();
const mockExecuteMany = jest.fn();
const mockCommit = jest.fn();
const mockRollback = jest.fn();
const mockClose = jest.fn();
const mockPoolGetConnection = jest.fn();
const mockPoolClose = jest.fn();
const mockCreatePool = jest.fn();
const mockGetConnection = jest.fn();
const mockConnection = {
  execute: mockExecute,
  executeMany: mockExecuteMany,
  commit: mockCommit,
  rollback: mockRollback,
  close: mockClose,
  oracleServerVersion: 2_304_000_000,
  oracleServerVersionString: "23.4.0.0.0",
};
const mockPool = {
  getConnection: mockPoolGetConnection,
  close: mockPoolClose,
};

const mockDriver = {
  STRING: "STRING",
  DB_TYPE_VECTOR: "VECTOR",
  DB_TYPE_JSON: "JSON",
  OUT_FORMAT_ARRAY: "ARRAY",
  createPool: mockCreatePool,
  getConnection: mockGetConnection,
};

beforeEach(() => {
  mockUseDriver = true;
  jest.clearAllMocks();
  mockLoadPeer.mockResolvedValue(mockDriver);
  mockExecute.mockResolvedValue({ rows: [] });
  mockExecuteMany.mockResolvedValue({ rowsAffected: 1 });
  mockPoolGetConnection.mockResolvedValue(mockConnection);
  mockCreatePool.mockResolvedValue(mockPool);
  mockGetConnection.mockResolvedValue(mockConnection);
  mockConnection.oracleServerVersion = 2_304_000_000;
  mockConnection.oracleServerVersionString = "23.4.0.0.0";
});

const describeIntegration =
  hasOracleCredentials && hasOracleDriver ? describe : describe.skip;

describeIntegration("OracleAIVectorSearch integration", () => {
  let store: InstanceType<typeof OracleAIVectorSearch>;
  const collectionName = `MEM0_TS_ORACLE_${Date.now()}_${Math.floor(Math.random() * 100000)}`;

  beforeAll(async () => {
    mockUseDriver = false;
    store = new OracleAIVectorSearch({
      connectionParams: oracleConfig,
      collectionName,
      dimension: 3,
      distanceMetric: "COSINE",
      useConnectionPool: true,
      mutateOnDuplicate: true,
      doCreateIndex: false,
    });
    await store.initialize();
    expect(mockLoadPeer).not.toHaveBeenCalled();
  });

  beforeEach(() => {
    mockUseDriver = false;
  });

  afterAll(async () => {
    if (!store) return;
    try {
      await store.deleteCol();
    } finally {
      await store.close();
    }
  });

  it("inserts, searches, filters, updates, lists, and deletes vectors", async () => {
    await store.insert(
      [
        [1, 0, 0],
        [0, 1, 0],
        [0, 0, 1],
      ],
      ["oracle-1", "oracle-2", "oracle-3"],
      [
        { category: "books", rating: 5, tags: ["ai"] },
        { category: "books", rating: 3, tags: ["db"] },
        { category: "music", rating: 4, tags: ["ai"] },
      ],
    );

    const unfilteredResults = await store.search([1, 0, 0], 2);
    expect(unfilteredResults.map((result) => result.id)).toContain("oracle-1");
    expect(unfilteredResults[0]?.score).toBeCloseTo(1, 4);

    const searchResults = await store.search([1, 0, 0], 5, {
      category: "books",
      rating: { gte: 4 },
    });
    expect(searchResults).toHaveLength(1);
    expect(searchResults[0]).toMatchObject({
      id: "oracle-1",
      payload: { category: "books", rating: 5 },
    });
    expect(searchResults[0]?.score).toBeCloseTo(1, 4);

    await store.insert(
      [[0, 0, 0.95]],
      ["oracle-3"],
      [{ category: "music", rating: 5, tags: ["ai", "upserted"] }],
    );
    expect(await store.get("oracle-3")).toMatchObject({
      payload: { category: "music", rating: 5, tags: ["ai", "upserted"] },
    });

    await store.update("oracle-1", [0.9, 0.1, 0], {
      category: "books",
      rating: 6,
      tags: ["ai", "updated"],
    });
    expect(await store.get("oracle-1")).toMatchObject({
      payload: { category: "books", rating: 6 },
    });
    expect(await store.get("missing-vector")).toBeNull();

    const [listed, count] = await store.list({ category: { in: ["books"] } });
    expect(count).toBe(2);
    expect(listed.map((result) => result.id).sort()).toEqual([
      "oracle-1",
      "oracle-2",
    ]);

    const [limited, total] = await store.list(undefined, 1);
    expect(limited).toHaveLength(1);
    expect(total).toBe(3);

    await store.delete("oracle-2");
    expect(await store.get("oracle-2")).toBeNull();
  });

  it("supports every Oracle metadata filter operator", async () => {
    await store.insert(
      [
        [1, 0, 0],
        [0, 1, 0],
        [0, 0, 1],
      ],
      ["filter-1", "filter-2", "filter-3"],
      [
        {
          filter_test: "operators",
          category: "books",
          rating: 5,
          title: "Oracle Vector Search",
          published: true,
          tags: ["oracle", "ai"],
          profile: { tier: "pro" },
          users: [{ role: "admin" }],
        },
        {
          filter_test: "operators",
          category: "books",
          rating: 3,
          title: "AI Basics",
          published: false,
          tags: ["db"],
          profile: { tier: "free" },
          users: [{ role: "reader" }],
        },
        {
          filter_test: "operators",
          category: "music",
          rating: 4,
          title: "oracle in Music",
          tags: ["ai"],
          profile: { tier: "pro" },
          users: [{ role: "editor" }],
        },
      ],
    );
    const idsFor = async (filters: SearchFilters) =>
      (
        await store.search([1, 0, 0], 10, {
          filter_test: "operators",
          ...filters,
        })
      )
        .map((result) => result.id)
        .sort();
    await expect(idsFor({ category: "books" })).resolves.toEqual([
      "filter-1",
      "filter-2",
    ]);
    await expect(idsFor({ rating: { eq: 5 } })).resolves.toEqual(["filter-1"]);
    await expect(idsFor({ rating: { ne: 5 } })).resolves.toEqual([
      "filter-2",
      "filter-3",
    ]);
    await expect(idsFor({ rating: { gt: 3 } })).resolves.toEqual([
      "filter-1",
      "filter-3",
    ]);
    await expect(idsFor({ rating: { gte: 4 } })).resolves.toEqual([
      "filter-1",
      "filter-3",
    ]);
    await expect(idsFor({ rating: { lt: 4 } })).resolves.toEqual(["filter-2"]);
    await expect(idsFor({ rating: { lte: 4 } })).resolves.toEqual([
      "filter-2",
      "filter-3",
    ]);
    await expect(idsFor({ category: { in: ["music"] } })).resolves.toEqual([
      "filter-3",
    ]);
    await expect(idsFor({ category: { nin: ["books"] } })).resolves.toEqual([
      "filter-3",
    ]);
    await expect(idsFor({ rating: { between: [4, 5] } })).resolves.toEqual([
      "filter-1",
      "filter-3",
    ]);
    await expect(idsFor({ published: { exists: true } })).resolves.toEqual([
      "filter-1",
      "filter-2",
    ]);
    await expect(idsFor({ published: { exists: false } })).resolves.toEqual([
      "filter-3",
    ]);
    await expect(idsFor({ title: { contains: "Vector" } })).resolves.toEqual([
      "filter-1",
    ]);
    await expect(idsFor({ title: { icontains: "ORACLE" } })).resolves.toEqual([
      "filter-1",
      "filter-3",
    ]);
    await expect(idsFor({ "profile.tier": "pro" })).resolves.toEqual([
      "filter-1",
      "filter-3",
    ]);
    await expect(idsFor({ "users[*].role": "admin" })).resolves.toEqual([
      "filter-1",
    ]);
    await expect(
      idsFor({ $or: [{ category: "music" }, { rating: { lt: 4 } }] }),
    ).resolves.toEqual(["filter-2", "filter-3"]);
    await expect(
      idsFor({ $and: [{ rating: { gte: 3 } }, { rating: { lte: 4 } }] }),
    ).resolves.toEqual(["filter-2", "filter-3"]);
    await expect(idsFor({ $not: [{ rating: { gte: 4 } }] })).resolves.toEqual([
      "filter-2",
    ]);
    await expect(idsFor({ category: { in: [] } })).resolves.toEqual([]);
    await expect(idsFor({ category: { nin: [] } })).resolves.toEqual([
      "filter-1",
      "filter-2",
      "filter-3",
    ]);
  });

  it("persists and restores the configured user ID", async () => {
    const originalUserId = await store.getUserId();
    const configuredUserId = `integration-user-${Date.now()}`;
    try {
      await store.setUserId(configuredUserId);
      await expect(store.getUserId()).resolves.toBe(configuredUserId);
    } finally {
      await store.setUserId(originalUserId);
    }
  });

  it("supports direct connections and converts non-cosine distance scores", async () => {
    const directCollectionName = `${collectionName}_EUCLIDEAN`;
    const directStore = new OracleAIVectorSearch({
      connectionParams: oracleConfig,
      collectionName: directCollectionName,
      dimension: 3,
      distanceMetric: "EUCLIDEAN",
      useConnectionPool: false,
      doCreateIndex: false,
    });
    try {
      await directStore.initialize();
      await directStore.insert([[1, 0, 0]], ["direct-1"], [{ kind: "direct" }]);
      const consoleError = jest.spyOn(console, "error").mockImplementation();
      try {
        await expect(
          directStore.insert(
            [[0, 1, 0]],
            ["direct-1"],
            [{ kind: "duplicate" }],
          ),
        ).rejects.toThrow("Batch insert failed on 1 record(s)");
      } finally {
        consoleError.mockRestore();
      }
      expect(await directStore.get("direct-1")).toMatchObject({
        payload: { kind: "direct" },
      });
      const results = await directStore.search([0, 1, 0], 1);
      expect(results).toHaveLength(1);
      expect(results[0]).toMatchObject({
        id: "direct-1",
        payload: { kind: "direct" },
      });
      expect(results[0]?.score).toBeCloseTo(1 / (1 + Math.sqrt(2)), 4);
    } finally {
      await directStore.deleteCol();
      await directStore.close();
    }
  });

  it("creates and uses an HNSW vector index", async () => {
    const indexedCollectionName = `${collectionName}_HNSW`;
    const indexedStore = new OracleAIVectorSearch({
      connectionParams: oracleConfig,
      collectionName: indexedCollectionName,
      dimension: 3,
      distanceMetric: "COSINE",
      indexType: "HNSW",
      doCreateIndex: true,
    });

    try {
      await indexedStore.initialize();
      await indexedStore.insert(
        [[1, 0, 0]],
        ["indexed-1"],
        [{ kind: "indexed" }],
      );

      const results = await indexedStore.search([1, 0, 0], 1);
      expect(results).toHaveLength(1);
      expect(results[0]).toMatchObject({
        id: "indexed-1",
        payload: { kind: "indexed" },
      });
      expect(results[0]?.score).toBeCloseTo(1, 4);
    } finally {
      await indexedStore.deleteCol();
      await indexedStore.close();
    }
  });

  it("creates and uses an IVF vector index after seeding vectors", async () => {
    const indexedCollectionName = `${collectionName}_IVF`;
    const seedStore = new OracleAIVectorSearch({
      connectionParams: oracleConfig,
      collectionName: indexedCollectionName,
      dimension: 3,
      distanceMetric: "COSINE",
      doCreateIndex: false,
    });
    const indexedStore = new OracleAIVectorSearch({
      connectionParams: oracleConfig,
      collectionName: indexedCollectionName,
      dimension: 3,
      distanceMetric: "COSINE",
      indexType: "IVF",
      indexAccuracy: 90,
      indexParameters: {
        neighbor_partitions: 1,
        samples_per_partition: 1,
        min_vectors_per_partition: 0,
      },
      doCreateIndex: true,
    });

    try {
      await seedStore.initialize();
      await seedStore.insert(
        [
          [1, 0, 0],
          [0, 1, 0],
          [0, 0, 1],
        ],
        ["ivf-1", "ivf-2", "ivf-3"],
        [{ kind: "ivf" }, { kind: "ivf" }, { kind: "ivf" }],
      );
      await seedStore.close();

      await indexedStore.initialize();
      const results = await indexedStore.search([1, 0, 0], 1);
      expect(results).toHaveLength(1);
      expect(results[0]?.id).toBe("ivf-1");
      expect(results[0]?.score).toBeCloseTo(1, 4);
    } finally {
      await indexedStore.deleteCol();
      await indexedStore.close();
    }
  });
});

function createStore() {
  return new OracleAIVectorSearch({
    client: mockConnection,
    collectionName: "oracle_memories",
    dimension: 3,
    doCreateIndex: false,
  });
}

const describeUnit = describe;

describeUnit("OracleAIVectorSearch unit", () => {
  beforeEach(() => {
    mockUseDriver = true;
  });
  it("creates a pool from connectionParams by default", async () => {
    const store = new OracleAIVectorSearch({
      connectionParams: {
        user: "oracle_user",
        password: "oracle_password",
        connectString: "localhost:1521/freepdb1",
        poolMin: 2,
        poolMax: 8,
      },
      collectionName: "pooled_memories",
      doCreateIndex: false,
    });

    await store.initialize();

    expect(mockCreatePool).toHaveBeenCalledWith(
      expect.objectContaining({
        user: "oracle_user",
        password: "oracle_password",
        connectString: "localhost:1521/freepdb1",
        poolMin: 2,
        poolMax: 8,
      }),
    );
    expect(mockPoolGetConnection).toHaveBeenCalled();
  });

  it("uses a direct connection when useConnectionPool is false", async () => {
    const store = new OracleAIVectorSearch({
      connectionParams: { user: "oracle_user", connectString: "db" },
      collectionName: "direct_memories",
      useConnectionPool: false,
      doCreateIndex: false,
    });

    await store.initialize();

    expect(mockGetConnection).toHaveBeenCalledWith({
      user: "oracle_user",
      connectString: "db",
    });
    expect(mockCreatePool).not.toHaveBeenCalled();
  });

  it("rejects Oracle Database versions earlier than 23.4", async () => {
    mockConnection.oracleServerVersion = 2_303_000_000;
    mockConnection.oracleServerVersionString = "23.3.0.0.0";
    const store = createStore();

    await expect(store.initialize()).rejects.toThrow(
      "Oracle DB version 23.3.0.0.0 not supported, must be >=23.4 for vector support",
    );
    expect(mockExecute).not.toHaveBeenCalled();
  });

  it("cleans up an owned pool and retries initialization after a failure", async () => {
    mockExecute.mockRejectedValueOnce(new Error("DDL Error"));
    const store = new OracleAIVectorSearch({
      connectionParams: { user: "oracle_user", connectString: "db" },
      collectionName: "retry_memories",
      doCreateIndex: false,
    });

    await expect(store.initialize()).rejects.toThrow("DDL Error");
    expect(mockPoolClose).toHaveBeenCalledTimes(1);

    await expect(store.initialize()).resolves.toBeUndefined();
    expect(mockCreatePool).toHaveBeenCalledTimes(2);
  });

  it("uses a caller-provided pool", async () => {
    const store = new OracleAIVectorSearch({
      client: mockPool,
      collectionName: "provided_pool_memories",
      doCreateIndex: false,
    });

    await store.initialize();

    expect(mockPoolGetConnection).toHaveBeenCalled();
    expect(mockCreatePool).not.toHaveBeenCalled();
  });

  it("loads the optional driver through its default module export", async () => {
    mockLoadPeer.mockResolvedValueOnce({ default: mockDriver });
    const store = createStore();

    await store.initialize();

    expect(mockLoadPeer).toHaveBeenCalled();
  });

  it("applies index and distance configuration to generated SQL", async () => {
    const store = new OracleAIVectorSearch({
      client: mockConnection,
      collectionName: "configured_memories",
      dimension: 8,
      distanceMetric: "DOT",
      doCreateIndex: true,
      indexType: "IVF",
      indexName: "configured_idx",
      indexAccuracy: 90,
      indexParameters: {
        neighbor_partitions: 8,
        samples_per_partition: 16,
        min_vectors_per_partition: 2,
      },
    });

    await store.initialize();
    await store.search(new Array(8).fill(0.1));

    expect(mockExecute).toHaveBeenCalledWith(
      expect.stringContaining(
        'CREATE VECTOR INDEX IF NOT EXISTS "configured_idx"',
      ),
    );
    expect(mockExecute).toHaveBeenCalledWith(
      expect.stringContaining(
        "ORGANIZATION NEIGHBOR PARTITIONS DISTANCE DOT WITH TARGET ACCURACY 90",
      ),
    );
    expect(mockExecute).toHaveBeenCalledWith(
      expect.stringContaining(
        "PARAMETERS (type IVF, neighbor partitions 8, samples_per_partition 16, min_vectors_per_partition 2)",
      ),
    );
    expect(mockExecute).toHaveBeenLastCalledWith(
      expect.stringContaining("VECTOR_DISTANCE(vector, :query_vector, DOT)"),
      expect.any(Object),
      expect.any(Object),
    );
  });

  it("validates all constrained configuration values", () => {
    const baseConfig = {
      client: mockConnection,
      collectionName: "valid_memories",
    };

    expect(
      () => new OracleAIVectorSearch({ ...baseConfig, dimension: 0 }),
    ).toThrow("dimension");
    expect(
      () =>
        new OracleAIVectorSearch({
          ...baseConfig,
          distanceMetric: "INVALID" as "COSINE",
        }),
    ).toThrow("distance metric");
    expect(
      () =>
        new OracleAIVectorSearch({
          ...baseConfig,
          indexType: "INVALID" as "HNSW",
        }),
    ).toThrow("index type");
    expect(
      () =>
        new OracleAIVectorSearch({
          ...baseConfig,
          indexParameters: { unsupported: 1 },
        }),
    ).toThrow("Unsupported HNSW index parameter");
    expect(
      () => new OracleAIVectorSearch({ ...baseConfig, indexAccuracy: 101 }),
    ).toThrow("indexAccuracy");
    expect(
      () =>
        new OracleAIVectorSearch({
          ...baseConfig,
          indexParameters: { neighbors: 1 },
        }),
    ).toThrow("indexParameters.neighbors");
    expect(
      () =>
        new OracleAIVectorSearch({
          ...baseConfig,
          indexType: "IVF",
          indexParameters: { samples_per_partition: 0 },
        }),
    ).toThrow("indexParameters.samples_per_partition must be an integer >= 1");
    expect(
      () =>
        new OracleAIVectorSearch({
          ...baseConfig,
          distanceMetric: 42 as unknown as "COSINE",
        }),
    ).toThrow("Unsupported Oracle distance metric: 42");
    expect(
      () =>
        new OracleAIVectorSearch({
          ...baseConfig,
          collectionName: null as unknown as string,
        }),
    ).not.toThrow();
    expect(
      () =>
        new OracleAIVectorSearch({
          ...baseConfig,
          collectionName: "",
        }),
    ).toThrow("collectionName cannot be empty");
    expect(() => new OracleAIVectorSearch()).toThrow(
      "Must provide at least one of `connectionParams` and `client`",
    );
    expect(() => new OracleAIVectorSearch({ connectionParams: {} })).toThrow(
      "Must provide at least one of `connectionParams` and `client`",
    );
  });

  it("normalizes case and applies nullish metric and index defaults", () => {
    expect(
      () =>
        new OracleAIVectorSearch({
          client: mockConnection,
          collectionName: "normalized_memories",
          distanceMetric: "cosine" as unknown as "COSINE",
          indexType: "ivf" as unknown as "HNSW",
        }),
    ).not.toThrow();
    expect(
      () =>
        new OracleAIVectorSearch({
          client: mockConnection,
          collectionName: "nullish_defaults_memories",
          distanceMetric: null as unknown as "COSINE",
          indexType: null as unknown as "HNSW",
        }),
    ).not.toThrow();
  });

  it("defensively validates index parameters if configuration is mutated", async () => {
    const config = {
      client: mockConnection,
      collectionName: "mutated_index_memories",
      doCreateIndex: true,
      indexParameters: { neighbors: 2 },
    };
    const invalidValueStore = new OracleAIVectorSearch(config);
    config.indexParameters = { neighbors: -1 };
    await expect(invalidValueStore.initialize()).rejects.toThrow(
      "indexParameters.neighbors must be an integer between 2 and 2048",
    );

    const extraConfig: {
      client: typeof mockConnection;
      collectionName: string;
      doCreateIndex: boolean;
      indexParameters: Record<string, number>;
    } = {
      ...config,
      collectionName: "mutated_extra_index_memories",
      indexParameters: { neighbors: 2 },
    };
    const unsupportedKeyStore = new OracleAIVectorSearch(extraConfig);
    extraConfig.indexParameters = { neighbors: 2, unsupported: 1 };
    await expect(unsupportedKeyStore.initialize()).rejects.toThrow(
      "Unsupported HNSW index parameter: unsupported",
    );
  });

  it("renders validated HNSW index parameters", async () => {
    const store = new OracleAIVectorSearch({
      client: mockConnection,
      collectionName: "hnsw_memories",
      doCreateIndex: true,
      indexType: "HNSW",
      indexParameters: { neighbors: 32, efconstruction: 200 },
    });

    await store.initialize();

    expect(mockExecute).toHaveBeenCalledWith(
      expect.stringContaining(
        "PARAMETERS (type HNSW, neighbors 32, efconstruction 200)",
      ),
    );
  });

  it("creates the vector and migration tables during initialization", async () => {
    const store = createStore();

    await store.initialize();

    expect(mockLoadPeer).toHaveBeenCalledWith(
      "oracledb",
      "Oracle AI Vector Search",
      expect.any(Function),
    );
    expect(mockExecute).toHaveBeenCalledWith(
      expect.stringContaining('CREATE TABLE IF NOT EXISTS "oracle_memories"'),
    );
    expect(mockExecute).toHaveBeenCalledWith(
      expect.stringContaining(
        "CREATE TABLE IF NOT EXISTS mem0_oracle_migrations",
      ),
    );
    // Oracle DDL commits implicitly; createCol and createMigrationTable do not
    // issue redundant explicit commits.
    expect(mockCommit).not.toHaveBeenCalled();
  });

  it("binds Float32 vectors and payloads using Oracle vector and JSON types", async () => {
    const store = createStore();
    await store.initialize();
    mockCommit.mockClear();

    await store.insert([[0.1, 0.2, 0.3]], ["memory-1"], [{ topic: "oracle" }]);

    expect(mockExecuteMany).toHaveBeenCalledWith(
      expect.stringContaining('INSERT INTO "oracle_memories"'),
      [["memory-1", expect.any(Float32Array), { topic: "oracle" }]],
      expect.objectContaining({
        bindDefs: [
          { type: "STRING", maxSize: 36 },
          { type: "VECTOR" },
          { type: "JSON" },
        ],
      }),
    );
    expect(mockCommit).toHaveBeenCalledTimes(1);
  });

  it("rejects insert batches with mismatched IDs or payloads", async () => {
    const store = createStore();

    await expect(store.insert([[0.1, 0.2, 0.3]], [])).rejects.toThrow(
      "ids and vectors must have the same length",
    );
    await expect(
      store.insert(
        [
          [0.1, 0.2, 0.3],
          [0.4, 0.5, 0.6],
        ],
        ["memory-1", "memory-2"],
        [{ topic: "oracle" }],
      ),
    ).rejects.toThrow("payloads must be empty or match vectors length");
    expect(mockLoadPeer).not.toHaveBeenCalled();
  });

  it("uses MERGE only when mutateOnDuplicate is enabled", async () => {
    const store = new OracleAIVectorSearch({
      client: mockConnection,
      collectionName: "upsert_memories",
      dimension: 3,
      doCreateIndex: false,
      mutateOnDuplicate: true,
    });

    await store.insert([[0.1, 0.2, 0.3]], ["memory-1"], [{ topic: "oracle" }]);

    expect(mockExecuteMany).toHaveBeenCalledWith(
      expect.stringContaining('MERGE INTO "upsert_memories"'),
      expect.any(Array),
      expect.any(Object),
    );
  });

  it("rejects a batch insert with Oracle batch errors", async () => {
    const store = createStore();
    await store.initialize();
    mockCommit.mockClear();
    mockExecuteMany.mockResolvedValueOnce({
      batchErrors: [
        { offset: 0, message: "invalid vector" },
        { message: "missing offset" },
      ],
    });
    const consoleError = jest.spyOn(console, "error").mockImplementation();

    try {
      await expect(
        store.insert(
          [
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
          ],
          ["memory-1", "memory-2"],
        ),
      ).rejects.toThrow("Batch insert failed on 2 record(s)");

      expect(mockCommit).not.toHaveBeenCalled();
      expect(mockRollback).toHaveBeenCalledTimes(1);
    } finally {
      consoleError.mockRestore();
    }
  });

  it("releases a pooled connection when an operation fails", async () => {
    const store = new OracleAIVectorSearch({
      connectionParams: { user: "oracle_user", connectString: "db" },
      collectionName: "pooled_error_memories",
      doCreateIndex: false,
    });
    await store.initialize();
    mockClose.mockClear();
    mockExecuteMany.mockResolvedValueOnce({
      batchErrors: [{ offset: 0, message: "invalid vector" }],
    });
    const consoleError = jest.spyOn(console, "error").mockImplementation();
    try {
      await expect(
        store.insert([[0.1, 0.2, 0.3]], ["memory-1"]),
      ).rejects.toThrow("Batch insert failed on 1 record(s)");

      expect(mockClose).toHaveBeenCalledTimes(1);
      expect(mockRollback).not.toHaveBeenCalled();
    } finally {
      consoleError.mockRestore();
    }
  });

  it("uses JSON_EXISTS filters and converts cosine distance to similarity", async () => {
    mockExecute.mockResolvedValueOnce({ rows: [] });
    mockExecute.mockResolvedValueOnce({ rows: [] });
    mockExecute.mockResolvedValueOnce({
      rows: [["memory-1", Buffer.from('{"topic":"oracle"}'), 0.125]],
    });
    const store = createStore();

    const results = await store.search([0.1, 0.2, 0.3], 1, {
      topic: "oracle",
    });

    expect(results).toEqual([
      { id: "memory-1", payload: { topic: "oracle" }, score: 0.875 },
    ]);
    expect(mockExecute).toHaveBeenLastCalledWith(
      expect.stringContaining("JSON_EXISTS(payload"),
      expect.objectContaining({ filter_0: "oracle", limit: 1 }),
      { outFormat: "ARRAY" },
    );
    expect(mockExecute.mock.calls.at(-1)?.[0]).not.toContain(
      "VECTOR_INDEX_TRANSFORM",
    );
    expect(mockExecute.mock.calls.at(-1)?.[0]).toContain(
      "FETCH APPROX FIRST :limit ROWS ONLY",
    );
    expect(mockExecute.mock.calls.at(-1)?.[0]).toContain("ORDER BY distance");
  });

  it("converts Oracle distances to higher-is-better scores", async () => {
    mockExecute.mockResolvedValueOnce({ rows: [] });
    mockExecute.mockResolvedValueOnce({ rows: [] });
    mockExecute.mockResolvedValueOnce({
      rows: [["memory-1", { topic: "oracle" }, 0.125]],
    });
    const store = new OracleAIVectorSearch({
      client: mockConnection,
      collectionName: "oracle_memories",
      dimension: 3,
      distanceMetric: "EUCLIDEAN",
      doCreateIndex: false,
    });

    const results = await store.search([0.1, 0.2, 0.3], 1);

    expect(results[0]?.score).toBeCloseTo(1 / 1.125, 6);

    mockExecute
      .mockResolvedValueOnce({ rows: [] })
      .mockResolvedValueOnce({ rows: [] })
      .mockResolvedValueOnce({
        rows: [["memory-1", { topic: "oracle" }, -0.75]],
      });
    const dotStore = new OracleAIVectorSearch({
      client: mockConnection,
      collectionName: "oracle_dot_memories",
      dimension: 3,
      distanceMetric: "DOT",
      doCreateIndex: false,
    });

    const dotResults = await dotStore.search([0.1, 0.2, 0.3], 1);
    expect(dotResults[0]?.score).toBe(0.75);

    mockExecute
      .mockResolvedValueOnce({ rows: [] })
      .mockResolvedValueOnce({ rows: [] })
      .mockResolvedValueOnce({
        rows: [["memory-1", { topic: "oracle" }, 2]],
      });
    const cosineStore = new OracleAIVectorSearch({
      client: mockConnection,
      collectionName: "oracle_cosine_memories",
      dimension: 3,
      distanceMetric: "COSINE",
      doCreateIndex: false,
    });

    const cosineResults = await cosineStore.search([0.1, 0.2, 0.3], 1);
    expect(cosineResults[0]?.score).toBe(0);
  });

  it("uses VECTOR_INDEX_TRANSFORM for unfiltered searches", async () => {
    mockExecute.mockResolvedValueOnce({ rows: [] });
    mockExecute.mockResolvedValueOnce({ rows: [] });
    mockExecute.mockResolvedValueOnce({ rows: [] });
    const store = createStore();

    await store.search([0.1, 0.2, 0.3], 1);

    expect(mockExecute.mock.calls.at(-1)?.[0]).toContain(
      'SELECT /*+ VECTOR_INDEX_TRANSFORM("oracle_memories") */',
    );
    expect(mockExecute.mock.calls.at(-1)?.[0]).toContain(
      "FETCH APPROX FIRST :limit ROWS ONLY",
    );
  });

  it("uses VECTOR_INDEX_TRANSFORM when given an empty filter object", async () => {
    const store = createStore();

    await store.search([0.1, 0.2, 0.3], 1, {});

    expect(mockExecute.mock.calls.at(-1)?.[0]).toContain(
      'SELECT /*+ VECTOR_INDEX_TRANSFORM("oracle_memories") */',
    );
  });

  it("rejects unsafe collection and metadata filter keys", async () => {
    expect(
      () =>
        new OracleAIVectorSearch({
          client: mockConnection,
          collectionName: "memories; DROP TABLE users",
        }),
    ).toThrow("Invalid Oracle identifier");

    const store = createStore();
    await expect(
      store.search([0.1, 0.2, 0.3], 1, { "bad-key": "x" }),
    ).rejects.toThrow("Invalid Oracle metadata filter key");

    await expect(
      store.search([0.1, 0.2, 0.3], 1, { "display name,alias": "x" }),
    ).resolves.toEqual([]);
  });

  it("is available through the vector store factory", () => {
    const { VectorStoreFactory } = require("../src/utils/factory");
    const store = VectorStoreFactory.create("oracledb", {
      client: mockConnection,
      collectionName: "factory_memories",
    });

    expect(store).toBeInstanceOf(OracleAIVectorSearch);
  });

  it("rolls back a direct connection if creation fails", async () => {
    mockExecute.mockRejectedValueOnce(new Error("DDL Error"));
    const store = createStore();

    await expect(store.initialize()).rejects.toThrow("DDL Error");
    expect(mockRollback).toHaveBeenCalledTimes(1);
  });

  it("returns a clear error when the migration user ID row is absent", async () => {
    const store = createStore();
    await store.initialize();
    mockExecute.mockClear();
    mockExecute
      .mockResolvedValueOnce({ rows: [] })
      .mockResolvedValueOnce({ rows: [] });

    await expect(store.getUserId()).rejects.toThrow(
      "Failed to retrieve user_id from migration table",
    );
  });

  it("reads the winning user ID after a concurrent migration insert", async () => {
    const store = createStore();
    await store.initialize();
    mockExecute.mockClear();
    mockExecute
      .mockRejectedValueOnce(
        Object.assign(new Error("ORA-00001: unique constraint violated"), {
          errorNum: 1,
        }),
      )
      .mockResolvedValueOnce({ rows: [["concurrent-user"]] });

    await expect(store.getUserId()).resolves.toBe("concurrent-user");
  });

  it("does not close caller-provided connections", async () => {
    const store = createStore();
    await store.close();

    // A caller-provided connection remains owned by the caller. Connections
    // acquired from pools are released by withConnection(), and self-created
    // clients are closed by close().
    expect(mockClose).not.toHaveBeenCalled();
  });

  it("closes an owned pool at most once", async () => {
    const store = new OracleAIVectorSearch({
      connectionParams: { user: "oracle_user", connectString: "db" },
      collectionName: "close_once_memories",
      doCreateIndex: false,
    });
    await store.initialize();

    await Promise.all([store.close(), store.close()]);
    await store.close();

    expect(mockPoolClose).toHaveBeenCalledTimes(1);
  });

  it("handles nested metadata filter keys", async () => {
    const store = createStore();
    await store.search([0.1, 0.2, 0.3], 1, { "user.id": "123" });

    expect(mockExecute).toHaveBeenLastCalledWith(
      expect.stringContaining(
        'JSON_EXISTS(payload, \'$."user"."id"?(@ == $filter_0)\'',
      ),
      expect.objectContaining({ filter_0: "123" }),
      expect.any(Object),
    );
  });

  it("supports compatible comparison, membership, and boolean filters", async () => {
    const store = createStore();
    await store.search([0.1, 0.2, 0.3], 5, {
      $or: [
        { category: { in: ["books", "games"] } },
        { price: { gte: 10, lte: 20 } },
      ],
      status: { nin: ["archived", "deleted"] },
      title: { icontains: "Oracle" },
      author: ["Alice", "Bob"],
      hidden: { exists: false },
    });

    const [sql, binds] = mockExecute.mock.calls.at(-1);
    expect(sql).toContain(" OR ");
    expect(sql).toContain(" AND ");
    expect(sql).toContain("@ >= $filter_2");
    expect(sql).toContain("@ <= $filter_3");
    expect(sql).toContain("LOWER(JSON_VALUE(payload");
    expect(sql).toContain("NOT JSON_EXISTS(payload, '$.\"hidden\"')");
    expect(binds).toMatchObject({
      filter_0: "books",
      filter_1: "games",
      filter_2: 10,
      filter_3: 20,
      filter_4: "archived",
      filter_5: "deleted",
      filter_6: "%Oracle%",
      filter_7: "Alice",
      filter_8: "Bob",
      limit: 5,
    });
  });

  it("supports negated groups, between, and rejects invalid operators", async () => {
    const store = createStore();
    await store.search([0.1, 0.2, 0.3], 1, {
      $not: [{ rating: { between: [3, 5] } }, { category: "restricted" }],
    });

    const [sql, binds] = mockExecute.mock.calls.at(-1);
    expect(sql).toContain("NOT ((JSON_EXISTS(payload");
    expect(binds).toMatchObject({
      filter_0: 3,
      filter_1: 5,
      filter_2: "restricted",
    });

    await expect(
      store.search([0.1, 0.2, 0.3], 1, { rating: { unsupported: 1 } }),
    ).rejects.toThrow("Unsupported filter operator: unsupported");
  });

  it("supports every remaining filter operator and shorthand", async () => {
    const store = createStore();
    await store.search([0.1, 0.2, 0.3], 1, {
      $and: [{ visible: "*" }, { score: { $eq: 7, ne: 0, gt: 1, lt: 10 } }],
      title: { contains: "100%_coverage\\check" },
      published: { exists: true },
      emptyIn: { in: [] },
      emptyNin: { nin: [] },
    });

    const [sql, binds] = mockExecute.mock.calls.at(-1);
    expect(sql).toContain("JSON_EXISTS(payload, '$.\"visible\"')");
    expect(sql).toContain("@ == $filter_0");
    expect(sql).toContain("@ != $filter_1");
    expect(sql).toContain("@ > $filter_2");
    expect(sql).toContain("@ < $filter_3");
    expect(sql).toContain(
      "JSON_VALUE(payload, '$.\"title\"' RETURNING VARCHAR2(4000)) LIKE",
    );
    expect(sql).toContain("JSON_EXISTS(payload, '$.\"published\"')");
    expect(sql).toContain("1 = 0");
    expect(sql).toContain("1 = 1");
    expect(binds).toMatchObject({
      filter_0: 7,
      filter_1: 0,
      filter_2: 1,
      filter_3: 10,
      filter_4: "%100\\%\\_coverage\\\\check%",
    });
  });

  it("validates logical and operator filter values", async () => {
    const store = createStore();
    const invalidFilters = [
      { $or: { category: "books" } },
      { category: { in: "books" } },
      { category: { nin: "books" } },
      { price: { between: [1] } },
      { published: { exists: "yes" } },
      { $and: [] },
    ];

    for (const filters of invalidFilters) {
      await expect(store.search([0.1, 0.2, 0.3], 1, filters)).rejects.toThrow();
    }
  });

  it("applies translated filters to the combined list query", async () => {
    const store = createStore();
    await store.list({ category: { eq: "books" } }, 10);

    const [sql, binds] = mockExecute.mock.calls.at(-1);
    expect(sql).toContain("JSON_EXISTS(payload");
    expect(sql).toContain("COUNT(*) OVER() AS total_count");
    expect(binds).toMatchObject({ filter_0: "books" });
  });

  it("returns list rows and the total from one query", async () => {
    const store = createStore();
    await store.initialize();
    mockExecute.mockClear();
    mockExecute.mockResolvedValueOnce({
      rows: [["memory-1", { topic: "oracle" }, 2]],
    });

    await expect(store.list(undefined, 1)).resolves.toEqual([
      [{ id: "memory-1", payload: { topic: "oracle" } }],
      2,
    ]);
    expect(mockExecute).toHaveBeenCalledTimes(1);
  });

  it("supports array-wildcard paths without interpolating filter values", async () => {
    const store = createStore();
    await store.search([0.1, 0.2, 0.3], 1, {
      "users[*].role": "admin'); DROP TABLE mem0; --",
    });

    const [sql, binds] = mockExecute.mock.calls.at(-1);
    expect(sql).toContain(
      'JSON_EXISTS(payload, \'$."users"[*]."role"?(@ == $filter_0)\'',
    );
    expect(sql).not.toContain("DROP TABLE");
    expect(binds).toMatchObject({
      filter_0: "admin'); DROP TABLE mem0; --",
    });
  });
});
