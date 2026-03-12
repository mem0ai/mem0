/// <reference types="jest" />
/**
 * End-to-end tests for Qdrant dimension mismatch fix.
 *
 * Requires a running Qdrant instance at localhost:6333 (v1.13.x).
 * These tests replicate the exact scenarios from issues #4212, #4173, #4056.
 *
 * Skipped automatically when Qdrant is not available.
 *
 * Run: npx jest --config jest.config.js src/oss/tests/qdrant-e2e.test.ts --forceExit
 */

import { QdrantClient } from "@qdrant/js-client-rest";
import { Qdrant } from "../src/vector_stores/qdrant";
import { v4 as uuidv4 } from "uuid";
jest.setTimeout(30000);

const QDRANT_HOST = "localhost";
const QDRANT_PORT = 6333;

// Check if Qdrant is reachable synchronously at load time using
// a sync check via child_process so describe.skip works correctly.
function isQdrantAvailable(): boolean {
  try {
    const { execSync } = require("child_process");
    execSync(
      `node -e "const s=require('net').createConnection({host:'${QDRANT_HOST}',port:${QDRANT_PORT}});s.on('connect',()=>{s.destroy();process.exit(0)});s.on('error',()=>process.exit(1));s.setTimeout(2000,()=>process.exit(1))"`,
      { timeout: 3000, stdio: "ignore" },
    );
    return true;
  } catch {
    return false;
  }
}

const qdrantAvailable = isQdrantAvailable();
if (!qdrantAvailable) {
  console.warn("Qdrant not available at localhost:6333 — skipping e2e tests");
}

let qdrantClient: QdrantClient;

beforeAll(async () => {
  if (!qdrantAvailable) return;
  qdrantClient = new QdrantClient({ host: QDRANT_HOST, port: QDRANT_PORT });
  const collections = await qdrantClient.getCollections();
  expect(collections).toBeDefined();
});

// Helper: delete a collection if it exists
async function deleteCollectionIfExists(name: string) {
  try {
    await qdrantClient.deleteCollection(name);
  } catch {
    // Collection doesn't exist — fine
  }
}

// Helper: create a fake embedder that produces vectors of a given dimension
function createFakeEmbedder(dims: number) {
  return {
    embed: jest.fn().mockImplementation(async (_text: string) => {
      const vec = new Array(dims).fill(0);
      for (let i = 0; i < _text.length && i < dims; i++) {
        vec[i] = _text.charCodeAt(i) / 255;
      }
      return vec;
    }),
    embedBatch: jest.fn().mockImplementation(async (texts: string[]) => {
      return Promise.all(
        texts.map(async (t) => {
          const vec = new Array(dims).fill(0);
          for (let i = 0; i < t.length && i < dims; i++) {
            vec[i] = t.charCodeAt(i) / 255;
          }
          return vec;
        }),
      );
    }),
  };
}

// Conditionally skip tests when Qdrant is unavailable
const describeIfQdrant = qdrantAvailable ? describe : describe.skip;

afterAll(async () => {
  await deleteCollectionIfExists("e2e_test_768");
  await deleteCollectionIfExists("e2e_test_1536");
  await deleteCollectionIfExists("e2e_test_race");
  await deleteCollectionIfExists("e2e_test_race2");
  await deleteCollectionIfExists("e2e_test_noexplicit");
  await deleteCollectionIfExists("e2e_test_explicit");
  await deleteCollectionIfExists("e2e_test_embdims");
  await deleteCollectionIfExists("e2e_test_autodetect");
  await deleteCollectionIfExists("memory_migrations");
});

// ───────────────────────────────────────────────────────────────────────────
// 1. Reproduce #4212 / #4173: dimension mismatch with 768-dim embedder
// ───────────────────────────────────────────────────────────────────────────
describeIfQdrant("Issue #4212/#4173: Qdrant dimension mismatch", () => {
  it("BEFORE FIX scenario: 768-dim vector into 1536-dim collection → Bad Request", async () => {
    const collectionName = "e2e_test_1536";
    await deleteCollectionIfExists(collectionName);
    await qdrantClient.createCollection(collectionName, {
      vectors: { size: 1536, distance: "Cosine" },
    });

    // Insert a 768-dim vector — this is what nomic-embed-text produces
    const vector768 = new Array(768).fill(0.1);
    try {
      await qdrantClient.upsert(collectionName, {
        points: [
          { id: "test-1", vector: vector768, payload: { data: "hello" } },
        ],
      });
      fail("Expected Qdrant to reject 768-dim vector into 1536-dim collection");
    } catch (error: any) {
      // This is the exact "Bad Request" error users were hitting
      expect(error.status).toBe(400);
    }

    await deleteCollectionIfExists(collectionName);
  });

  it("AFTER FIX: Qdrant store with dimension=768 works end-to-end", async () => {
    const collectionName = "e2e_test_768";
    await deleteCollectionIfExists(collectionName);
    await deleteCollectionIfExists("memory_migrations");

    // Create Qdrant store with correct dimension (what our auto-detect provides)
    const store = new Qdrant({
      host: QDRANT_HOST,
      port: QDRANT_PORT,
      collectionName,
      embeddingModelDims: 768,
      dimension: 768,
    });
    await store.initialize();

    // Verify collection was created with 768 dims
    const info = await qdrantClient.getCollection(collectionName);
    expect(info.config?.params?.vectors?.size).toBe(768);

    // Insert 768-dim vectors (what nomic-embed-text produces)
    const vec1 = new Array(768).fill(0);
    vec1[0] = 1.0;
    const vec2 = new Array(768).fill(0);
    vec2[1] = 1.0;

    const id1 = uuidv4();
    const id2 = uuidv4();

    await store.insert([vec1, vec2], [id1, id2], [
      { data: "hello", userId: "u1" },
      { data: "world", userId: "u1" },
    ]);

    // Search with 768-dim query — this USED TO fail with Bad Request
    const results = await store.search(vec1, 2, { userId: "u1" });
    expect(results.length).toBe(2);
    expect(results[0].id).toBe(id1); // Most similar to itself
    expect(results[0].score).toBeGreaterThan(0.9);

    // Get by ID
    const item = await store.get(id1);
    expect(item).not.toBeNull();
    expect(item!.payload.data).toBe("hello");

    // Update with 768-dim vector
    const vec3 = new Array(768).fill(0);
    vec3[2] = 1.0;
    await store.update(id1, vec3, { data: "updated", userId: "u1" });
    const updated = await store.get(id1);
    expect(updated!.payload.data).toBe("updated");

    // Delete
    await store.delete(id2);
    const deleted = await store.get(id2);
    expect(deleted).toBeNull();

    // List
    const [listed, count] = await store.list({ userId: "u1" });
    expect(count).toBe(1);
    expect(listed[0].payload.data).toBe("updated");

    await deleteCollectionIfExists(collectionName);
    await deleteCollectionIfExists("memory_migrations");
  });

  it("AFTER FIX: Memory auto-detects 768 dims via probe (full integration)", async () => {
    const collectionName = "e2e_test_autodetect";
    await deleteCollectionIfExists(collectionName);
    await deleteCollectionIfExists("memory_migrations");

    const fakeEmbedder = createFakeEmbedder(768);

    // Mock only the non-Qdrant factories to avoid Google SDK import crash
    jest.resetModules();
    jest.doMock("../src/utils/factory", () => {
      // Import Qdrant directly (avoids loading Google embedder via factory)
      const { Qdrant: QdrantStore } = require("../src/vector_stores/qdrant");
      return {
        EmbedderFactory: { create: jest.fn().mockReturnValue(fakeEmbedder) },
        VectorStoreFactory: {
          create: jest.fn().mockImplementation((_provider: string, config: any) => {
            return new QdrantStore(config);
          }),
        },
        LLMFactory: {
          create: jest.fn().mockReturnValue({
            generateResponse: jest.fn().mockResolvedValue('{"facts":[]}'),
          }),
        },
        HistoryManagerFactory: {
          create: jest.fn().mockReturnValue({
            addHistory: jest.fn().mockResolvedValue(undefined),
            getHistory: jest.fn().mockResolvedValue([]),
            reset: jest.fn().mockResolvedValue(undefined),
          }),
        },
      };
    });

    jest.doMock("../src/utils/telemetry", () => ({
      captureClientEvent: jest.fn().mockResolvedValue(undefined),
    }));

    const { Memory } = require("../src/memory");

    // This is the EXACT config from issue #4212 — NO dimension specified
    const mem = new Memory({
      embedder: {
        provider: "ollama",
        config: { model: "nomic-embed-text" },
      },
      vectorStore: {
        provider: "qdrant",
        config: {
          host: QDRANT_HOST,
          port: QDRANT_PORT,
          collectionName,
        },
      },
      llm: { provider: "openai", config: { apiKey: "fake" } },
      disableHistory: true,
    });

    // This triggers init — probe should detect 768 dims
    await mem.getAll({ userId: "test-user" });

    // Verify the probe was called
    expect(fakeEmbedder.embed).toHaveBeenCalledWith("dimension probe");

    // Verify Qdrant collection was created with auto-detected 768 dims
    const collectionInfo = await qdrantClient.getCollection(collectionName);
    expect(collectionInfo.config?.params?.vectors?.size).toBe(768);

    // Search should work (this used to throw Bad Request)
    const searchResult = await mem.search("hello world", {
      userId: "test-user",
    });
    expect(searchResult).toBeDefined();

    await deleteCollectionIfExists(collectionName);
    await deleteCollectionIfExists("memory_migrations");
    jest.resetModules();
  });

  it("AFTER FIX: explicit dimension=768 skips probe (backward compat)", async () => {
    const collectionName = "e2e_test_explicit";
    await deleteCollectionIfExists(collectionName);
    await deleteCollectionIfExists("memory_migrations");

    const fakeEmbedder = createFakeEmbedder(768);

    jest.resetModules();
    jest.doMock("../src/utils/factory", () => {
      const { Qdrant: QdrantStore } = require("../src/vector_stores/qdrant");
      return {
        EmbedderFactory: { create: jest.fn().mockReturnValue(fakeEmbedder) },
        VectorStoreFactory: {
          create: jest.fn().mockImplementation((_provider: string, config: any) => {
            return new QdrantStore(config);
          }),
        },
        LLMFactory: {
          create: jest.fn().mockReturnValue({
            generateResponse: jest.fn().mockResolvedValue('{"facts":[]}'),
          }),
        },
        HistoryManagerFactory: {
          create: jest.fn().mockReturnValue({
            addHistory: jest.fn().mockResolvedValue(undefined),
            getHistory: jest.fn().mockResolvedValue([]),
            reset: jest.fn().mockResolvedValue(undefined),
          }),
        },
      };
    });

    jest.doMock("../src/utils/telemetry", () => ({
      captureClientEvent: jest.fn().mockResolvedValue(undefined),
    }));

    const { Memory } = require("../src/memory");

    // Workaround config from #4212 — explicit dimension
    const mem = new Memory({
      embedder: {
        provider: "ollama",
        config: { model: "nomic-embed-text" },
      },
      vectorStore: {
        provider: "qdrant",
        config: {
          host: QDRANT_HOST,
          port: QDRANT_PORT,
          collectionName,
          dimension: 768,
        },
      },
      llm: { provider: "openai", config: { apiKey: "fake" } },
      disableHistory: true,
    });

    await mem.getAll({ userId: "test-user" });

    // Probe should NOT have been called
    expect(fakeEmbedder.embed).not.toHaveBeenCalledWith("dimension probe");

    const collectionInfo = await qdrantClient.getCollection(collectionName);
    expect(collectionInfo.config?.params?.vectors?.size).toBe(768);

    await deleteCollectionIfExists(collectionName);
    await deleteCollectionIfExists("memory_migrations");
    jest.resetModules();
  });

  it("AFTER FIX: embeddingDims in embedder config skips probe", async () => {
    const collectionName = "e2e_test_embdims";
    await deleteCollectionIfExists(collectionName);
    await deleteCollectionIfExists("memory_migrations");

    const fakeEmbedder = createFakeEmbedder(768);

    jest.resetModules();
    jest.doMock("../src/utils/factory", () => {
      const { Qdrant: QdrantStore } = require("../src/vector_stores/qdrant");
      return {
        EmbedderFactory: { create: jest.fn().mockReturnValue(fakeEmbedder) },
        VectorStoreFactory: {
          create: jest.fn().mockImplementation((_provider: string, config: any) => {
            return new QdrantStore(config);
          }),
        },
        LLMFactory: {
          create: jest.fn().mockReturnValue({
            generateResponse: jest.fn().mockResolvedValue('{"facts":[]}'),
          }),
        },
        HistoryManagerFactory: {
          create: jest.fn().mockReturnValue({
            addHistory: jest.fn().mockResolvedValue(undefined),
            getHistory: jest.fn().mockResolvedValue([]),
            reset: jest.fn().mockResolvedValue(undefined),
          }),
        },
      };
    });

    jest.doMock("../src/utils/telemetry", () => ({
      captureClientEvent: jest.fn().mockResolvedValue(undefined),
    }));

    const { Memory } = require("../src/memory");

    const mem = new Memory({
      embedder: {
        provider: "ollama",
        config: { model: "nomic-embed-text", embeddingDims: 768 },
      },
      vectorStore: {
        provider: "qdrant",
        config: {
          host: QDRANT_HOST,
          port: QDRANT_PORT,
          collectionName,
        },
      },
      llm: { provider: "openai", config: { apiKey: "fake" } },
      disableHistory: true,
    });

    await mem.getAll({ userId: "test-user" });

    // Probe should NOT have been called — dimension inferred from embeddingDims
    expect(fakeEmbedder.embed).not.toHaveBeenCalledWith("dimension probe");

    const collectionInfo = await qdrantClient.getCollection(collectionName);
    expect(collectionInfo.config?.params?.vectors?.size).toBe(768);

    await deleteCollectionIfExists(collectionName);
    await deleteCollectionIfExists("memory_migrations");
    jest.resetModules();
  });
});

// ───────────────────────────────────────────────────────────────────────────
// 2. Reproduce #4056 issue 1: Collection creation race condition
// ───────────────────────────────────────────────────────────────────────────
describeIfQdrant("Issue #4056: Qdrant race condition", () => {
  it("concurrent ensureCollection calls don't crash (no 409 error leak)", async () => {
    const collectionName = "e2e_test_race";
    await deleteCollectionIfExists(collectionName);
    await deleteCollectionIfExists("memory_migrations");

    // Create 5 Qdrant instances concurrently — this simulates the race
    // that caused "Collection memory_migrations already exists!" in #4056
    const instances = Array.from(
      { length: 5 },
      () =>
        new Qdrant({
          host: QDRANT_HOST,
          port: QDRANT_PORT,
          collectionName,
          embeddingModelDims: 768,
          dimension: 768,
        }),
    );

    // All should initialize without throwing 409 Conflict
    await Promise.all(instances.map((inst) => inst.initialize()));

    // Verify collection exists with correct dimension
    const info = await qdrantClient.getCollection(collectionName);
    expect(info.config?.params?.vectors?.size).toBe(768);

    // memory_migrations should also exist (created by initialize)
    const migrInfo = await qdrantClient.getCollection("memory_migrations");
    expect(migrInfo.config?.params?.vectors?.size).toBe(1);

    await deleteCollectionIfExists(collectionName);
    await deleteCollectionIfExists("memory_migrations");
  });

  it("getUserId works after concurrent initialization", async () => {
    const collectionName = "e2e_test_race2";
    await deleteCollectionIfExists(collectionName);
    await deleteCollectionIfExists("memory_migrations");

    const instance = new Qdrant({
      host: QDRANT_HOST,
      port: QDRANT_PORT,
      collectionName,
      embeddingModelDims: 768,
      dimension: 768,
    });

    await instance.initialize();

    // getUserId should work without 409 crash
    const userId = await instance.getUserId();
    expect(typeof userId).toBe("string");
    expect(userId.length).toBeGreaterThan(0);

    // setUserId + getUserId roundtrip
    await instance.setUserId("custom-e2e-user");
    const updated = await instance.getUserId();
    expect(updated).toBe("custom-e2e-user");

    await deleteCollectionIfExists(collectionName);
    await deleteCollectionIfExists("memory_migrations");
  });
});

// ───────────────────────────────────────────────────────────────────────────
// 3. Reproduce #4056 issue 2: memory_migrations dimension isolation
// ───────────────────────────────────────────────────────────────────────────
describeIfQdrant("Issue #4056: memory_migrations dimension isolation", () => {
  it("memory_migrations uses dim=1 independently of main collection dim=768", async () => {
    const collectionName = "e2e_test_noexplicit";
    await deleteCollectionIfExists(collectionName);
    await deleteCollectionIfExists("memory_migrations");

    const instance = new Qdrant({
      host: QDRANT_HOST,
      port: QDRANT_PORT,
      collectionName,
      embeddingModelDims: 768,
      dimension: 768,
    });

    await instance.initialize();

    // Allow Qdrant a moment to fully commit collections
    await new Promise((r) => setTimeout(r, 500));

    // Main collection should be 768
    const mainInfo = await qdrantClient.getCollection(collectionName);
    expect(mainInfo.config?.params?.vectors?.size).toBe(768);

    // memory_migrations should be 1 (NOT 768!)
    // This was the bug in #4056 issue 2 — telemetry used wrong dimension
    const migrationsInfo =
      await qdrantClient.getCollection("memory_migrations");
    expect(migrationsInfo.config?.params?.vectors?.size).toBe(1);

    // getUserId should work — vector dim=1 in memory_migrations
    const userId = await instance.getUserId();
    expect(typeof userId).toBe("string");

    // setUserId should also work
    await instance.setUserId("custom-test-user");
    const newUserId = await instance.getUserId();
    expect(newUserId).toBe("custom-test-user");

    await deleteCollectionIfExists(collectionName);
    await deleteCollectionIfExists("memory_migrations");
  });
});
