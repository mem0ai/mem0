/// <reference types="jest" />
/**
 * add() writes the resolved scope (user_id / agent_id / run_id) into its
 * filters object. If that object is the caller's, the scope survives the call
 * and leaks into the next add() that reuses it, which also defeats the
 * "one of userId, agentId or runId is required" guard.
 *
 * search() and getAll() already build a fresh object from config.filters.
 */
jest.mock("../src/utils/telemetry", () => ({
  captureClientEvent: jest.fn().mockResolvedValue(undefined),
  isTelemetryEnabled: jest.fn(() => false),
}));

import { Memory } from "../src/memory";

const DIM = 1536;
let seq = 0;

function createMemory(): Memory {
  const m = new Memory({
    disableHistory: true,
    vectorStore: {
      provider: "memory",
      config: {
        collectionName: `test-add-filters-${seq++}`,
        dimension: DIM,
        dbPath: ":memory:",
      },
    },
    historyDbPath: ":memory:",
    embedder: { provider: "openai", config: { apiKey: "test-key" } },
    llm: { provider: "openai", config: { apiKey: "test-key" } },
  } as any);

  // infer:false is enough to exercise the scope handling, so the LLM is never
  // called; the embedder just has to return a well-formed vector.
  (m as any).embedder = {
    embed: async () => new Array(DIM).fill(0.1),
    embedBatch: async (texts: string[]) =>
      texts.map(() => new Array(DIM).fill(0.1)),
  };
  return m;
}

describe("add() does not mutate the caller's filters object", () => {
  it("leaves the caller's object untouched", async () => {
    const memory = createMemory();
    const filters: Record<string, any> = {};

    await memory.add([{ role: "user", content: "alice note" }], {
      userId: "alice",
      infer: false,
      filters,
    });

    expect(filters).toEqual({});
  });

  it("still throws when a reused object is the only source of scope", async () => {
    const memory = createMemory();
    const filters: Record<string, any> = {};

    await memory.add([{ role: "user", content: "alice note" }], {
      userId: "alice",
      infer: false,
      filters,
    });

    // No userId/agentId/runId on this call, so the required-scope guard must
    // fire rather than reading a value left behind by the previous call.
    await expect(
      memory.add([{ role: "user", content: "bob note" }], {
        infer: false,
        filters,
      }),
    ).rejects.toThrow(
      "One of the filters: userId, agentId or runId is required!",
    );
  });

  it("does not store one user's memory under another user's scope", async () => {
    const memory = createMemory();
    const filters: Record<string, any> = {};

    await memory.add([{ role: "user", content: "alice note" }], {
      userId: "alice",
      infer: false,
      filters,
    });
    // A second caller reuses the object and supplies no scope of its own. This
    // must not be silently attributed to alice.
    await memory
      .add([{ role: "user", content: "bob note" }], {
        infer: false,
        filters,
      })
      .catch(() => undefined);

    const alice = await memory.getAll({ filters: { user_id: "alice" } });
    expect(alice.results.map((r) => r.memory)).toEqual(["alice note"]);
  });

  it("keeps scope keys the caller passed in", async () => {
    const memory = createMemory();

    await memory.add([{ role: "user", content: "scoped note" }], {
      infer: false,
      filters: { user_id: "carol" },
    });

    const carol = await memory.getAll({ filters: { user_id: "carol" } });
    expect(carol.results.map((r) => r.memory)).toEqual(["scoped note"]);
  });
});
