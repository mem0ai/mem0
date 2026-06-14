/**
 * Tests for label-driven, guardrailed embedding failures + retry in add().
 *
 * add() returns { results, failed[] }: good memories persist, failures carry a
 * label (errorClass / remediation / retryAfter). memory.retryFailed() retries
 * them per label, and the guardrail (NaN/Inf/dim) gates persistence every time.
 */
import fs from "fs";
import os from "os";
import path from "path";
import { Memory } from "../memory";
import {
  classifyEmbedError,
  makeVectorValidator,
  sanitizeVector,
  EmbeddingFailure,
} from "../memory/errorRetry";

const DIM = 1536;

// A distinct, dense-ish vector per text. Several non-zero components (not a
// single one-hot) so that zeroing one NaN slot still leaves a healthy L2 norm.
function vectorFor(text: string): number[] {
  let h = 0;
  for (const c of text) h = (h * 31 + c.charCodeAt(0)) | 0;
  const v = new Array(DIM).fill(0.01);
  for (let k = 0; k < 5; k++) v[Math.abs(h + k * 97) % DIM] = 0.5;
  return v;
}

const tmpDbs: string[] = [];
function freshDbPath(): string {
  const p = path.join(
    fs.mkdtempSync(path.join(os.tmpdir(), "mem0-retry-")),
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

// Embedder driven by per-text rules so each scenario is deterministic.
//   "throw:<status>"  -> embed() throws { status }
//   "nan"             -> returns a vector with a NaN element (no throw)
//   "dim"             -> returns a wrong-length vector (no throw)
//   "empty"           -> returns []
//   otherwise         -> a clean one-hot vector
type Rule = "ok" | "nan" | "allnan" | "dim" | "empty" | { throwStatus: number };
class RuleEmbedder {
  public embedCalls = 0;
  constructor(private rules: Map<string, Rule>) {}
  private rule(text: string): Rule {
    return this.rules.get(text) ?? "ok";
  }
  async embed(text: string): Promise<number[]> {
    this.embedCalls++;
    const r = this.rule(text);
    if (typeof r === "object") {
      const err: any = new Error(`provider ${r.throwStatus}`);
      err.status = r.throwStatus;
      throw err;
    }
    if (r === "nan") return vectorFor(text).map((x, i) => (i === 0 ? NaN : x));
    if (r === "allnan") return new Array(DIM).fill(NaN);
    if (r === "dim") return new Array(DIM - 2).fill(0.1);
    if (r === "empty") return [];
    return vectorFor(text);
  }
  // Always force the per-item path so per-text rules apply cleanly.
  async embedBatch(_texts: string[]): Promise<number[][]> {
    throw new Error("batch unavailable");
  }
}

function buildMemory(rules: Map<string, Rule>) {
  const m = new Memory({
    disableHistory: true,
    vectorStore: {
      provider: "memory",
      config: { dimension: DIM, dbPath: freshDbPath() },
    },
    embedder: { provider: "openai", config: { apiKey: "x" } },
    llm: { provider: "openai", config: { apiKey: "x" } },
  } as any);
  return { m, embedder: new RuleEmbedder(rules) };
}

const A = "Alice likes Python";
const B = "Bob lives in Lyon";
const C = "Carol ships fast";

function stubLLM(facts: string[]) {
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

async function ready(rules: Map<string, Rule>, facts: string[]) {
  const { m, embedder } = buildMemory(rules);
  (m as any).embedder = embedder;
  (m as any).llm = stubLLM(facts);
  await (m as any)._ensureInitialized();
  return { m, embedder };
}

jest.setTimeout(30000);

describe("add() returns { results, failed } with labels", () => {
  it("flagship: good saved, NaN reported as internal/escalate, not persisted", async () => {
    const rules = new Map<string, Rule>([[B, "nan"]]);
    const { m } = await ready(rules, [A, B, C]);

    const res = await m.add([A, B, C].join(". "), { userId: "u1" });

    expect(res.results.map((r) => r.memory).sort()).toEqual([A, C].sort());
    expect(res.failed).toHaveLength(1);
    expect(res.failed![0]).toMatchObject({
      text: B,
      errorClass: "internal",
      remediation: "escalate",
    });
    const all = await m.getAll({ filters: { user_id: "u1" } });
    expect(all.results.map((r) => r.memory)).not.toContain(B);
  });

  it("provider 503 is labelled provider/retry and not persisted", async () => {
    const rules = new Map<string, Rule>([[B, { throwStatus: 503 }]]);
    const { m } = await ready(rules, [A, B]);

    const res = await m.add([A, B].join(". "), { userId: "u2" });
    expect(res.failed![0]).toMatchObject({
      text: B,
      errorClass: "provider",
      remediation: "retry",
    });
    expect(res.results).toHaveLength(1);
  });

  it("wrong dimension is labelled validation/reconfigure", async () => {
    const rules = new Map<string, Rule>([[B, "dim"]]);
    const { m } = await ready(rules, [A, B]);
    const res = await m.add([A, B].join(". "), { userId: "u3" });
    expect(res.failed![0]).toMatchObject({
      text: B,
      errorClass: "validation",
      remediation: "reconfigure",
    });
  });

  it("empty vector is caught (not vacuously valid)", async () => {
    const rules = new Map<string, Rule>([[B, "empty"]]);
    const { m } = await ready(rules, [A, B]);
    const res = await m.add([A, B].join(". "), { userId: "u4" });
    expect(res.failed!.map((f) => f.text)).toContain(B);
    expect(res.results).toHaveLength(1);
  });

  it("all-fail returns { results: [], failed } without throwing", async () => {
    const rules = new Map<string, Rule>([
      [A, "nan"],
      [B, "nan"],
    ]);
    const { m } = await ready(rules, [A, B]);
    const res = await m.add([A, B].join(". "), { userId: "u5" });
    expect(res.results).toHaveLength(0);
    expect(res.failed).toHaveLength(2);
  });

  it("happy path: all good, no failed field", async () => {
    const { m } = await ready(new Map(), [A, B, C]);
    const res = await m.add([A, B, C].join(". "), { userId: "u6" });
    expect(res.results).toHaveLength(3);
    expect(res.failed).toBeUndefined();
  });
});

describe("memory.retryFailed() is label-driven", () => {
  it("retries a provider failure once the provider recovers, and persists it", async () => {
    const rules = new Map<string, Rule>([[B, { throwStatus: 503 }]]);
    const { m, embedder } = await ready(rules, [A, B]);

    const res = await m.add([A, B].join(". "), { userId: "u7" });
    expect(res.failed![0].errorClass).toBe("provider");

    // Provider recovers: B now embeds cleanly.
    rules.delete(B);
    const retry = await m.retryFailed(res.failed!);

    expect(retry.results.map((r) => r.memory)).toContain(B);
    expect(retry.failed).toHaveLength(0);
    const all = await m.getAll({ filters: { user_id: "u7" } });
    expect(all.results.map((r) => r.memory).sort()).toEqual([A, B].sort());
  });

  it("refuses to blindly re-embed a reconfigure failure (no embed call)", async () => {
    const rules = new Map<string, Rule>([[B, "dim"]]);
    const { m, embedder } = await ready(rules, [A, B]);

    const res = await m.add([A, B].join(". "), { userId: "u8" });
    const before = embedder.embedCalls;

    const retry = await m.retryFailed(res.failed!);

    expect(embedder.embedCalls).toBe(before); // never re-embedded
    expect(retry.results).toHaveLength(0);
    expect(retry.failed).toHaveLength(1);
    expect(retry.failed[0].error).toMatch(/reconfigur/i);
  });

  it("sanitizes a localized-NaN vector and SAVES it without re-embedding", async () => {
    // One NaN component in 1536 — localized poison. Retry coerces NaN->0
    // (intent lives in the text, untouched) and persists, no wasted re-embed.
    const rules = new Map<string, Rule>([[B, "nan"]]);
    const { m, embedder } = await ready(rules, [A, B]);

    const res = await m.add([A, B].join(". "), { userId: "u9" });
    expect(res.failed![0]).toMatchObject({ errorClass: "internal" });
    const before = embedder.embedCalls;

    const retry = await m.retryFailed(res.failed!);

    expect(embedder.embedCalls).toBe(before); // sanitized the preserved vector, no re-embed
    expect(retry.results.map((r) => r.memory)).toContain(B);
    expect(retry.failed).toHaveLength(0);
    const all = await m.getAll({ filters: { user_id: "u9" } });
    expect(all.results.map((r) => r.memory).sort()).toEqual([A, B].sort());
  });

  it("refuses to save a fully-degenerate (all-NaN) vector", async () => {
    // Whole vector NaN -> sanitizing gives a zero-norm vector a cosine index
    // would silently never return, so it must stay failed, not be stored.
    const rules = new Map<string, Rule>([[B, "allnan"]]);
    const { m } = await ready(rules, [A, B]);

    const res = await m.add([A, B].join(". "), { userId: "u9b" });
    const retry = await m.retryFailed(res.failed!);

    expect(retry.results).toHaveLength(0);
    expect(retry.failed).toHaveLength(1);
    const all = await m.getAll({ filters: { user_id: "u9b" } });
    expect(all.results.map((r) => r.memory)).not.toContain(B);
  });

  it("survives a JSON round-trip (plain data, no closures)", async () => {
    const rules = new Map<string, Rule>([[B, { throwStatus: 503 }]]);
    const { m } = await ready(rules, [A, B]);
    const res = await m.add([A, B].join(". "), { userId: "u10" });

    const rehydrated: EmbeddingFailure[] = JSON.parse(
      JSON.stringify(res.failed),
    );
    rules.delete(B);
    const retry = await m.retryFailed(rehydrated);
    expect(retry.results.map((r) => r.memory)).toContain(B);
  });
});

describe("hardening: insert failures, dedup, infer:false, short batch", () => {
  it("C1: a vector-store insert failure is surfaced, not reported as success", async () => {
    const { m } = await ready(new Map(), [A, B]);
    // Make the store reject every insert after init.
    (m as any).vectorStore.insert = async () => {
      throw new Error("store down");
    };
    const res = await m.add([A, B].join(". "), { userId: "c1" });
    expect(res.results).toHaveLength(0);
    expect(res.failed!.map((f) => f.errorClass)).toEqual([
      "provider",
      "provider",
    ]);
  });

  it("C2: retrying the same failure twice does not duplicate the memory", async () => {
    const rules = new Map<string, Rule>([[B, { throwStatus: 503 }]]);
    const { m } = await ready(rules, [A, B]);
    const res = await m.add([A, B].join(". "), { userId: "c2" });

    rules.delete(B);
    await m.retryFailed(res.failed!);
    await m.retryFailed(res.failed!); // second retry should be a no-op

    const all = await m.getAll({ filters: { user_id: "c2" } });
    const bobs = all.results.filter((r) => r.memory === B);
    expect(bobs).toHaveLength(1);
  });

  it("H1: infer:false captures embed failures instead of throwing", async () => {
    const rules = new Map<string, Rule>([["bad text", { throwStatus: 503 }]]);
    const { m } = await ready(rules, []);
    const res = await m.add(
      [
        { role: "user", content: "good text" },
        { role: "user", content: "bad text" },
      ],
      { userId: "h1", infer: false },
    );
    expect(res.results.map((r) => r.memory)).toEqual(["good text"]);
    expect(res.failed!.map((f) => f.text)).toEqual(["bad text"]);
  });

  it("H4: a short embedBatch return reports the missing tail as a failure (not silently dropped)", async () => {
    const { m } = await ready(new Map(), [A, B, C]);
    // embedBatch returns one fewer vector than texts.
    (m as any).embedder.embedBatch = async (texts: string[]) =>
      texts.slice(0, texts.length - 1).map(() => new Array(DIM).fill(0.1));

    const res = await m.add([A, B, C].join(". "), { userId: "h4" });
    // The tail text has no vector, so it is surfaced as a failure, never dropped.
    expect(res.failed!.length).toBeGreaterThan(0);
    expect(res.results.length).toBeLessThan(3);
  });
});

describe("classifier and validator units", () => {
  it("classifies by status, not a misleading message", () => {
    const err: any = new Error("invalid dimension nan");
    err.status = 503;
    expect(classifyEmbedError(err)).toMatchObject({
      errorClass: "provider",
      remediation: "retry",
    });
  });

  it("parses retryAfter on 429", () => {
    const err: any = new Error("rate limited");
    err.status = 429;
    err.retryAfter = 30;
    expect(classifyEmbedError(err)).toMatchObject({
      errorClass: "provider",
      retryAfter: 30,
    });
  });

  it("validator rejects empty, NaN, wrong-dim, undefined; accepts clean", () => {
    const g = makeVectorValidator(3);
    expect(g.validate([0.1, 0.2, 0.3]).ok).toBe(true);
    expect(g.validate([]).reason).toBe("empty");
    expect(g.validate([0.1, NaN, 0.3]).reason).toBe("non-finite");
    expect(g.validate([0.1, 0.2]).reason).toBe("dimension-mismatch");
    expect(g.validate(undefined).reason).toBe("undefined");
  });

  it("first-vector-wins when no seed dim", () => {
    const g = makeVectorValidator(null);
    expect(g.validate([1, 2, 3, 4]).ok).toBe(true); // sets bar to 4
    expect(g.validate([1, 2, 3]).reason).toBe("dimension-mismatch");
  });
});

describe("sanitizeVector repairs only what is safe to store", () => {
  it("coerces a localized NaN to 0 and keeps a healthy norm", () => {
    const v = new Array(100).fill(0.5);
    v[1] = NaN; // 1% poison, under the 5% threshold
    const s = sanitizeVector(v, 100);
    expect(s.ok).toBe(true);
    expect(s.vector![1]).toBe(0);
  });

  it("keeps Inf as 'huge' (±1e19), float32- and square-safe, never zero", () => {
    const v = new Array(100).fill(0.5);
    v[10] = Infinity;
    v[20] = -Infinity;
    const s = sanitizeVector(v, 100);
    expect(s.ok).toBe(true);
    expect(s.vector!.every((x) => Number.isFinite(x))).toBe(true);
    expect(s.vector![10]).toBe(1e19);
    expect(s.vector![20]).toBe(-1e19);
    // The sentinel must survive float32 storage and squaring (the MAX_VALUE bug).
    expect(Number.isFinite(new Float32Array([s.vector![10]])[0])).toBe(true);
    expect(Number.isFinite(new Float32Array([s.vector![10] ** 2])[0])).toBe(
      true,
    );
  });

  it("refuses an all-NaN vector (degenerate zero norm)", () => {
    const s = sanitizeVector([NaN, NaN, NaN, NaN], 4);
    expect(s.ok).toBe(false);
    // >5% repaired trips the heavy-damage guard first; either way it refuses.
    expect(["too-many-non-finite", "degenerate-zero-norm"]).toContain(s.reason);
  });

  it("refuses a wrong-dimension vector (cannot fabricate axes)", () => {
    const s = sanitizeVector([0.5, 0.5], 4);
    expect(s.ok).toBe(false);
    expect(s.reason).toBe("dimension-mismatch");
  });

  it("refuses when too many components are non-finite (>5%)", () => {
    const v = new Array(100).fill(0.5);
    for (let i = 0; i < 10; i++) v[i] = NaN; // 10% poison
    const s = sanitizeVector(v, 100);
    expect(s.ok).toBe(false);
    expect(s.reason).toBe("too-many-non-finite");
  });

  it("passes a clean vector through unchanged", () => {
    const s = sanitizeVector([0.1, 0.2, 0.3], 3);
    expect(s.ok).toBe(true);
    expect(s.vector).toEqual([0.1, 0.2, 0.3]);
  });
});
