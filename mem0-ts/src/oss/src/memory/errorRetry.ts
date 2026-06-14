// Label-driven, guardrailed handling of embedding failures in add().
import type { MemoryItem } from "../types";

// Why an embed failed. Values match the Python error_code vocabulary (#5245).
export type ErrorClass =
  | "provider_error"
  | "validation_error"
  | "internal_error";

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

// A structurally-bad vector caught by inspecting the embedder's output is a
// validation_error regardless of how it's bad; remediation tells them what to do.
export function classifyValidation(reason: ValidationReason): Classification {
  switch (reason) {
    case "dimension-mismatch":
      return { errorClass: "validation_error", remediation: "reconfigure" };
    case "non-finite":
    case "empty":
    case "undefined":
      return { errorClass: "validation_error", remediation: "escalate" };
  }
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
        return {
          errorClass: "provider_error",
          remediation: "retry",
          retryAfter,
        };
      case status === 401:
      case status === 403:
        return { errorClass: "provider_error", remediation: "escalate" };
      case status >= 400 && status < 500:
        return { errorClass: "validation_error", remediation: "reconfigure" };
    }
  }

  const code = typeof e?.code === "string" ? e.code.toUpperCase() : "";
  switch (code) {
    case "ECONNRESET":
    case "ETIMEDOUT":
    case "ENOTFOUND":
    case "EAI_AGAIN":
    case "EPIPE":
      return { errorClass: "provider_error", remediation: "retry", retryAfter };
  }

  const msg = (
    err instanceof Error ? err.message : String(err ?? "")
  ).toLowerCase();
  if (
    /rate.?limit|too many requests|timeout|timed out|socket hang up|temporarily unavailable|50[234]/.test(
      msg,
    )
  ) {
    return { errorClass: "provider_error", remediation: "retry", retryAfter };
  }
  if (/\bnan\b|infinity|non-?finite/.test(msg)) {
    return { errorClass: "validation_error", remediation: "escalate" };
  }
  if (
    /dimension|shape|expected .* got|wrong size|invalid|malformed|empty|length|validation/.test(
      msg,
    )
  ) {
    return { errorClass: "validation_error", remediation: "reconfigure" };
  }
  return { errorClass: "provider_error", remediation: "retry", retryAfter };
}

// provider/retry: wait any retryAfter, re-embed, re-validate, persist if good.
export class ProviderRetryStrategy implements RemediationStrategy {
  readonly errorClass = "provider_error" as const;
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

// validation_error: a structurally-bad vector (wrong dim, NaN/Inf, empty).
// A blind retry would reproduce it, so surface it unchanged for the caller to act on.
export class ValidationSurfaceStrategy implements RemediationStrategy {
  readonly errorClass = "validation_error" as const;
  async apply(f: EmbeddingFailure): Promise<RetryOutcome> {
    return { kind: "stillFailed", failure: f };
  }
}

// internal_error: a mem0-side processing failure (store write, dedup, etc.).
// Re-embedding won't help, so surface it unchanged.
export class InternalSurfaceStrategy implements RemediationStrategy {
  readonly errorClass = "internal_error" as const;
  async apply(f: EmbeddingFailure): Promise<RetryOutcome> {
    return { kind: "stillFailed", failure: f };
  }
}

export const STRATEGIES: Record<ErrorClass, RemediationStrategy> = {
  provider_error: new ProviderRetryStrategy(),
  validation_error: new ValidationSurfaceStrategy(),
  internal_error: new InternalSurfaceStrategy(),
};
