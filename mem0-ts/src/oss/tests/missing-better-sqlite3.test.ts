// better-sqlite3 is a native addon, so it must not load until a SQLite-backed store is used.
// Serverless and edge runtimes cannot bind it, and with disableHistory and a non-SQLite vector
// store nothing ever needs it (#3291).

jest.mock("better-sqlite3", () => {
  throw new Error("Cannot find module 'better-sqlite3'");
});

const INSTALL_HINT = "Install it with: npm install better-sqlite3";

describe("mem0ai/oss without better-sqlite3 installed", () => {
  const originalTelemetry = process.env.MEM0_TELEMETRY;

  beforeAll(() => {
    process.env.MEM0_TELEMETRY = "false";
  });

  afterAll(() => {
    process.env.MEM0_TELEMETRY = originalTelemetry;
  });

  beforeEach(() => {
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test("mem0ai/oss loads", async () => {
    await expect(import("../src")).resolves.toHaveProperty("Memory");
  });

  test("Memory with disableHistory and a non-SQLite vector store works", async () => {
    const { Memory } = await import("../src");
    const client = {
      addVectors: jest.fn(),
      similaritySearchVectorWithScore: jest.fn().mockResolvedValue([]),
    };
    const memory = new Memory({
      disableHistory: true,
      embedder: { provider: "openai", config: { apiKey: "sk-test" } },
      llm: { provider: "openai", config: { apiKey: "sk-test" } },
      vectorStore: {
        provider: "langchain",
        config: { client, dimension: 3 },
      },
    });

    await expect(memory.history("memory-1")).resolves.toEqual([]);
  });

  test("SQLite history store explains how to install better-sqlite3", async () => {
    const { SQLiteManager } = await import("../src/storage/SQLiteManager");
    const manager = new SQLiteManager(":memory:");

    await expect(manager.getHistory("memory-1")).rejects.toThrow(
      `The 'better-sqlite3' package is required to use the SQLite history store. ${INSTALL_HINT}`,
    );
  });

  test("memory vector store explains how to install better-sqlite3", async () => {
    const { MemoryVectorStore } = await import("../src/vector_stores/memory");
    const store = new MemoryVectorStore({ dimension: 3, dbPath: ":memory:" });

    await expect(store.initialize()).rejects.toThrow(
      `The 'better-sqlite3' package is required to use the memory vector store. ${INSTALL_HINT}`,
    );
  });
});
