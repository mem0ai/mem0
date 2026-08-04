/**
 * Tests for label-driven, guardrailed embedding failures + retry in add().
 *
 * add() returns { results, failed[] }: good memories persist, failures carry a
 * label (errorClass / remediation / retryAfter). memory.retryFailed() retries
 * them per label, and the guardrail (NaN/Inf/dim) gates persistence every time.
 */
// add() fires a telemetry POST per call. Left real, every test in this file
// waits ~5s on the network and the suite times out under CI load; stubbed, the
// whole file runs in under a second. Same stub as vector-stores-compat.test.ts.
jest.mock("../src/utils/telemetry", () => ({
  captureClientEvent: jest.fn().mockResolvedValue(undefined),
  isTelemetryEnabled: jest.fn(() => false),
}));

import { Memory } from "../src/memory";
import {
  classifyEmbedError,
  classifyValidation,
  makeVectorValidator,
  toEmbeddingError,
  projectError,
  EmbeddingFailure,
} from "../src/memory/errorRetry";
import {
  RateLimitError,
  NetworkError,
  ValidationError,
  AuthenticationError,
  EmbeddingError,
} from "../../common/exceptions";

const DIM = 1536;

// A distinct vector per text.
function vectorFor(text: string): number[] {
  let h = 0;
  for (const c of text) h = (h * 31 + c.charCodeAt(0)) | 0;
  const v = new Array(DIM).fill(0.01);
  for (let k = 0; k < 5; k++) v[Math.abs(h + k * 97) % DIM] = 0.5;
  return v;
}

// Embedder driven by per-text rules so each scenario is deterministic.
//   "throw:<status>"  -> embed() throws { status }
//   "nan"             -> returns a vector with a NaN element (no throw)
//   "dim"             -> returns a wrong-length vector (no throw)
//   "empty"           -> returns []
//   otherwise         -> a clean one-hot vector
type Rule = "ok" | "nan" | "dim" | "empty" | { throwStatus: number };
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
    if (r === "dim") return new Array(DIM - 2).fill(0.1);
    if (r === "empty") return [];
    return vectorFor(text);
  }
  // Always force the per-item path so per-text rules apply cleanly.
  async embedBatch(_texts: string[]): Promise<number[][]> {
    throw new Error("batch unavailable");
  }
}

let storeSeq = 0;
function buildMemory(rules: Map<string, Rule>) {
  const m = new Memory({
    disableHistory: true,
    vectorStore: {
      provider: "memory",
      config: {
        // In-memory and uniquely named per test: no filesystem I/O, no shared
        // state, and nothing to clean up. Matches the other memory tests.
        collectionName: `test-embed-retry-${storeSeq++}`,
        dimension: DIM,
        dbPath: ":memory:",
      },
    },
    historyDbPath: ":memory:",
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
  it("flagship: good saved, NaN reported as validation_error/escalate, not persisted", async () => {
    const rules = new Map<string, Rule>([[B, "nan"]]);
    const { m } = await ready(rules, [A, B, C]);

    const res = await m.add([A, B, C].join(". "), { userId: "u1" });

    expect(res.results.map((r) => r.memory).sort()).toEqual([A, C].sort());
    expect(res.failed).toHaveLength(1);
    expect(res.failed[0]).toMatchObject({
      text: B,
      errorClass: "validation_error",
      remediation: "escalate",
    });
    const all = await m.getAll({ filters: { user_id: "u1" } });
    expect(all.results.map((r) => r.memory)).not.toContain(B);
  });

  it("provider 503 is labelled provider/retry and not persisted", async () => {
    const rules = new Map<string, Rule>([[B, { throwStatus: 503 }]]);
    const { m } = await ready(rules, [A, B]);

    const res = await m.add([A, B].join(". "), { userId: "u2" });
    expect(res.failed[0]).toMatchObject({
      text: B,
      errorClass: "provider_error",
      remediation: "retry",
    });
    expect(res.results).toHaveLength(1);
  });

  it("wrong dimension is labelled validation/reconfigure", async () => {
    const rules = new Map<string, Rule>([[B, "dim"]]);
    const { m } = await ready(rules, [A, B]);
    const res = await m.add([A, B].join(". "), { userId: "u3" });
    expect(res.failed[0]).toMatchObject({
      text: B,
      errorClass: "validation_error",
      remediation: "reconfigure",
    });
  });

  it("empty vector is caught (not vacuously valid)", async () => {
    const rules = new Map<string, Rule>([[B, "empty"]]);
    const { m } = await ready(rules, [A, B]);
    const res = await m.add([A, B].join(". "), { userId: "u4" });
    expect(res.failed.map((f) => f.text)).toContain(B);
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

  it("happy path: failed is present and empty, never absent", async () => {
    const { m } = await ready(new Map(), [A, B, C]);
    const res = await m.add([A, B, C].join(". "), { userId: "u6" });
    expect(res.results).toHaveLength(3);
    // Always an array: callers branch on .length, never on the key existing,
    // so `failed` is safe to read without a non-null assertion.
    expect(res.failed).toEqual([]);
  });
});

describe("raiseOnPartialFailure: opt-in strict mode (preserve-then-raise)", () => {
  it("raises EmbeddingError with failedTexts/persistedCount, good ones still persisted", async () => {
    const rules = new Map<string, Rule>([[B, { throwStatus: 503 }]]);
    const { m } = await ready(rules, [A, B, C]);

    let err: EmbeddingError | undefined;
    try {
      await m.add([A, B, C].join(". "), {
        userId: "rp1",
        raiseOnPartialFailure: true,
      });
    } catch (e) {
      err = e as EmbeddingError;
    }

    expect(err).toBeInstanceOf(EmbeddingError);
    expect(err!.failedTexts).toEqual([B]);
    expect(err!.persistedCount).toBe(2);

    // Preserve-then-raise: the good ones are in the store despite the throw.
    const all = await m.getAll({ filters: { user_id: "rp1" } });
    expect(all.results.map((r) => r.memory).sort()).toEqual([A, C].sort());
  });

  it("default (flag off) returns { results, failed } and does not throw", async () => {
    const rules = new Map<string, Rule>([[B, { throwStatus: 503 }]]);
    const { m } = await ready(rules, [A, B]);
    const res = await m.add([A, B].join(". "), { userId: "rp2" });
    expect(res.results).toHaveLength(1);
    expect(res.failed).toHaveLength(1);
  });

  it("flag on but nothing fails: does not throw", async () => {
    const { m } = await ready(new Map(), [A, B]);
    const res = await m.add([A, B].join(". "), {
      userId: "rp3",
      raiseOnPartialFailure: true,
    });
    expect(res.results).toHaveLength(2);
  });
});

describe("memory.retryFailed() is label-driven", () => {
  it("retries a provider failure once the provider recovers, and persists it", async () => {
    const rules = new Map<string, Rule>([[B, { throwStatus: 503 }]]);
    const { m, embedder } = await ready(rules, [A, B]);

    const res = await m.add([A, B].join(". "), { userId: "u7" });
    expect(res.failed[0].errorClass).toBe("provider_error");

    // Provider recovers: B now embeds cleanly.
    rules.delete(B);
    const retry = await m.retryFailed(res.failed);

    expect(retry.results.map((r) => r.memory)).toContain(B);
    expect(retry.failed).toHaveLength(0);
    const all = await m.getAll({ filters: { user_id: "u7" } });
    expect(all.results.map((r) => r.memory).sort()).toEqual([A, B].sort());
  });

  it("does not re-embed a validation failure (wrong dim), surfaces it instead", async () => {
    const rules = new Map<string, Rule>([[B, "dim"]]);
    const { m, embedder } = await ready(rules, [A, B]);

    const res = await m.add([A, B].join(". "), { userId: "u8" });
    expect(res.failed[0]).toMatchObject({
      errorClass: "validation_error",
      remediation: "reconfigure",
    });
    const before = embedder.embedCalls;

    const retry = await m.retryFailed(res.failed);

    expect(embedder.embedCalls).toBe(before); // never re-embedded
    expect(retry.results).toHaveLength(0);
    expect(retry.failed).toHaveLength(1);
  });

  it("a NaN failure is surfaced on retry and never persisted (no sanitize)", async () => {
    const rules = new Map<string, Rule>([[B, "nan"]]);
    const { m, embedder } = await ready(rules, [A, B]);

    const res = await m.add([A, B].join(". "), { userId: "u9" });
    expect(res.failed[0]).toMatchObject({
      errorClass: "validation_error",
      remediation: "escalate",
    });
    const before = embedder.embedCalls;

    const retry = await m.retryFailed(res.failed);

    expect(embedder.embedCalls).toBe(before); // no re-embed, no sanitize
    expect(retry.results).toHaveLength(0);
    expect(retry.failed).toHaveLength(1);
    const all = await m.getAll({ filters: { user_id: "u9" } });
    expect(all.results.map((r) => r.memory)).not.toContain(B);
  });

  it("survives a JSON round-trip (plain data, no closures)", async () => {
    const rules = new Map<string, Rule>([[B, { throwStatus: 503 }]]);
    const { m } = await ready(rules, [A, B]);
    const res = await m.add([A, B].join(". "), { userId: "u10" });

    const rehydrated: EmbeddingFailure[] = JSON.parse(
      JSON.stringify(res.failed),
    );
    expect(rehydrated[0].errorCode).toBe(res.failed[0].errorCode);
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
    expect(res.failed.map((f) => f.errorClass)).toEqual([
      "internal_error",
      "internal_error",
    ]);
  });

  it("C2: retrying the same failure twice does not duplicate the memory", async () => {
    const rules = new Map<string, Rule>([[B, { throwStatus: 503 }]]);
    const { m } = await ready(rules, [A, B]);
    const res = await m.add([A, B].join(". "), { userId: "c2" });

    rules.delete(B);
    await m.retryFailed(res.failed);
    await m.retryFailed(res.failed); // second retry should be a no-op

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
    expect(res.failed.map((f) => f.text)).toEqual(["bad text"]);
  });

  it("H4: a short embedBatch return reports the missing tail as a failure (not silently dropped)", async () => {
    const { m } = await ready(new Map(), [A, B, C]);
    // embedBatch returns one fewer vector than texts.
    (m as any).embedder.embedBatch = async (texts: string[]) =>
      texts.slice(0, texts.length - 1).map(() => new Array(DIM).fill(0.1));

    const res = await m.add([A, B, C].join(". "), { userId: "h4" });
    // The tail text has no vector, so it is surfaced as a failure, never dropped.
    expect(res.failed.length).toBeGreaterThan(0);
    expect(res.results.length).toBeLessThan(3);
    // And it is labelled where it was caused: the provider returned nothing,
    // which is retryable, not a malformed vector to escalate and give up on.
    expect(res.failed[0]).toMatchObject({
      errorClass: "provider_error",
      remediation: "retry",
    });
  });
});

/**
 * These read the memory back out of the store. Everything above asserts on
 * add()'s return value, which cannot see a row that was written with the wrong
 * shape. It is still "results.length === 1" either way.
 */
describe("stored shape: what actually lands in the vector store", () => {
  it("P1: infer:false stores the full payload, not just the text", async () => {
    const { m } = await ready(new Map(), []);
    const res = await m.add([{ role: "user", content: "raw note" }], {
      userId: "p1",
      infer: false,
    });
    expect(res.results).toHaveLength(1);

    const stored = await (m as any).vectorStore.get(res.results[0].id);
    // hash drives dedup, textLemmatized drives keyword/hybrid search, and
    // user_id makes the row reachable by its owner. A row missing any of them
    // is persisted but effectively lost, the same failure #5509 is about,
    // just one layer down.
    expect(stored.payload).toMatchObject({ data: "raw note", user_id: "p1" });
    expect(typeof stored.payload.hash).toBe("string");
    expect(typeof stored.payload.textLemmatized).toBe("string");
    expect(typeof stored.payload.createdAt).toBe("string");
  });

  it("P2: a retried infer:false failure is still reachable by its owner", async () => {
    const rules = new Map<string, Rule>([["flaky note", { throwStatus: 503 }]]);
    const { m } = await ready(rules, []);

    const res = await m.add([{ role: "user", content: "flaky note" }], {
      userId: "p2",
      infer: false,
    });
    expect(res.failed).toHaveLength(1);

    rules.delete("flaky note"); // provider recovers
    const retry = await m.retryFailed(res.failed);
    expect(retry.results).toHaveLength(1);

    // The retry must carry the original tenancy. Without it the row exists but
    // getAll/search/deleteAll can never reach it again.
    const all = await m.getAll({ filters: { user_id: "p2" } });
    expect(all.results.map((r) => r.memory)).toContain("flaky note");
  });

  it("P3: a failure with no captured payload is surfaced, never stored ownerless", async () => {
    const { m } = await ready(new Map(), []);
    // A hand-built failure (or one round-tripped through a lossy transport)
    // has no tenancy. Persisting it would create an unreachable row, so the
    // retry must refuse and hand it back instead.
    const orphan: EmbeddingFailure = {
      text: "no owner",
      errorClass: "provider_error",
      remediation: "retry",
      error: "provider 503",
    };
    const retry = await m.retryFailed([orphan]);

    expect(retry.results).toHaveLength(0);
    expect(retry.failed).toHaveLength(1);
    expect(retry.failed[0].errorClass).toBe("internal_error");
    const all = await m.getAll({ filters: { user_id: "p3" } });
    expect(all.results).toHaveLength(0);
  });
});

describe("classifier and validator units", () => {
  it("classifies by status, not a misleading message", () => {
    const err: any = new Error("invalid dimension nan");
    err.status = 503;
    expect(classifyEmbedError(err)).toMatchObject({
      errorClass: "provider_error",
      remediation: "retry",
    });
  });

  it("parses retryAfter on 429", () => {
    const err: any = new Error("rate limited");
    err.status = 429;
    err.retryAfter = 30;
    expect(classifyEmbedError(err)).toMatchObject({
      errorClass: "provider_error",
      retryAfter: 30,
    });
  });

  // A thrown error is always provider_error; the retry decision rides remediation.
  it.each([
    [503, "retry", false],
    [502, "retry", false],
    [429, "retry", true],
    [401, "escalate", false],
    [403, "escalate", false],
    [400, "escalate", false],
  ])("status %i -> provider_error/%s", (status, remediation, hasRetryAfter) => {
    const err: any = new Error("provider call failed");
    err.status = status;
    if (status === 429) err.retryAfter = 30;
    const c = classifyEmbedError(err);
    expect(c.errorClass).toBe("provider_error");
    expect(c.remediation).toBe(remediation);
    expect(c.retryAfter !== undefined).toBe(hasRetryAfter);
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

  it("classifyValidation: a malformed vector is validation_error, remediation on the orthogonal axis", () => {
    expect(classifyValidation("non-finite")).toEqual({
      errorClass: "validation_error",
      remediation: "escalate",
      errorCode: "EMBED_002",
    });
    expect(classifyValidation("empty")).toEqual({
      errorClass: "validation_error",
      remediation: "escalate",
      errorCode: "EMBED_002",
    });
    expect(classifyValidation("dimension-mismatch")).toEqual({
      errorClass: "validation_error",
      remediation: "reconfigure",
      errorCode: "EMBED_002",
    });
  });

  it("classifyValidation: an absent vector is a provider fault, and retryable", () => {
    // A short embedBatch returns nothing for a text. That is not a bad vector
    // the model produced. It is the provider failing to answer, so it must
    // not be labelled escalate-and-never-retry.
    expect(classifyValidation("undefined")).toEqual({
      errorClass: "provider_error",
      remediation: "retry",
      errorCode: "EMBED_001",
    });
  });
});

describe("typed-exception parity (Python error_code shape)", () => {
  it("maps raw errors to typed instances (toEmbeddingError)", () => {
    expect(toEmbeddingError({ status: 429 })).toBeInstanceOf(RateLimitError);
    expect(toEmbeddingError({ status: 503 })).toBeInstanceOf(NetworkError);
    expect(toEmbeddingError({ status: 401 })).toBeInstanceOf(
      AuthenticationError,
    );
    const typed = new RateLimitError("limit", "EMBED_001");
    expect(toEmbeddingError(typed)).toBe(typed); // already typed, passed through
  });

  it("projects typed instances onto the wire Classification", () => {
    expect(projectError(new RateLimitError("x", "EMBED_001"))).toMatchObject({
      errorClass: "provider_error",
      remediation: "retry",
      errorCode: "EMBED_001",
    });
    expect(projectError(new NetworkError("x", "EMBED_001"))).toMatchObject({
      errorClass: "provider_error",
      remediation: "retry",
    });
    expect(
      projectError(new AuthenticationError("x", "EMBED_003")),
    ).toMatchObject({
      errorClass: "provider_error",
      remediation: "escalate",
      errorCode: "EMBED_003",
    });
    expect(projectError(new ValidationError("x", "EMBED_002"))).toMatchObject({
      errorClass: "validation_error",
      remediation: "reconfigure",
      errorCode: "EMBED_002",
    });
  });

  it("a classified provider failure carries errorCode on failed[]", async () => {
    const rules = new Map<string, Rule>([[B, { throwStatus: 503 }]]);
    const { m } = await ready(rules, [A, B]);
    const res = await m.add([A, B].join(". "), { userId: "ec" });
    expect(res.failed[0].errorCode).toBe("EMBED_001");
  });
});
