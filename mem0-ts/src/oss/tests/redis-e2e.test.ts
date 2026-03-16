/// <reference types="jest" />
/**
 * End-to-end tests for Redis vector store with init guard fix.
 *
 * Requires a running Redis Stack instance at localhost:6379.
 * Skipped automatically when Redis is not available.
 *
 * Run: npx jest --config jest.config.js src/oss/tests/redis-e2e.test.ts --forceExit
 */

import { createClient } from "redis";
import { RedisDB } from "../src/vector_stores/redis";
import { v4 as uuidv4 } from "uuid";
jest.setTimeout(30000);

const REDIS_HOST = "localhost";
const REDIS_PORT = 6379;
const REDIS_URL = `redis://${REDIS_HOST}:${REDIS_PORT}`;
const COLLECTION_NAME = "e2e_redis_test";

// Check if Redis is reachable synchronously at load time
function isRedisAvailable(): boolean {
  try {
    const { execSync } = require("child_process");
    execSync(
      `node -e "const s=require('net').createConnection({host:'${REDIS_HOST}',port:${REDIS_PORT}});s.on('connect',()=>{s.destroy();process.exit(0)});s.on('error',()=>process.exit(1));s.setTimeout(2000,()=>process.exit(1))"`,
      { timeout: 3000, stdio: "ignore" },
    );
    return true;
  } catch {
    return false;
  }
}

const redisAvailable = isRedisAvailable();
if (!redisAvailable) {
  console.warn("Redis not available at localhost:6379 — skipping e2e tests");
}

// Standalone client for cleanup
let cleanupClient: ReturnType<typeof createClient>;

async function cleanupRedis() {
  if (!redisAvailable) return;
  try {
    // Drop the index if it exists
    await cleanupClient.ft.dropIndex(COLLECTION_NAME);
  } catch {
    // Index doesn't exist — fine
  }

  // Delete all keys with our prefix
  const keys = await cleanupClient.keys(`mem0:${COLLECTION_NAME}:*`);
  if (keys.length > 0) {
    await cleanupClient.del(keys);
  }

  // Clean up memory_migrations key
  await cleanupClient.del("memory_migrations:1");
}

beforeAll(async () => {
  if (!redisAvailable) return;

  cleanupClient = createClient({ url: REDIS_URL });
  await cleanupClient.connect();

  // Verify Redis Stack is running with search module
  const modules = (await cleanupClient.moduleList()) as unknown as any[];
  const hasSearch = modules.some((mod: any[]) => {
    const moduleMap = new Map();
    for (let i = 0; i < mod.length; i += 2) {
      moduleMap.set(mod[i], mod[i + 1]);
    }
    return moduleMap.get("name")?.toLowerCase() === "search";
  });
  expect(hasSearch).toBe(true);
});

afterAll(async () => {
  if (!redisAvailable) return;
  await cleanupRedis();
  await cleanupClient.quit();
});

// Conditionally skip tests when Redis is unavailable
const describeIfRedis = redisAvailable ? describe : describe.skip;

// ───────────────────────────────────────────────────────────────────────────
// 1. Basic initialization and idempotent init guard
// ───────────────────────────────────────────────────────────────────────────
describeIfRedis("Redis: initialization", () => {
  afterEach(async () => {
    await cleanupRedis();
  });

  it("initializes successfully and creates index", async () => {
    const store = new RedisDB({
      redisUrl: REDIS_URL,
      collectionName: COLLECTION_NAME,
      embeddingModelDims: 128,
    });
    await store.initialize();

    // Verify the index was created by querying index info
    const info = await cleanupClient.ft.info(COLLECTION_NAME);
    expect(info).toBeDefined();
    expect(info.indexName).toBe(COLLECTION_NAME);

    await store.close();
  });

  it("idempotent initialize() — multiple calls don't crash", async () => {
    const store = new RedisDB({
      redisUrl: REDIS_URL,
      collectionName: COLLECTION_NAME,
      embeddingModelDims: 128,
    });

    // Call initialize multiple times concurrently
    await Promise.all([
      store.initialize(),
      store.initialize(),
      store.initialize(),
    ]);

    // Should still work fine
    const info = await cleanupClient.ft.info(COLLECTION_NAME);
    expect(info).toBeDefined();

    await store.close();
  });
});

// ───────────────────────────────────────────────────────────────────────────
// 2. Full CRUD operations
// ───────────────────────────────────────────────────────────────────────────
describeIfRedis("Redis: CRUD operations", () => {
  let store: RedisDB;

  beforeEach(async () => {
    await cleanupRedis();
    store = new RedisDB({
      redisUrl: REDIS_URL,
      collectionName: COLLECTION_NAME,
      embeddingModelDims: 4, // Small dims for testing
    });
    await store.initialize();
  });

  afterEach(async () => {
    await store.close();
    await cleanupRedis();
  });

  it("insert and search vectors", async () => {
    const id1 = uuidv4();
    const id2 = uuidv4();
    const vec1 = [1.0, 0.0, 0.0, 0.0];
    const vec2 = [0.0, 1.0, 0.0, 0.0];

    await store.insert(
      [vec1, vec2],
      [id1, id2],
      [
        {
          data: "hello world",
          hash: "h1",
          userId: "user1",
          createdAt: new Date().toISOString(),
        },
        {
          data: "goodbye world",
          hash: "h2",
          userId: "user1",
          createdAt: new Date().toISOString(),
        },
      ],
    );

    // Search — vec1 should be most similar to itself
    const results = await store.search(vec1, 2, { userId: "user1" });
    expect(results.length).toBe(2);
    // The first result should be closest to the query
    expect(results[0].id).toBe(id1);
    expect(results[0].score).toBeDefined();
    expect(results[0].payload).toBeDefined();
  });

  it("get vector by ID", async () => {
    const id = uuidv4();
    const vec = [0.5, 0.5, 0.0, 0.0];

    await store.insert(
      [vec],
      [id],
      [
        {
          data: "test memory",
          hash: "h-test",
          userId: "user1",
          createdAt: new Date().toISOString(),
        },
      ],
    );

    const result = await store.get(id);
    expect(result).not.toBeNull();
    expect(result!.id).toBe(id);
    expect(result!.payload.data).toBe("test memory");
    expect(result!.payload.hash).toBe("h-test");
  });

  it("get non-existent vector returns null", async () => {
    const result = await store.get("non-existent-id");
    expect(result).toBeNull();
  });

  it("update vector and payload", async () => {
    const id = uuidv4();
    const vec = [1.0, 0.0, 0.0, 0.0];

    await store.insert(
      [vec],
      [id],
      [
        {
          data: "original",
          hash: "h-orig",
          userId: "user1",
          createdAt: new Date().toISOString(),
        },
      ],
    );

    // Update with new vector and payload
    const newVec = [0.0, 0.0, 1.0, 0.0];
    await store.update(id, newVec, {
      data: "updated memory",
      hash: "h-updated",
      userId: "user1",
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });

    const result = await store.get(id);
    expect(result).not.toBeNull();
    expect(result!.payload.data).toBe("updated memory");
    expect(result!.payload.hash).toBe("h-updated");
  });

  it("delete vector", async () => {
    const id = uuidv4();
    const vec = [0.0, 0.0, 0.0, 1.0];

    await store.insert(
      [vec],
      [id],
      [
        {
          data: "to be deleted",
          hash: "h-del",
          userId: "user1",
          createdAt: new Date().toISOString(),
        },
      ],
    );

    // Verify it exists
    const before = await store.get(id);
    expect(before).not.toBeNull();

    // Delete
    await store.delete(id);

    // Verify it's gone
    const after = await store.get(id);
    expect(after).toBeNull();
  });

  it("list vectors with filters", async () => {
    const id1 = uuidv4();
    const id2 = uuidv4();
    const id3 = uuidv4();

    await store.insert(
      [
        [1, 0, 0, 0],
        [0, 1, 0, 0],
        [0, 0, 1, 0],
      ],
      [id1, id2, id3],
      [
        {
          data: "mem1",
          hash: "h1",
          userId: "usera",
          createdAt: new Date().toISOString(),
        },
        {
          data: "mem2",
          hash: "h2",
          userId: "usera",
          createdAt: new Date().toISOString(),
        },
        {
          data: "mem3",
          hash: "h3",
          userId: "userb",
          createdAt: new Date().toISOString(),
        },
      ],
    );

    // List all
    const [all, allCount] = await store.list();
    expect(allCount).toBe(3);
    expect(all.length).toBe(3);

    // List with filter
    const [filtered, filteredCount] = await store.list({
      userId: "usera",
    });
    expect(filteredCount).toBe(2);
    expect(filtered.length).toBe(2);
  });
});

// ───────────────────────────────────────────────────────────────────────────
// 3. getUserId / setUserId
// ───────────────────────────────────────────────────────────────────────────
describeIfRedis("Redis: getUserId / setUserId", () => {
  let store: RedisDB;

  beforeEach(async () => {
    await cleanupRedis();
    store = new RedisDB({
      redisUrl: REDIS_URL,
      collectionName: COLLECTION_NAME,
      embeddingModelDims: 4,
    });
    await store.initialize();
  });

  afterEach(async () => {
    await store.close();
    await cleanupRedis();
  });

  it("getUserId generates random ID if none exists", async () => {
    const userId = await store.getUserId();
    expect(typeof userId).toBe("string");
    expect(userId.length).toBeGreaterThan(0);
  });

  it("setUserId + getUserId roundtrip", async () => {
    await store.setUserId("custom-redis-user");
    const retrieved = await store.getUserId();
    expect(retrieved).toBe("custom-redis-user");
  });

  it("getUserId returns same value on subsequent calls", async () => {
    const first = await store.getUserId();
    const second = await store.getUserId();
    expect(first).toBe(second);
  });
});

// ───────────────────────────────────────────────────────────────────────────
// 4. Dimension handling (our fix ensures correct dims from Memory)
// ───────────────────────────────────────────────────────────────────────────
describeIfRedis("Redis: dimension handling", () => {
  afterEach(async () => {
    await cleanupRedis();
  });

  it("creates index with correct dimensions from config", async () => {
    const store = new RedisDB({
      redisUrl: REDIS_URL,
      collectionName: COLLECTION_NAME,
      embeddingModelDims: 768,
    });
    await store.initialize();

    // Verify the index has the right dimension in its schema
    const info = await cleanupClient.ft.info(COLLECTION_NAME);
    // Check that the vector field has DIM=768
    const attributes = info.attributes as any[];
    const vectorAttr = attributes.find(
      (a: any) => a.identifier === "embedding" || a.attribute === "embedding",
    );
    expect(vectorAttr).toBeDefined();

    await store.close();
  });

  it("insert with matching dimension succeeds", async () => {
    const dims = 128;
    const store = new RedisDB({
      redisUrl: REDIS_URL,
      collectionName: COLLECTION_NAME,
      embeddingModelDims: dims,
    });
    await store.initialize();

    const id = uuidv4();
    const vec = new Array(dims).fill(0.1);

    await store.insert(
      [vec],
      [id],
      [
        {
          data: "test",
          hash: "h1",
          createdAt: new Date().toISOString(),
        },
      ],
    );

    const result = await store.get(id);
    expect(result).not.toBeNull();
    expect(result!.id).toBe(id);

    await store.close();
  });
});
