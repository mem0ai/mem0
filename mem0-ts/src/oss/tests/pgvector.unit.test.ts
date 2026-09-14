const searchRows = [
  {
    id: "a",
    payload: { data: "exactly x-axis" },
    distance: "0",
  },
  {
    id: "b",
    payload: { data: "close to x-axis" },
    distance: "0.006116251198662548",
  },
  {
    id: "c",
    payload: { data: "y-axis" },
    distance: "1",
  },
  {
    id: "d",
    payload: { data: "opposite x-axis" },
    distance: "2",
  },
];

const mockState = {
  databaseExists: true,
};

function mockPgQuery(sql: string) {
  if (sql.includes("SELECT 1 FROM pg_database")) {
    return { rows: mockState.databaseExists ? [{ "?column?": 1 }] : [] };
  }

  if (sql.includes("FROM information_schema.tables")) {
    return { rows: [{ table_name: "memories" }] };
  }

  if (sql.includes("vector <=> $1::vector AS distance")) {
    return { rows: searchRows };
  }

  return { rows: [] };
}

jest.mock("pg", () => {
  const clients: any[] = [];
  const { EventEmitter } = require("events");

  const Client = jest.fn().mockImplementation((config: any) => {
    const client = Object.assign(new EventEmitter(), {
      config,
      connect: jest.fn().mockResolvedValue(undefined),
      end: jest.fn().mockResolvedValue(undefined),
      query: jest
        .fn()
        .mockImplementation(async (sql: string) => mockPgQuery(sql)),
    });

    clients.push(client);
    return client;
  });

  const escapeIdentifier = (str: string) => `"${str.replace(/"/g, '""')}"`;

  return {
    __esModule: true,
    default: { Client, escapeIdentifier },
    Client,
    escapeIdentifier,
    __mock: { Client, clients },
  };
});

import { PGVector } from "../src/vector_stores/pgvector";

function getClientQueries(client: { query: jest.Mock }) {
  return client.query.mock.calls.map(([sql]) => sql as string);
}

describe("PGVector", () => {
  beforeEach(() => {
    const pg = require("pg");
    mockState.databaseExists = true;
    pg.__mock.Client.mockClear();
    pg.__mock.clients.length = 0;
  });

  test("uses one direct client for connectionString mode and skips bootstrap database creation", async () => {
    mockState.databaseExists = false;

    const ssl = { rejectUnauthorized: false };
    const store = new PGVector({
      collectionName: "memories",
      connectionString:
        "postgresql://postgres:postgres@db.example.com:5432/neondb",
      ssl,
      embeddingModelDims: 3,
      dimension: 3,
    } as any);

    await store.initialize();

    const pg = require("pg");
    expect(pg.__mock.Client).toHaveBeenCalledTimes(1);
    expect(pg.__mock.Client).toHaveBeenCalledWith({
      connectionString:
        "postgresql://postgres:postgres@db.example.com:5432/neondb",
      ssl,
    });

    const directClient = pg.__mock.clients[0];
    const queries = getClientQueries(directClient);

    expect(queries).not.toEqual(
      expect.arrayContaining([
        expect.stringContaining("SELECT 1 FROM pg_database"),
      ]),
    );
    expect(queries).not.toEqual(
      expect.arrayContaining([expect.stringContaining("CREATE DATABASE")]),
    );
    expect(queries).toEqual(
      expect.arrayContaining([
        "CREATE EXTENSION IF NOT EXISTS vector",
        expect.stringContaining("FROM information_schema.tables"),
      ]),
    );
  });

  test("keeps the split-field bootstrap flow when connectionString is absent", async () => {
    mockState.databaseExists = false;
    const ssl = { rejectUnauthorized: false };

    const store = new PGVector({
      collectionName: "memories",
      user: "postgres",
      password: "postgres",
      host: "localhost",
      port: 5432,
      dbname: "vector_store",
      ssl,
      embeddingModelDims: 3,
      dimension: 3,
    } as any);

    await store.initialize();

    const pg = require("pg");
    expect(pg.__mock.Client).toHaveBeenCalledTimes(2);
    expect(pg.__mock.Client).toHaveBeenNthCalledWith(1, {
      database: "postgres",
      user: "postgres",
      password: "postgres",
      host: "localhost",
      port: 5432,
      ssl,
    });
    expect(pg.__mock.Client).toHaveBeenNthCalledWith(2, {
      database: "vector_store",
      user: "postgres",
      password: "postgres",
      host: "localhost",
      port: 5432,
      ssl,
    });

    const bootstrapClient = pg.__mock.clients[0];
    const activeClient = pg.__mock.clients[1];
    const bootstrapQueries = getClientQueries(bootstrapClient);

    expect(bootstrapQueries).toEqual(
      expect.arrayContaining([
        "SELECT 1 FROM pg_database WHERE datname = $1",
        'CREATE DATABASE "vector_store"',
      ]),
    );
    expect(bootstrapClient.end).toHaveBeenCalledTimes(1);
    expect(getClientQueries(activeClient)).toEqual(
      expect.arrayContaining([
        "CREATE EXTENSION IF NOT EXISTS vector",
        expect.stringContaining("FROM information_schema.tables"),
      ]),
    );
  });

  test("throws when connectionString is absent and split-field params are missing", () => {
    expect(
      () =>
        new PGVector({
          collectionName: "memories",
          embeddingModelDims: 3,
          dimension: 3,
        } as any),
    ).toThrow(
      "PGVector requires either connectionString or user, password, host, port",
    );
  });

  test("returns similarity score (1 - distance) clamped to [0, 1]", async () => {
    const store = new PGVector({
      collectionName: "memories",
      user: "postgres",
      password: "postgres",
      host: "localhost",
      port: 5432,
      embeddingModelDims: 3,
      dimension: 3,
    } as any);

    await store.initialize();

    const results = await store.search([1, 0, 0], 4);

    expect(results).toEqual([
      {
        id: "a",
        payload: { data: "exactly x-axis" },
        score: 1,
      },
      {
        id: "b",
        payload: { data: "close to x-axis" },
        score: 0.9938837488013375,
      },
      {
        id: "c",
        payload: { data: "y-axis" },
        score: 0,
      },
      {
        id: "d",
        payload: { data: "opposite x-axis" },
        score: 0,
      },
    ]);

    const pg = require("pg");
    expect(pg.__mock.Client).toHaveBeenCalledTimes(2);

    const activeClient = pg.__mock.clients[1];
    expect(activeClient.query).toHaveBeenCalledWith(
      expect.stringContaining("vector <=> $1::vector AS distance"),
      ["[1,0,0]", 4],
    );
  });

  test("attaches an error handler to every pg.Client so a server-side termination does not crash the host process", async () => {
    // See https://github.com/mem0ai/mem0/issues/7294
    // Without an `error` listener on the pg.Client, a server-side
    // termination (e.g. `pg_terminate_backend`, container restart)
    // emits an `'error'` event with no listener; Node throws it as an
    // uncaught exception and kills the host. PGVector must register a
    // listener so the host process stays alive.
    const store = new PGVector({
      collectionName: "memories",
      connectionString:
        "postgresql://postgres:postgres@db.example.com:5432/neondb",
      embeddingModelDims: 3,
      dimension: 3,
    } as any);

    await store.initialize();

    const pg = require("pg");
    const client = pg.__mock.clients[0];
    expect(client.listenerCount("error")).toBeGreaterThanOrEqual(1);
    expect(() =>
      client.emit(
        "error",
        Object.assign(new Error("terminating connection"), {
          code: "57P01",
        }),
      ),
    ).not.toThrow();
  });

  test("reconnects on the next call after the underlying pg.Client errors out", async () => {
    // After a server-side termination, the store must rebuild a fresh
    // pg.Client on the next call so a transient DB restart does not
    // permanently break the host. The original `_initPromise` was
    // memoised, so the fix is to drop it (and the broken client) when
    // the error listener fires.
    mockState.databaseExists = true;
    const store = new PGVector({
      collectionName: "memories",
      connectionString:
        "postgresql://postgres:postgres@db.example.com:5432/neondb",
      embeddingModelDims: 3,
      dimension: 3,
    } as any);

    await store.initialize();

    const pg = require("pg");
    const beforeErrorClient = pg.__mock.clients[0];
    beforeErrorClient.emit(
      "error",
      Object.assign(new Error("terminating connection"), {
        code: "57P01",
      }),
    );

    // The listener fires synchronously inside emit; the next initialize()
    // must use a brand-new pg.Client.
    await store.initialize();

    expect(pg.__mock.Client).toHaveBeenCalledTimes(2);
    const reconnectedClient = pg.__mock.clients[1];
    expect(reconnectedClient).not.toBe(beforeErrorClient);
    expect(reconnectedClient.listenerCount("error")).toBeGreaterThanOrEqual(
      1,
    );
  });
});
