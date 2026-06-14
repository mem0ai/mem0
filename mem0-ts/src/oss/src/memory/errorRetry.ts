// Label-driven, guardrailed handling of embedding failures in add().
import type { MemoryItem } from "../types";

// Why an embed failed. "internal" = provider returned a poison vector without erroring.
export type ErrorClass = "provider" | "validation" | "internal";

// What the caller should do about it.
export type Remediation = "retry" | "reconfigure" | "escalate";

// One dropped text. Plain data so it survives a JSON round-trip and can be retried later.
export interface EmbeddingFailure {
  text: string;
  errorClass: ErrorClass;
  remediation: Remediation;
  retryAfter?: number;
  error: string;
  readonly _payload?: Record<string, any>;
  readonly _memoryId?: string;
  // The poison vector, kept so retry can sanitize it without re-fetching.
  readonly _vector?: number[];
}

// What add() and retryFailed() both return.
export interface AddResult {
  results: MemoryItem[];
  failed: EmbeddingFailure[];
}

export interface Classification {
  errorClass: ErrorClass;
  remediation: Remediation;
  retryAfter?: number;
}

export type ValidationReason =
  | "undefined"
  | "empty"
  | "non-finite"
  | "dimension-mismatch";

export interface VectorValidation {
  ok: boolean;
  reason?: ValidationReason;
}

export interface RetryContext {
  validate(vec: number[] | undefined): VectorValidation;
  persist(f: EmbeddingFailure, vec: number[]): Promise<MemoryItem>;
  sleep(ms: number): Promise<void>;
  embed(text: string): Promise<number[]>;
  expectedDim(): number | null;
}

export type RetryOutcome =
  | { kind: "persisted"; item: MemoryItem }
  | { kind: "stillFailed"; failure: EmbeddingFailure };

export interface RemediationStrategy {
  readonly errorClass: ErrorClass;
  apply(f: EmbeddingFailure, ctx: RetryContext): Promise<RetryOutcome>;
}

// First-good-vector-wins guardrail, one instance per add()/retry run.
export function makeVectorValidator(seedDim: number | null = null) {
  let expectedDim = seedDim;
  return {
    validate(vec: number[] | undefined): VectorValidation {
      if (vec === undefined || vec === null || !Array.isArray(vec)) {
        return { ok: false, reason: "undefined" };
      }
      if (vec.length === 0) return { ok: false, reason: "empty" };
      for (let i = 0; i < vec.length; i++) {
        if (typeof vec[i] !== "number" || !Number.isFinite(vec[i])) {
          return { ok: false, reason: "non-finite" };
        }
      }
      if (expectedDim !== null && vec.length !== expectedDim) {
        return { ok: false, reason: "dimension-mismatch" };
      }
      if (expectedDim === null) expectedDim = vec.length;
      return { ok: true };
    },
  };
}

export function classifyValidation(reason: ValidationReason): Classification {
  switch (reason) {
    case "dimension-mismatch":
      return { errorClass: "validation", remediation: "reconfigure" };
    case "non-finite":
    case "empty":
    case "undefined":
      // No usable vector to store, and a retry can't conjure one — escalate.
      return { errorClass: "internal", remediation: "escalate" };
  }
}

// Keep Inf's "huge" meaning as ±1e19 — float32-safe and safe to square.
export const POS_INF_SENTINEL = 1e19;
export const NEG_INF_SENTINEL = -1e19;

// --- Sanitizer ------------------------------------------------------------
export type SanitizeReason =
  | "undefined"
  | "empty"
  | "dimension-mismatch"
  | "too-many-non-finite"
  | "degenerate-zero-norm";

export interface SanitizeResult {
  ok: boolean;
  vector?: number[];
  reason?: SanitizeReason;
  detail?: string;
}

const NORM_EPS = 1e-12;
const MAX_REPAIR_FRACTION = 0.05;

// NaN -> 0, ±Inf -> ±1e19 sentinel. Refuses on wrong dimension, too many repairs,
// or a zero-norm result a cosine index would silently never return.
export function sanitizeVector(
  vec: number[] | undefined | null,
  expectedDim: number | null,
): SanitizeResult {
  if (vec == null || !Array.isArray(vec))
    return { ok: false, reason: "undefined" };
  if (vec.length === 0) return { ok: false, reason: "empty" };
  if (expectedDim !== null && vec.length !== expectedDim) {
    return {
      ok: false,
      reason: "dimension-mismatch",
      detail: `expected ${expectedDim} dims, got ${vec.length}`,
    };
  }

  const out = new Array<number>(vec.length);
  let repaired = 0;
  let firstBad = -1;
  for (let i = 0; i < vec.length; i++) {
    const x = vec[i];
    if (typeof x === "number" && Number.isFinite(x)) {
      out[i] = x;
      continue;
    }
    out[i] =
      x === Infinity
        ? POS_INF_SENTINEL
        : x === -Infinity
          ? NEG_INF_SENTINEL
          : 0;
    repaired++;
    if (firstBad === -1) firstBad = i;
  }

  // Norm is measured on the vector we actually store.
  let sumSq = 0;
  for (let i = 0; i < out.length; i++) sumSq += out[i] * out[i];
  const degenerate = Math.sqrt(sumSq) <= NORM_EPS;

  if (repaired === 0) {
    if (degenerate)
      return {
        ok: false,
        reason: "degenerate-zero-norm",
        detail: "all-zero vector",
      };
    return { ok: true, vector: out };
  }

  const bad = vec[firstBad] as number;
  const label = Number.isNaN(bad)
    ? "NaN"
    : bad === Infinity
      ? "Inf"
      : bad === -Infinity
        ? "-Inf"
        : "non-number";
  const detail = `non-finite: ${label} at index ${firstBad} (${repaired}/${vec.length} components)`;

  if (repaired / vec.length > MAX_REPAIR_FRACTION) {
    return { ok: false, reason: "too-many-non-finite", detail };
  }
  if (degenerate) return { ok: false, reason: "degenerate-zero-norm", detail };
  return { ok: true, vector: out, detail };
}

function parseRetryAfter(e: any): number | undefined {
  const h =
    e?.response?.headers?.["retry-after"] ??
    e?.headers?.["retry-after"] ??
    e?.retryAfter;
  if (h == null) return undefined;
  const n = Number(h);
  return Number.isFinite(n) && n >= 0 ? n : undefined;
}

// Status-first classifier for a thrown embed() error; message is only a fallback.
export function classifyEmbedError(err: unknown): Classification {
  const e = err as any;
  const raw = e?.status ?? e?.statusCode ?? e?.response?.status;
  const status = typeof raw === "number" ? raw : Number(raw);
  const retryAfter = parseRetryAfter(e);

  if (Number.isFinite(status)) {
    switch (true) {
      case status === 429:
      case status >= 500 && status < 600:
        return { errorClass: "provider", remediation: "retry", retryAfter };
      case status === 401:
      case status === 403:
        return { errorClass: "provider", remediation: "escalate" };
      case status >= 400 && status < 500:
        return { errorClass: "validation", remediation: "reconfigure" };
    }
  }

  const code = typeof e?.code === "string" ? e.code.toUpperCase() : "";
  switch (code) {
    case "ECONNRESET":
    case "ETIMEDOUT":
    case "ENOTFOUND":
    case "EAI_AGAIN":
    case "EPIPE":
      return { errorClass: "provider", remediation: "retry", retryAfter };
  }

  const msg = (
    err instanceof Error ? err.message : String(err ?? "")
  ).toLowerCase();
  if (
    /rate.?limit|too many requests|timeout|timed out|socket hang up|temporarily unavailable|50[234]/.test(
      msg,
    )
  ) {
    return { errorClass: "provider", remediation: "retry", retryAfter };
  }
  if (/dimension|shape|expected .* got|wrong size/.test(msg)) {
    return { errorClass: "validation", remediation: "reconfigure" };
  }
  if (/\bnan\b|infinity|non-?finite/.test(msg)) {
    return { errorClass: "internal", remediation: "escalate" };
  }
  if (/invalid|malformed|empty|length|validation/.test(msg)) {
    return { errorClass: "validation", remediation: "reconfigure" };
  }
  return { errorClass: "provider", remediation: "retry", retryAfter };
}

// provider/retry: wait any retryAfter, re-embed, re-validate, persist if good.
export class ProviderRetryStrategy implements RemediationStrategy {
  readonly errorClass = "provider" as const;
  async apply(f: EmbeddingFailure, ctx: RetryContext): Promise<RetryOutcome> {
    if (f.retryAfter && f.retryAfter > 0) await ctx.sleep(f.retryAfter * 1000);
    let vec: number[];
    try {
      vec = await ctx.embed(f.text);
    } catch (e) {
      const c = classifyEmbedError(e);
      return {
        kind: "stillFailed",
        failure: {
          ...f,
          ...c,
          error: e instanceof Error ? e.message : String(e),
        },
      };
    }
    const v = ctx.validate(vec);
    if (!v.ok) {
      const c = classifyValidation(v.reason!);
      return {
        kind: "stillFailed",
        failure: { ...f, ...c, error: `re-embed produced ${v.reason} vector` },
      };
    }
    return { kind: "persisted", item: await ctx.persist(f, vec) };
  }
}

// validation/reconfigure: would fail identically on retry, so surface it unchanged.
export class ValidationReconfigureStrategy implements RemediationStrategy {
  readonly errorClass = "validation" as const;
  async apply(f: EmbeddingFailure): Promise<RetryOutcome> {
    return {
      kind: "stillFailed",
      failure: {
        ...f,
        error: `${f.error} — not retried: requires reconfiguration (fix the embedder model or vectorStore dimension).`,
      },
    };
  }
}

// internal/escalate: poison vector returned. Sanitize the preserved vector once
// and persist if safe; never re-embed, never store a degenerate vector.
export class InternalEscalateStrategy implements RemediationStrategy {
  readonly errorClass = "internal" as const;
  async apply(f: EmbeddingFailure, ctx: RetryContext): Promise<RetryOutcome> {
    if (!f._vector) {
      return {
        kind: "stillFailed",
        failure: {
          ...f,
          error: `${f.error} — no vector preserved to sanitize`,
        },
      };
    }
    const s = sanitizeVector(f._vector, ctx.expectedDim());
    if (s.ok && s.vector) {
      return { kind: "persisted", item: await ctx.persist(f, s.vector) };
    }
    const c: Classification =
      s.reason === "dimension-mismatch"
        ? { errorClass: "validation", remediation: "reconfigure" }
        : { errorClass: "internal", remediation: "escalate" };
    return {
      kind: "stillFailed",
      failure: { ...f, ...c, error: s.detail ?? `unsanitizable: ${s.reason}` },
    };
  }
}

export const STRATEGIES: Record<ErrorClass, RemediationStrategy> = {
  provider: new ProviderRetryStrategy(),
  validation: new ValidationReconfigureStrategy(),
  internal: new InternalEscalateStrategy(),
};
