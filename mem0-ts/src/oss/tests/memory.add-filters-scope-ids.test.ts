/// <reference types="jest" />
/**
 * add() validates and trims userId / agentId / runId, and search() and getAll()
 * validate and trim the same ids when they arrive as filters.user_id /
 * agent_id / run_id. add() did not do that for filters, so a padded, blank or
 * spaced id was stored as given and no read path could ever match it again.
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
        collectionName: `test-add-filters-scope-${seq++}`,
        dimension: DIM,
        dbPath: ":memory:",
      },
    },
    historyDbPath: ":memory:",
    embedder: { provider: "openai", config: { apiKey: "test-key" } },
    llm: { provider: "openai", config: { apiKey: "test-key" } },
  } as any);

  (m as any).embedder = {
    embed: async () => new Array(DIM).fill(0.1),
    embedBatch: async (texts: string[]) =>
      texts.map(() => new Array(DIM).fill(0.1)),
  };
  return m;
}

const note = [{ role: "user", content: "alice note" }];

describe("add() validates scope ids passed through filters", () => {
  it("trims a padded user_id so getAll() can read the memory back", async () => {
    const memory = createMemory();

    await memory.add(note, { infer: false, filters: { user_id: "  alice  " } });

    const { results } = await memory.getAll({ filters: { user_id: "alice" } });
    expect(results).toHaveLength(1);
  });

  it("trims agent_id and run_id the same way", async () => {
    const memory = createMemory();

    await memory.add(note, {
      infer: false,
      filters: { agent_id: " agent-1 ", run_id: " run-1 " },
    });

    const { results } = await memory.getAll({
      filters: { agent_id: "agent-1", run_id: "run-1" },
    });
    expect(results).toHaveLength(1);
  });

  it("rejects a whitespace-only user_id, as the top-level userId already does", async () => {
    const memory = createMemory();

    await expect(
      memory.add(note, { infer: false, filters: { user_id: "   " } }),
    ).rejects.toThrow("Invalid user_id: cannot be empty or whitespace-only");
  });

  it("rejects a user_id with inner whitespace", async () => {
    const memory = createMemory();

    await expect(
      memory.add(note, { infer: false, filters: { user_id: "alice smith" } }),
    ).rejects.toThrow("Invalid user_id: cannot contain whitespace");
  });
});
