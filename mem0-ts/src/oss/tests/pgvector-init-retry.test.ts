/**
 * PGVector initialization retry tests.
 *
 * Regression guard for the gap identified after #4841 merged — the idempotency
 * fix cached _initPromise but did NOT clear it on rejection.  A transient
 * postgres failure (network blip, pg not yet ready) therefore permanently
 * poisons the cached promise: every subsequent initialize() call re-throws
 * the original error instead of retrying.
 *
 * This suite proves:
 *   1. After a failed initialize(), a second call retries (not re-throws cached error).
 *   2. After a successful retry, further calls return the resolved promise (no extra work).
 *   3. The old behaviour (without .catch clearing) is demonstrably broken — the
 *      test marked FAILS_WITHOUT_FIX shows what upstream #4841 shipped before this PR.
 */
/// <reference types="jest" />

interface FakeClient {
  connect: jest.Mock;
  end: jest.Mock;
  query: jest.Mock;
  database: string;
}

const createdClients: FakeClient[] = [];

// Shared connect-fail toggle: when true, next connect() throws a transient error.
let failNextConnect = false;

jest.mock("pg", () => {
  return {
    __esModule: true,
    default: {
      Client: jest.fn().mockImplementation((cfg: { database: string }) => {
        let connected = false;
        const instance: FakeClient = {
          database: cfg.database,
          connect: jest.fn().mockImplementation(async () => {
            if (failNextConnect) {
              failNextConnect = false;
              throw new Error("Connection refused (transient)");
            }
            if (connected) {
              throw new Error(
                "Client has already been connected. You cannot reuse a client.",
              );
            }
            connected = true;
          }),
          end: jest.fn().mockImplementation(async () => {
            connected = false;
          }),
          query: jest.fn().mockImplementation(async (sql: string) => {
            if (/FROM pg_database/.test(sql)) {
              return { rows: [{ "?column?": 1 }] };
            }
            if (/information_schema\.tables/.test(sql)) {
              return { rows: [] };
            }
            return { rows: [] };
          }),
        };
        createdClients.push(instance);
        return instance;
      }),
    },
  };
});

import { PGVector } from "../src/vector_stores/pgvector";

function baseConfig() {
  return {
    collectionName: "test_collection",
    dbname: "vector_store",
    user: "test",
    password: "test",
    host: "localhost",
    port: 5432,
    embeddingModelDims: 1024,
  };
}

beforeEach(() => {
  createdClients.length = 0;
  failNextConnect = false;
  jest.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  (console.error as jest.Mock).mockRestore?.();
});

describe("PGVector initialization retry after transient failure", () => {
  test("second initialize() retries after first fails with transient error", async () => {
    // Constructor fires initialize() in the background — fail that one.
    failNextConnect = true;
    const store = new PGVector(baseConfig());

    // Drain the constructor's background promise so the failure is registered.
    await new Promise((r) => setTimeout(r, 0));

    // Now the background call has rejected and _initPromise must be cleared.
    // An explicit caller (e.g. Memory._ensureInitialized) retries.
    await expect(store.initialize()).resolves.toBeUndefined();
  });

  test("after transient failure then success, further calls do not reconnect", async () => {
    failNextConnect = true;
    const store = new PGVector(baseConfig());
    await new Promise((r) => setTimeout(r, 0));

    // First explicit call: retries and succeeds.
    await store.initialize();
    const clientsAfterRetry = createdClients.length;

    // Subsequent calls must reuse the resolved promise, not reconnect.
    await store.initialize();
    await store.initialize();

    expect(createdClients.length).toBe(clientsAfterRetry);
  });

  test("failed initialize() exposes the original error to the caller", async () => {
    failNextConnect = true;
    const store = new PGVector(baseConfig());
    await new Promise((r) => setTimeout(r, 0));

    // Force failure again for a direct caller.
    failNextConnect = true;
    await expect(store.initialize()).rejects.toThrow(
      "Connection refused (transient)",
    );
  });

  /**
   * FAILS_WITHOUT_FIX — documents the broken behaviour shipped by #4841.
   *
   * Without `.catch(() => { this._initPromise = undefined; throw error; })`,
   * _initPromise stays set to the rejected promise.  The second initialize()
   * call returns that same rejected promise instead of retrying.
   *
   * Run with the fix present: test passes.
   * Revert the .catch() block and run again: test fails with the cached error.
   */
  test("FAILS_WITHOUT_FIX: demonstrates cached-rejection is broken without the fix", async () => {
    failNextConnect = true;
    const store = new PGVector(baseConfig());
    await new Promise((r) => setTimeout(r, 0));

    // With fix: _initPromise was cleared on rejection, retry succeeds.
    // Without fix: _initPromise still holds the rejected promise, re-throws.
    await expect(store.initialize()).resolves.toBeUndefined();
  });
});
