/**
 * Tests for label-driven, guardrailed embedding failures in add().
 *
 * add() returns { results, failed[] }: good memories persist, failures carry a
 * label (errorClass / errorCode / remediation / retryAfter) and an index that
 * locates them in the call, and the guardrail (NaN/Inf/dim) gates persistence
 * every time.
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
} from "../src/memory/errorRetry";
import {
  MemoryError,
  RateLimitError,
  NetworkError,
  ValidationError,
  AuthenticationError,
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

describe("index locates a failure in the call that produced it", () => {
  it("infer:false: index is the caller's own messages position, system slots kept", async () => {
    const rules = new Map<string, Rule>([[B, { throwStatus: 503 }]]);
    const { m } = await ready(rules, []);

    const res = await m.add(
      [
        { role: "system", content: "you are a bot" },
        { role: "user", content: A },
        { role: "user", content: B },
      ],
      { userId: "ix1", infer: false },
    );

    expect(res.failed).toHaveLength(1);
    expect(res.failed[0].index).toBe(2);
    expect(res.results).toHaveLength(1);
  });

  it("infer:false: two identical messages stay distinguishable", async () => {
    // The whole point of index. Keyed on text alone these two failures are
    // indistinguishable, so a caller cannot tell which of their messages to
    // resend.
    const rules = new Map<string, Rule>([[A, { throwStatus: 503 }]]);
    const { m } = await ready(rules, []);

    const res = await m.add(
      [
        { role: "user", content: A },
        { role: "user", content: B },
        { role: "user", content: A },
      ],
      { userId: "ix2", infer: false },
    );

    expect(res.failed.map((f) => f.index)).toEqual([0, 2]);
    expect(new Set(res.failed.map((f) => f.text))).toEqual(new Set([A]));
  });

  it("infer:true: index is the position in the embed request", async () => {
    const rules = new Map<string, Rule>([[B, "nan"]]);
    const { m } = await ready(rules, [A, B, C]);

    const res = await m.add([A, B, C].join(". "), { userId: "ix3" });

    expect(res.failed).toHaveLength(1);
    expect(res.failed[0].index).toBe(1);
  });

  it("every entry carries an index, and they are in one coordinate space", async () => {
    const rules = new Map<string, Rule>([[B, { throwStatus: 503 }]]);
    const { m } = await ready(rules, []);
    // A embeds fine but cannot be stored, B never embeds. Two different
    // failure kinds in one call: both must be numbered off the same list.
    const store = (m as any).vectorStore;
    const realInsert = store.insert.bind(store);
    store.insert = async () => {
      throw new Error("store down");
    };

    const res = await m.add(
      [
        { role: "user", content: A },
        { role: "user", content: B },
      ],
      { userId: "ix4", infer: false },
    );
    store.insert = realInsert;

    expect(res.failed.map((f) => f.index)).toEqual([0, 1]);
    expect(res.failed.every((f) => typeof f.index === "number")).toBe(true);
  });
});

describe("internal_error carries its own code", () => {
  it("a store insert failure is EMBED_004, not a provider blip", async () => {
    const { m } = await ready(new Map(), []);
    const store = (m as any).vectorStore;
    store.insert = async () => {
      throw new Error("store down");
    };

    const res = await m.add([{ role: "user", content: A }], {
      userId: "ie1",
      infer: false,
    });

    expect(res.results).toHaveLength(0);
    expect(res.failed[0]).toMatchObject({
      errorClass: "internal_error",
      remediation: "escalate",
      errorCode: "EMBED_004",
    });
  });

  it("projectError never labels an internal fault EMBED_001", () => {
    // EMBED_001 means "provider blip, retry may work". Saying that about a
    // mem0-side fault sends a caller into a retry loop that cannot succeed.
    const c = projectError(new MemoryError("something of ours broke", "X"));
    expect(c.errorClass).toBe("internal_error");
    expect(c.errorCode).toBe("EMBED_004");
  });
});
