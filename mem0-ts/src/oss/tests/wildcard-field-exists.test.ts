/**
 * "*" filter value = field-exists across TS vector stores (issue #6539).
 */
/// <reference types="jest" />
import { MemoryVectorStore } from "../src/vector_stores/memory";
import { CassandraDB } from "../src/vector_stores/cassandra";
import { PineconeDB } from "../src/vector_stores/pinecone";
import { Qdrant } from "../src/vector_stores/qdrant";
import { Milvus } from "../src/vector_stores/milvus";

describe("field-exists wildcard (*)", () => {
  test("MemoryVectorStore rejects missing fields for *", () => {
    const store = new MemoryVectorStore({
      collectionName: "wc",
      dimension: 3,
      dbPath: ":memory:",
    }) as any;
    expect(store.matchFieldCondition({ agent_id: "a" }, "agent_id", "*")).toBe(
      true,
    );
    expect(store.matchFieldCondition({}, "agent_id", "*")).toBe(false);
    expect(store.matchFieldCondition({ agent_id: null }, "agent_id", "*")).toBe(
      false,
    );
  });

  test("CassandraDB rejects missing fields for *", () => {
    const store = Object.create(CassandraDB.prototype) as any;
    expect(store.matchFieldCondition({ agent_id: "a" }, "agent_id", "*")).toBe(
      true,
    );
    expect(store.matchFieldCondition({}, "agent_id", "*")).toBe(false);
  });

  test("PineconeDB emits $exists for *", () => {
    const store = Object.create(PineconeDB.prototype) as any;
    expect(store.createFilter({ agent_id: "*" })).toEqual({
      agent_id: { $exists: true },
    });
    expect(store.createFilter({ agent_id: "x" })).toEqual({
      agent_id: { $eq: "x" },
    });
  });

  test("Qdrant uses must_not is_empty for *", () => {
    const store = Object.create(Qdrant.prototype) as any;
    expect(store.createFilter({ agent_id: "*" })).toEqual({
      must: undefined,
      should: undefined,
      must_not: [{ is_empty: { key: "agent_id" } }],
    });
  });

  test("Milvus emits exists metadata[key] for *", () => {
    const store = Object.create(Milvus.prototype) as any;
    expect(store.createFilter({ agent_id: "*" })).toBe(
      'exists metadata["agent_id"]',
    );
    expect(store.createFilter({ agent_id: "bot" })).toBe(
      '(metadata["agent_id"] == "bot")',
    );
  });
});
