/// <reference types="jest" />

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

function mockPgQuery(sql: string) {
  if (sql.includes("SELECT 1 FROM pg_database")) {
    return { rows: [{ "?column?": 1 }] };
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

  const Client = jest.fn().mockImplementation((config: any) => {
    const client = {
      config,
      connect: jest.fn().mockResolvedValue(undefined),
      end: jest.fn().mockResolvedValue(undefined),
      query: jest
        .fn()
        .mockImplementation(async (sql: string) => mockPgQuery(sql)),
    };

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

describe("PGVector - search()", () => {
  beforeEach(() => {
    const pg = require("pg");
    pg.__mock.Client.mockClear();
    pg.__mock.clients.length = 0;
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
});
