/// <reference types="jest" />
/**
 * Cassandra vector store — filter matching unit tests.
 *
 * Cassandra has no server-side metadata filter, so search()/list() scan rows
 * and apply filters in-app via matchFieldCondition(). These tests drive that
 * matcher through the public list() API with an injected fake client.
 */
import { CassandraDB } from "../src/vector_stores/cassandra";

type Row = { id: string; payload: Record<string, any> };

// Minimal fake driver: CREATE statements during initialize() return nothing;
// a SELECT returns the seeded rows in one page (pageState undefined => stop).
function fakeClient(rows: Row[]) {
  return {
    async connect() {},
    async execute(query: string) {
      if (/^\s*SELECT/i.test(query)) {
        return { rows, pageState: undefined };
      }
      return { rows: [], pageState: undefined };
    },
    async shutdown() {},
  };
}

function makeStore(rows: Row[]) {
  return new CassandraDB({
    keyspace: "mem0",
    collectionName: "mem0",
    dimension: 3,
    client: fakeClient(rows) as any,
  } as any);
}

describe("CassandraDB filter matching", () => {
  const rows: Row[] = [
    { id: "a", payload: { data: "a", age: 5 } },
    { id: "b", payload: { data: "b", age: 15 } },
    { id: "c", payload: { data: "c", age: 25 } },
  ];

  it("applies every operator in a compound range filter (not just the first)", async () => {
    const store = makeStore(rows);
    // age in [10, 20]: only "b" (15) qualifies. The old matcher returned on the
    // first operator (gte), so "c" (25) leaked through because lte was ignored.
    const [results] = await store.list({ age: { gte: 10, lte: 20 } });
    expect(results.map((r) => r.id)).toEqual(["b"]);
  });

  it("still matches a single-operator filter", async () => {
    const store = makeStore(rows);
    const [results] = await store.list({ age: { gte: 15 } });
    expect(results.map((r) => r.id).sort()).toEqual(["b", "c"]);
  });

  it("treats a plain equality filter as before", async () => {
    const store = makeStore(rows);
    const [results] = await store.list({ age: 15 });
    expect(results.map((r) => r.id)).toEqual(["b"]);
  });
});
