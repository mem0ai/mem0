/**
 * Regression: the `memory` provider must give the entity store its OWN db file
 * for ANY dbPath, not only ones ending in ".db".
 *
 * The entity store path was derived with `basePath.replace(/\.db$/, ...)`, a
 * no-op for e.g. ".sqlite" or extensionless paths. That made the entity store
 * open the SAME sqlite file as the main store, so extracted entities leaked
 * into getAll()/search() as phantom memories. The existing entity tests all use
 * dbPath ":memory:" (two connections are separate DBs by sqlite semantics), so
 * they never exercised a persistent non-".db" path.
 */
/// <reference types="jest" />
import { Memory } from "../src/memory";
import type { MemoryConfig } from "../src/types";
import * as os from "os";
import * as path from "path";
import * as fs from "fs";

jest.mock("../src/embeddings/google", () => ({ GoogleEmbedder: jest.fn() }));
jest.mock("../src/llms/google", () => ({ GoogleLLM: jest.fn() }));

// The LLM extracts one fact rich in proper nouns so real entity extraction
// produces entity records (Bob, Berlin, ...) that get written to the entity store.
jest.mock("../src/llms/openai", () => ({
  OpenAILLM: jest.fn().mockImplementation(() => ({
    generateResponse: jest.fn().mockResolvedValue(
      JSON.stringify({
        memory: [
          { id: "0", text: "Alice met Bob in Berlin", attributed_to: "user" },
        ],
      }),
    ),
  })),
}));

const mockEmbedding = new Array(256).fill(0.1);
jest.mock("../src/embeddings/openai", () => ({
  OpenAIEmbedder: jest.fn().mockImplementation(() => ({
    embed: jest.fn().mockResolvedValue(mockEmbedding),
    embedBatch: jest
      .fn()
      .mockImplementation((t: string[]) =>
        Promise.resolve(t.map(() => mockEmbedding)),
      ),
    embeddingDims: 256,
  })),
}));

let tmpRoot: string;
beforeAll(() => {
  tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-entity-dbpath-"));
});
afterAll(() => {
  fs.rmSync(tmpRoot, { recursive: true, force: true });
});

describe("entity store isolation for the memory provider", () => {
  // ".db" always worked; the others used to collide.
  it.each([
    ["ends in .db", "store.db"],
    ["ends in .sqlite", "store.sqlite"],
    ["ends in .sqlite3", "store.sqlite3"],
    ["no extension", "store"],
  ])(
    "keeps entities out of the main store when dbPath %s",
    async (_label, file) => {
      // Own directory per case so the file listing is unambiguous.
      const dir = fs.mkdtempSync(path.join(tmpRoot, "case-"));
      const m = new Memory({
        version: "v1.1",
        embedder: { provider: "openai", config: { apiKey: "k", model: "m" } },
        vectorStore: {
          provider: "memory",
          config: { dbPath: path.join(dir, file), dimension: 256 },
        },
        llm: {
          provider: "openai",
          config: { apiKey: "k", model: "gpt-4o-mini" },
        },
      } as MemoryConfig);

      await m.add("Alice met Bob in Berlin", { userId: "u" });

      const all = await m.getAll({ filters: { user_id: "u" } } as any);
      const memories = all.results.map((r: any) => r.memory);

      // getAll must return only the stored memory, never the extracted entities.
      expect(memories).toEqual(["Alice met Bob in Berlin"]);

      // and the entity store must have been given its own separate file.
      const files = fs.readdirSync(dir);
      expect(files.some((f) => f.includes("_entities"))).toBe(true);
    },
  );
});
