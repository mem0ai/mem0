/**
 * Issue #7565: add() stores scope ids from filters unvalidated, so a padded
 * or blank id is written and can never be read back (every read path trims
 * first). add() must validate/trim filter ids like search()/getAll() do.
 */
import { Memory } from "../memory/index";

// This VM has no better-sqlite3 native binding; stub it so the in-memory
// vector store / history can run without a real database file.
jest.mock("better-sqlite3", () => {
  class Stmt {
    run() { return { changes: 1 }; }
    all() { return []; }
    get() { return undefined; }
    bind() { return this; }
  }
  const db = {
    exec: () => {},
    pragma: () => "",
    prepare: () => new Stmt(),
    transaction: (fn: Function) => fn,
    close: () => {},
  };
  return jest.fn(() => db);
});

jest.mock("../utils/factory", () => {
  const actual = jest.requireActual("../utils/factory");
  return {
    ...actual,
    EmbedderFactory: {
      create: jest.fn(() => ({
        embed: async (): Promise<number[]> => [0.1, 0.2],
        embedBatch: async (texts: string[]): Promise<number[][]> =>
          texts.map(() => [0.1, 0.2]),
      })),
    },
    LLMFactory: {
      create: jest.fn(() => ({})),
    },
  };
});

function makeMemory(): Memory {
  return new Memory({
    embedder: { provider: "openai", config: { model: "stub" } },
    vectorStore: { provider: "memory", config: { collectionName: "mem" } },
    llm: { provider: "openai", config: { model: "stub" } },
    disableHistory: true,
  });
}

describe("add() filter id validation", () => {
  it("trims padded filter ids before storing, so the memory can be read back", async () => {
    const m = makeMemory();
    const spy = jest
      .spyOn(m as any, "addToVectorStore")
      .mockResolvedValue({ results: [] });
    await m.add([{ role: "user", content: "note" }], {
      infer: false,
      filters: { user_id: "  alice  " },
    });

    const [, metadata, filters] = spy.mock.calls[0] as [
      Message[],
      Record<string, any>,
      Record<string, any>,
    ];
    // The trimmed id is what actually reaches the store (and metadata).
    expect(filters.user_id).toBe("alice");
    expect(metadata.user_id).toBe("alice");
  });

  it("rejects filter ids containing internal whitespace", async () => {
    const m = makeMemory();
    jest
      .spyOn(m as any, "addToVectorStore")
      .mockResolvedValue({ results: [] });
    await expect(
      m.add([{ role: "user", content: "note" }], {
        infer: false,
        filters: { user_id: "al ice" },
      }),
    ).rejects.toThrow(/cannot contain whitespace/i);
  });
});
