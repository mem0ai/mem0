/**
 * Regression tests for issue #5509: add() must not silently drop memories when
 * an embedding fails. Successfully-embedded memories are persisted, then an
 * EmbeddingError is raised reporting the dropped texts.
 */
import fs from "fs";
import os from "os";
import path from "path";
import { Memory } from "../memory";
import { EmbeddingError } from "../memory/errors";

const DIM = 1536; // matches the default in-memory vector store dimension

// Each Memory gets its own temp SQLite file so tests don't share store state.
const tmpDbs: string[] = [];
function freshDbPath(): string {
  const p = path.join(
    fs.mkdtempSync(path.join(os.tmpdir(), "mem0-5509-")),
    "store.db",
  );
  tmpDbs.push(p);
  return p;
}
afterAll(() => {
  for (const p of tmpDbs) {
    try {
      fs.rmSync(path.dirname(p), { recursive: true, force: true });
    } catch {}
  }
});

// A distinct one-hot vector per text so dedup/similarity doesn't collapse them.
function vectorFor(text: string): number[] {
  let h = 0;
  for (const c of text) h = (h * 31 + c.charCodeAt(0)) | 0;
  const v = new Array(DIM).fill(0);
  v[Math.abs(h) % DIM] = 1;
  return v;
}

// embedBatch() always throws to force the per-item fallback; embed() throws for
// any text in `failTexts`, otherwise returns a stable vector.
class FlakyEmbedder {
  public failedTexts: string[] = [];
  constructor(
    private failTexts: Set<string>,
    private error: Error = new Error("Simulated provider 503"),
  ) {}
  async embed(text: string): Promise<number[]> {
    if (this.failTexts.has(text)) {
      this.failedTexts.push(text);
      throw this.error;
    }
    return vectorFor(text);
  }
  async embedBatch(_texts: string[]): Promise<number[][]> {
    throw new Error("Batch endpoint unavailable");
  }
}

function makeStubLLM(facts: string[]) {
  return {
    async generateResponse(): Promise<string> {
      return JSON.stringify({
        memory: facts.map((text, i) => ({ id: String(i), text })),
      });
    },
    async generateChat() {
      return { content: "", role: "assistant" };
    },
  };
}

async function buildMemory(facts: string[], embedder: FlakyEmbedder) {
  const m = new Memory({
    disableHistory: true,
    // Explicit dimension skips the startup embed() probe; fresh db per test.
    vectorStore: {
      provider: "memory",
      config: { dimension: DIM, dbPath: freshDbPath() },
    },
    embedder: { provider: "openai", config: { apiKey: "x" } },
    llm: { provider: "openai", config: { apiKey: "x" } },
  } as any);
  (m as any).embedder = embedder;
  (m as any).llm = makeStubLLM(facts);
  // Finish init now (with the stub in place) so add() doesn't race the probe.
  await (m as any)._ensureInitialized();
  return m;
}

const FACTS = [
  "Alice is friends with Bob",
  "Alice is friends with Carol",
  "Alice is friends with Dave",
];
const FAILED = "Alice is friends with Carol";

jest.setTimeout(30000);

describe("#5509 add() embedding failures are not silent", () => {
  it("throws EmbeddingError when some texts fail to embed", async () => {
    const m = await buildMemory(FACTS, new FlakyEmbedder(new Set([FAILED])));
    await expect(m.add(FACTS.join(". "), { userId: "u1" })).rejects.toThrow(
      EmbeddingError,
    );
  });

  it("persists the memories that did embed and reports the ones that failed", async () => {
    const m = await buildMemory(FACTS, new FlakyEmbedder(new Set([FAILED])));

    let err: EmbeddingError | undefined;
    try {
      await m.add(FACTS.join(". "), { userId: "u2" });
    } catch (e) {
      err = e as EmbeddingError;
    }

    expect(err).toBeInstanceOf(EmbeddingError);
    expect(err!.failedTexts).toEqual([FAILED]);
    // The two facts that embedded were persisted (hybrid, not all-or-nothing).
    expect(err!.persistedCount).toBe(2);
  });

  it("classifies a 503 as a provider error", async () => {
    const m = await buildMemory(
      FACTS,
      new FlakyEmbedder(new Set([FAILED]), new Error("Simulated provider 503")),
    );
    await expect(
      m.add(FACTS.join(". "), { userId: "u3" }),
    ).rejects.toMatchObject({ errorClass: "provider" });
  });

  it("classifies a dimension mismatch as a validation error", async () => {
    const m = await buildMemory(
      FACTS,
      new FlakyEmbedder(
        new Set([FAILED]),
        new Error("Invalid embedding dimension: expected 1536 got 512"),
      ),
    );
    await expect(
      m.add(FACTS.join(". "), { userId: "u4" }),
    ).rejects.toMatchObject({ errorClass: "validation" });
  });

  it("keeps the most actionable errorClass when failures are mixed (provider wins)", async () => {
    // Carol fails with a validation error, Dave with a provider 503.
    class MixedEmbedder extends FlakyEmbedder {
      async embed(text: string): Promise<number[]> {
        if (text === "Alice is friends with Carol") {
          this.failedTexts.push(text);
          throw new Error("Invalid embedding dimension");
        }
        if (text === "Alice is friends with Dave") {
          this.failedTexts.push(text);
          throw new Error("Simulated provider 503");
        }
        return vectorFor(text);
      }
    }
    const m = await buildMemory(FACTS, new MixedEmbedder(new Set()));
    await expect(
      m.add(FACTS.join(". "), { userId: "u6" }),
    ).rejects.toMatchObject({ errorClass: "provider" });
  });

  it("does not throw when every text embeds successfully", async () => {
    const embedder = new FlakyEmbedder(new Set());
    const m = await buildMemory(FACTS, embedder);
    const res = await m.add(FACTS.join(". "), { userId: "u5" });
    expect(res.results.length).toBe(FACTS.length);
    expect(embedder.failedTexts.length).toBe(0);
  });
});
