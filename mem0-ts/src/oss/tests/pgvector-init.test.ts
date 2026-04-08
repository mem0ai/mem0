/**
 * PGVector initialization idempotency tests.
 *
 * Regression guard for #4727 — `PGVector` is constructed with a fire-and-forget
 * `initialize()` call, then `Memory._autoInitialize()` explicitly awaits
 * `initialize()` a second time. The second call used to run `this.client.connect()`
 * on an already-connected `pg.Client` and throw:
 *
 *   Error: Client has already been connected. You cannot reuse a client.
 *
 * These tests mock the `pg.Client` to prove that:
 *   1. Multiple concurrent `initialize()` calls share a single in-flight promise.
 *   2. Each `pg.Client` instance only has `connect()` invoked once.
 *   3. The existing behavior of creating the target database and swapping
 *      clients is preserved.
 */
/// <reference types="jest" />

// Track every client instance the code under test creates so we can assert
// on their lifecycle without needing a real postgres.
interface FakeClient {
  connect: jest.Mock;
  end: jest.Mock;
  query: jest.Mock;
  database: string;
}

const createdClients: FakeClient[] = [];

jest.mock("pg", () => {
  return {
    __esModule: true,
    default: {
      Client: jest.fn().mockImplementation((cfg: { database: string }) => {
        // State lives in the closure so the mock does not depend on
        // `this` binding through `jest.fn().mockImplementation(...)`.
        let connected = false;
        const instance: FakeClient = {
          database: cfg.database,
          connect: jest.fn().mockImplementation(async () => {
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
            // Minimal fake results so `_doInitialize` reaches the end.
            if (/FROM pg_database/.test(sql)) {
              return { rows: [{ "?column?": 1 }] }; // database already exists
            }
            if (/information_schema\.tables/.test(sql)) {
              return { rows: [] }; // collection does not exist yet
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
  // Silence the `console.error` from the constructor's fire-and-forget
  // promise so the test output stays clean.
  jest.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  (console.error as jest.Mock).mockRestore?.();
});

describe("PGVector initialization idempotency (#4727)", () => {
  test("multiple initialize() calls share a single in-flight promise", async () => {
    const store = new PGVector(baseConfig());

    // Mimic Memory._autoInitialize() explicitly awaiting initialize()
    // on top of the constructor's fire-and-forget call.
    await Promise.all([
      store.initialize(),
      store.initialize(),
      store.initialize(),
    ]);

    // PGVector swaps the client: first instance talks to `postgres`,
    // second talks to the target `vector_store` database.
    expect(createdClients.length).toBe(2);

    // Neither client should have `connect()` called more than once —
    // that is the exact precondition the pg driver rejects.
    for (const client of createdClients) {
      expect(client.connect).toHaveBeenCalledTimes(1);
    }
  });

  test("subsequent initialize() after completion returns cached promise without reconnect", async () => {
    const store = new PGVector(baseConfig());

    await store.initialize();
    const clientsAfterFirst = createdClients.length;

    // A later, fully-sequential call (e.g. Memory retrying after a
    // transient error) must not trigger a fresh connect cycle.
    await store.initialize();

    expect(createdClients.length).toBe(clientsAfterFirst);
    for (const client of createdClients) {
      expect(client.connect).toHaveBeenCalledTimes(1);
    }
  });

  test("initialize() never throws the 'already been connected' error", async () => {
    const store = new PGVector(baseConfig());

    // If the bug from #4727 regresses, one of these awaits will reject
    // with the exact error string below.
    await expect(
      Promise.all([store.initialize(), store.initialize()]),
    ).resolves.not.toThrow();

    for (const client of createdClients) {
      const connectErrors = client.connect.mock.results
        .filter((r) => r.type === "throw")
        .map((r) => (r.value as Error).message);
      expect(connectErrors).not.toContain(
        "Client has already been connected. You cannot reuse a client.",
      );
    }
  });
});
