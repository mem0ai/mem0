/// <reference types="jest" />
/**
 * Unit tests for Redis vector store insert/update with entity payloads.
 *
 * Entity payloads from _linkEntitiesForMemory lack hash, created_at,
 * and updated_at. Direct property access produces undefined/NaN values.
 * These tests verify the nullish coalescing guards.
 */

import { RedisDB } from "../src/vector_stores/redis";

jest.mock("redis", () => ({
  createClient: jest.fn(() => ({
    connect: jest.fn(),
    on: jest.fn(),
    moduleList: jest.fn().mockResolvedValue([{ name: "search", ver: 20800 }]),
    ft: {
      create: jest.fn(),
      search: jest.fn(),
      info: jest.fn().mockRejectedValue(new Error("Unknown index")),
      _list: jest.fn().mockResolvedValue([]),
    },
    hSet: jest.fn(),
    hGetAll: jest.fn(),
    del: jest.fn(),
    exists: jest.fn(),
    quit: jest.fn(),
  })),
}));

function createStore(): RedisDB {
  return new RedisDB({
    redisUrl: "redis://localhost:6379",
    collectionName: "test",
    embeddingModelDims: 4,
  });
}

describe("RedisDB – entity payload handling", () => {
  let store: RedisDB;
  let mockClient: any;

  beforeAll(async () => {
    store = createStore();
    await store.initialize();
    mockClient = (store as any).client;
  });

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("insert with entity payload (no hash/created_at) does not produce NaN", async () => {
    const entityPayload = {
      data: "OpenAI",
      entityType: "organization",
      linkedMemoryIds: ["mem-1"],
      userId: "test_user",
    };

    await store.insert([[0.1, 0.2, 0.3, 0.4]], ["entity-1"], [entityPayload]);

    expect(mockClient.hSet).toHaveBeenCalledTimes(1);
    const call = mockClient.hSet.mock.calls[0];
    const entry = call[1];

    expect(entry.memory_id).toBe("entity-1");
    expect(entry.memory).toBe("OpenAI");
    expect(entry.hash).toBe("");
    expect(entry.created_at).toBe(0);
    expect(Number.isNaN(entry.created_at)).toBe(false);
  });

  test("update with entity payload (no hash/created_at/updated_at) does not produce NaN", async () => {
    const entityPayload = {
      data: "OpenAI",
      entityType: "organization",
      linkedMemoryIds: ["mem-1"],
      userId: "test_user",
    };

    await store.update("entity-1", [0.1, 0.2, 0.3, 0.4], entityPayload);

    expect(mockClient.hSet).toHaveBeenCalledTimes(1);
    const call = mockClient.hSet.mock.calls[0];
    const entry = call[1];

    expect(entry.memory_id).toBe("entity-1");
    expect(entry.memory).toBe("OpenAI");
    expect(entry.hash).toBe("");
    expect(entry.created_at).toBe(0);
    expect(entry.updated_at).toBe(0);
    expect(Number.isNaN(entry.created_at)).toBe(false);
    expect(Number.isNaN(entry.updated_at)).toBe(false);
  });

  test("insert with normal payload preserves timestamp", async () => {
    const normalPayload = {
      data: "likes coffee",
      hash: "abc123",
      createdAt: "2026-06-25T10:00:00.000Z",
      userId: "test_user",
    };

    await store.insert([[0.1, 0.2, 0.3, 0.4]], ["mem-1"], [normalPayload]);

    const call = mockClient.hSet.mock.calls[0];
    const entry = call[1];

    expect(entry.hash).toBe("abc123");
    expect(entry.memory).toBe("likes coffee");
    expect(entry.created_at).toBeGreaterThan(0);
    expect(Number.isNaN(entry.created_at)).toBe(false);
  });
});
