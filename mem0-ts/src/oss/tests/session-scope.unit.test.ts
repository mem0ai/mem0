/**
 * Unit tests for Memory.buildSessionScope. The recent-conversation buffer key
 * derived from user_id/agent_id/run_id must be unique per id combination.
 */
/// <reference types="jest" />
jest.mock("../src/utils/factory", () => {
  const { MemoryVectorStore } = jest.requireActual(
    "../src/vector_stores/memory",
  );
  const { SQLiteManager } = jest.requireActual("../src/storage/SQLiteManager");
  const testEmbedding = new Array(1536).fill(0.1);
  class MockEmbedder {
    embeddingDims = 1536;
    async embed(): Promise<number[]> {
      return testEmbedding;
    }
    async embedBatch(texts: string[]): Promise<number[][]> {
      return texts.map(() => testEmbedding);
    }
  }
  class MockLLM {
    async generateResponse() {
      return JSON.stringify({ memory: [] });
    }
  }
  return {
    __esModule: true,
    EmbedderFactory: { create: jest.fn(() => new MockEmbedder()) },
    LLMFactory: { create: jest.fn(() => new MockLLM()) },
    VectorStoreFactory: {
      create: jest.fn(
        () => new MemoryVectorStore({ collectionName: "t", dimension: 1536 }),
      ),
    },
    HistoryManagerFactory: {
      create: jest.fn(() => new SQLiteManager(":memory:")),
    },
  };
});

import { Memory } from "../src/memory";
import { SearchFilters } from "../src/types";

function scopeOf(memory: Memory, filters: SearchFilters): string {
  return (memory as any).buildSessionScope(filters);
}

function cartesian(values: string[], length: number): string[][] {
  if (length === 0) return [[]];
  const rest = cartesian(values, length - 1);
  const result: string[][] = [];
  for (const value of values) {
    for (const tail of rest) {
      result.push([value, ...tail]);
    }
  }
  return result;
}

describe("Memory session scope key", () => {
  let memory: Memory;

  beforeAll(async () => {
    memory = new Memory();
    await (memory as any)._initPromise;
  });

  it("keeps the unchanged key format for ids without delimiter characters", () => {
    expect(
      scopeOf(memory, { user_id: "550e8400-e29b-41d4-a716-446655440000" }),
    ).toBe("user_id=550e8400-e29b-41d4-a716-446655440000");
    expect(scopeOf(memory, { agent_id: "agent.assistant:v2" })).toBe(
      "agent_id=agent.assistant:v2",
    );
    expect(scopeOf(memory, { run_id: "12345" })).toBe("run_id=12345");
    expect(
      scopeOf(memory, { user_id: "user@example.com", agent_id: "support-bot" }),
    ).toBe("agent_id=support-bot&user_id=user@example.com");
  });

  it("no longer collides an id embedding the join syntax with the equivalent split filters", () => {
    const collapsedRun = scopeOf(memory, { run_id: "proj-x&user_id=u1" });
    const splitRun = scopeOf(memory, { user_id: "u1", run_id: "proj-x" });
    expect(collapsedRun).not.toBe(splitRun);

    const collapsedAgent = scopeOf(memory, { run_id: "proj-y&agent_id=a1" });
    const splitAgent = scopeOf(memory, { agent_id: "a1", run_id: "proj-y" });
    expect(collapsedAgent).not.toBe(splitAgent);
  });

  it("maps every distinct filter combination of delimiter-heavy ids to a distinct key", () => {
    const keys: string[] = ["user_id", "agent_id", "run_id"];
    const values = [
      "u1",
      "r1",
      "a1",
      "%",
      "&",
      "=",
      "a==",
      "a1&run_id=r1",
      "a1&user_id=u1",
      "r1&user_id=u1",
      "a1&run_id=r1&user_id=u1",
    ];
    const seen = new Map<string, SearchFilters>();

    for (let mask = 1; mask < 1 << keys.length; mask++) {
      const subset = keys.filter((_key, i) => mask & (1 << i));
      for (const combo of cartesian(values, subset.length)) {
        const filters: SearchFilters = {};
        subset.forEach((key, i) => (filters[key] = combo[i]));
        const scope = scopeOf(memory, filters);
        if (seen.has(scope)) {
          expect(seen.get(scope)).toEqual(filters);
        } else {
          seen.set(scope, filters);
        }
      }
    }
  });

  it("gives ids containing delimiter characters a new key format", () => {
    expect(scopeOf(memory, { user_id: "dXNlcl9pZDE=" })).toBe(
      "user_id=dXNlcl9pZDE%3D",
    );
    expect(scopeOf(memory, { agent_id: "x&y" })).toBe("agent_id=x%26y");
    expect(scopeOf(memory, { run_id: "50% off" })).toBe("run_id=50%25 off");
  });

  it("routes the add pipeline through the builder", async () => {
    const db = (memory as any).db;
    const spy = jest.spyOn(db, "getLastMessages");
    await memory.add([{ role: "user", content: "hello" }], {
      runId: "proj-x&user_id=u1",
    });
    expect(spy).toHaveBeenCalledWith("run_id=proj-x%26user_id%3Du1", 10);
    spy.mockRestore();
  });

  it("pins the exact key strings shared with the Python test suite", () => {
    expect(
      scopeOf(memory, { user_id: "550e8400-e29b-41d4-a716-446655440000" }),
    ).toBe("user_id=550e8400-e29b-41d4-a716-446655440000");
    expect(
      scopeOf(memory, { user_id: "u1", agent_id: "a1", run_id: "r1" }),
    ).toBe("agent_id=a1&run_id=r1&user_id=u1");
    expect(scopeOf(memory, { run_id: "proj-x&user_id=u1" })).toBe(
      "run_id=proj-x%26user_id%3Du1",
    );
  });
});
