/**
 * pgvector ESM import compatibility test.
 * Verifies that pgvector.ts uses a CommonJS-compatible import pattern
 * for the `pg` package, which does not support named exports in ESM (Node.js 22+).
 *
 * Refs: https://github.com/mem0ai/mem0/issues/4519
 * Refs: https://github.com/mem0ai/mem0/issues/4513
 */
/// <reference types="jest" />

// Mock pg before importing the module that depends on it
jest.mock("pg", () => ({
  Client: jest.fn().mockImplementation(() => ({
    connect: jest.fn(),
    end: jest.fn(),
    query: jest.fn(),
  })),
  Pool: jest.fn().mockImplementation(() => ({})),
}));

import { PGVector } from "../src/vector_stores/pgvector";
import type { PGVectorConfig } from "../src/vector_stores/pgvector";

describe("PGVector ESM import compatibility", () => {
  const dummyConfig: PGVectorConfig = {
    user: "test",
    password: "test",
    host: "localhost",
    port: 5432,
    embeddingModelDims: 1536,
  };

  test("PGVector can be instantiated without throwing ESM import error", () => {
    expect(() => new PGVector(dummyConfig)).not.toThrow();
  });

  test("PGVector exposes expected async vector store methods", () => {
    const store = new PGVector(dummyConfig);
    expect(typeof store.initialize).toBe("function");
    expect(typeof store.insert).toBe("function");
    expect(typeof store.search).toBe("function");
    expect(typeof store.get).toBe("function");
    expect(typeof store.delete).toBe("function");
    expect(typeof store.close).toBe("function");
  });
});
