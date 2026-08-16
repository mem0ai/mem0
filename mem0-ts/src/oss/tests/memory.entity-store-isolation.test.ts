/**
 * The entity store must never resolve to the memory store's own storage.
 *
 * getEntityStore() renames only `collectionName`. Supabase and Baidu name their
 * table with `tableName`, Vectorize names its index with `indexName`, and none
 * of the three read `collectionName`, so the entity store used to open the exact
 * table the memories live in. Every extracted entity was then written into the
 * user's memory collection and came back out of search() and getAll().
 */
/// <reference types="jest" />

const mockCreatedConfigs: any[] = [];

const mockStoreStub = (config: any) => {
  mockCreatedConfigs.push(config);
  return {
    initialize: jest.fn().mockResolvedValue(undefined),
    insert: jest.fn().mockResolvedValue(undefined),
    search: jest.fn().mockResolvedValue([]),
    list: jest.fn().mockResolvedValue([[], 0]),
    get: jest.fn().mockResolvedValue(null),
    update: jest.fn().mockResolvedValue(undefined),
    delete: jest.fn().mockResolvedValue(undefined),
    deleteCol: jest.fn().mockResolvedValue(undefined),
    getUserId: jest.fn().mockResolvedValue("u"),
    setUserId: jest.fn().mockResolvedValue(undefined),
    initializeUserId: jest.fn().mockResolvedValue(undefined),
    keywordSearch: jest.fn().mockResolvedValue(null),
  };
};

jest.mock("../src/vector_stores/supabase", () => ({
  SupabaseDB: jest.fn().mockImplementation(mockStoreStub),
}));
jest.mock("../src/vector_stores/baidu", () => ({
  BaiduDB: jest.fn().mockImplementation(mockStoreStub),
}));
jest.mock("../src/vector_stores/vectorize", () => ({
  VectorizeDB: jest.fn().mockImplementation(mockStoreStub),
}));
jest.mock("../src/vector_stores/databricks", () => ({
  DatabricksVectorStore: jest.fn().mockImplementation(mockStoreStub),
}));
jest.mock("../src/vector_stores/memory", () => ({
  MemoryVectorStore: jest.fn().mockImplementation(mockStoreStub),
}));
jest.mock("../src/utils/telemetry", () => ({
  captureClientEvent: jest.fn(),
  captureEvent: jest.fn(),
  isTelemetryEnabled: () => false,
  telemetry: { captureEvent: jest.fn() },
}));

import { Memory } from "../src/memory";

async function configsFor(provider: string, storeConfig: any) {
  mockCreatedConfigs.length = 0;
  const m: any = new Memory({
    vectorStore: { provider, config: { dimension: 8, ...storeConfig } },
    historyDbPath: ":memory:",
  } as any);
  await m._ensureInitialized();
  await m.getEntityStore();
  return mockCreatedConfigs;
}

describe("entity store does not share storage with the memory store", () => {
  it("supabase: entity table is separate from the memory table", async () => {
    const [memoryCfg, entityCfg] = await configsFor("supabase", {
      collectionName: "memories",
      tableName: "memories",
      supabaseUrl: "https://x.supabase.co",
      supabaseKey: "k",
    });
    expect(memoryCfg.tableName).toBe("memories");
    expect(entityCfg.tableName).toBe("memories_entities");
  });

  it("baidu: entity table is separate from the memory table", async () => {
    const [memoryCfg, entityCfg] = await configsFor("baidu", {
      collectionName: "memories",
      tableName: "memories",
      endpoint: "e",
      account: "a",
      apiKey: "k",
    });
    expect(memoryCfg.tableName).toBe("memories");
    expect(entityCfg.tableName).toBe("memories_entities");
  });

  it("vectorize: entity index is separate from the memory index", async () => {
    const [memoryCfg, entityCfg] = await configsFor("vectorize", {
      collectionName: "memories",
      indexName: "memories",
      accountId: "a",
      apiKey: "k",
    });
    expect(memoryCfg.indexName).toBe("memories");
    expect(entityCfg.indexName).toBe("memories_entities");
  });

  it("memory: entity db is separate even when dbPath does not end in .db", async () => {
    const [memoryCfg, entityCfg] = await configsFor("memory", {
      collectionName: "memories",
      dbPath: "/tmp/mem0-isolation/store.sqlite",
    });
    expect(memoryCfg.dbPath).toBe("/tmp/mem0-isolation/store.sqlite");
    expect(entityCfg.dbPath).not.toBe(memoryCfg.dbPath);
  });

  it("memory: existing .db naming is unchanged", async () => {
    const [, entityCfg] = await configsFor("memory", {
      collectionName: "memories",
      dbPath: "/tmp/mem0-isolation/store.db",
    });
    expect(entityCfg.dbPath).toBe("/tmp/mem0-isolation/store_entities.db");
  });

  it("databricks: existing naming is unchanged", async () => {
    const [, withTable] = await configsFor("databricks", {
      collectionName: "memories",
      tableName: "memories",
      workspaceUrl: "w",
      token: "t",
      endpointName: "e",
    });
    expect(withTable.tableName).toBe("memories_entities");

    const [, withoutTable] = await configsFor("databricks", {
      collectionName: "memories",
      workspaceUrl: "w",
      token: "t",
      endpointName: "e",
    });
    expect(withoutTable.tableName).toBe("memories_entities");
  });
});
