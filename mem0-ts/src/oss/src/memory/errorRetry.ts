// Label-driven, guardrailed handling of embedding failures in add().
import type { MemoryItem } from "../types";
import {
  MemoryError,
  RateLimitError,
  NetworkError,
  ValidationError,
  AuthenticationError,
  MemoryQuotaExceededError,
  EmbeddingError,
  EMBED_ERROR_CODE,
  type EmbedErrorCode,
} from "../../../common/exceptions";

// Values match the Python error_code vocabulary (#5245).
export type ErrorClass =
  | "provider_error"
  | "validation_error"
  | "internal_error";

export type Remediation = "retry" | "reconfigure" | "escalate";

// One dropped text. Plain data so it survives a JSON round-trip.
export interface EmbeddingFailure {
  text: string;
  errorClass: ErrorClass;
  remediation: Remediation;
  errorCode?: EmbedErrorCode;
  retryAfter?: number;
  error: string;
  readonly _payload?: Record<string, any>;
  readonly _memoryId?: string;
}

export interface AddResult {
  results: MemoryItem[];
  failed: EmbeddingFailure[];
}

export interface Classification {
  errorClass: ErrorClass;
  remediation: Remediation;
  errorCode: EmbedErrorCode;
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

// A structurally-bad returned vector is always validation_error; remediation differs.
export function classifyValidation(reason: ValidationReason): Classification {
  const errorCode = EMBED_ERROR_CODE.VALIDATION;
  switch (reason) {
    case "dimension-mismatch":
      return {
        errorClass: "validation_error",
        remediation: "reconfigure",
        errorCode,
      };
    case "non-finite":
    case "empty":
    case "undefined":
      return {
        errorClass: "validation_error",
        remediation: "escalate",
        errorCode,
      };
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

// Normalize a thrown embed() value into a typed MemoryError (status-first,
// then node code, then message as a last resort). Mirrors the client SDK types.
export function toEmbeddingError(err: unknown): MemoryError {
  if (err instanceof MemoryError) return err;

  const e = err as any;
  const raw = e?.status ?? e?.statusCode ?? e?.response?.status;
  const status = typeof raw === "number" ? raw : Number(raw);
  const retryAfter = parseRetryAfter(e);
  const message = err instanceof Error ? err.message : String(err ?? "");
  const debugInfo: Record<string, unknown> =
    retryAfter !== undefined ? { retryAfter } : {};
  const C = EMBED_ERROR_CODE;

  if (Number.isFinite(status)) {
    switch (true) {
      case status === 429:
        return new RateLimitError(message, C.TRANSIENT, { debugInfo });
      case status >= 500 && status < 600:
        return new NetworkError(message, C.TRANSIENT, { debugInfo });
      case status === 401:
      case status === 403:
        return new AuthenticationError(message, C.AUTH);
      case status >= 400 && status < 500:
        return new ValidationError(message, C.VALIDATION);
    }
  }

  const code = typeof e?.code === "string" ? e.code.toUpperCase() : "";
  switch (code) {
    case "ECONNRESET":
    case "ETIMEDOUT":
    case "ENOTFOUND":
    case "EAI_AGAIN":
    case "EPIPE":
      return new NetworkError(message, C.TRANSIENT, { debugInfo });
  }

  const msg = message.toLowerCase();
  switch (true) {
    case /rate.?limit|too many requests/.test(msg):
      return new RateLimitError(message, C.TRANSIENT, { debugInfo });
    case /timeout|timed out|socket hang up|temporarily unavailable|50[234]/.test(
      msg,
    ):
      return new NetworkError(message, C.TRANSIENT, { debugInfo });
    case /\bnan\b|infinity|non-?finite/.test(msg):
      return new ValidationError(message, C.VALIDATION, {
        debugInfo: { surface: "escalate" },
      });
    case /dimension|shape|expected .* got|wrong size|invalid|malformed|empty|length|validation/.test(
      msg,
    ):
      return new ValidationError(message, C.VALIDATION);
  }

  return new EmbeddingError(message, C.TRANSIENT, { debugInfo });
}

function isEmbedCode(c: string): c is EmbedErrorCode {
  return (
    c === EMBED_ERROR_CODE.TRANSIENT ||
    c === EMBED_ERROR_CODE.VALIDATION ||
    c === EMBED_ERROR_CODE.AUTH
  );
}

// Collapse a typed error to the plain wire Classification. Order: specific first.
export function projectError(err: MemoryError): Classification {
  const retryAfter =
    typeof err.debugInfo?.retryAfter === "number"
      ? (err.debugInfo.retryAfter as number)
      : undefined;
  const errorCode: EmbedErrorCode = isEmbedCode(err.errorCode)
    ? err.errorCode
    : EMBED_ERROR_CODE.TRANSIENT;

  switch (true) {
    case err instanceof RateLimitError:
    case err instanceof NetworkError:
      return {
        errorClass: "provider_error",
        remediation: "retry",
        errorCode,
        retryAfter,
      };
    case err instanceof MemoryQuotaExceededError:
    case err instanceof AuthenticationError:
      return {
        errorClass: "provider_error",
        remediation: "escalate",
        errorCode,
      };
    case err instanceof ValidationError:
      return {
        errorClass: "validation_error",
        remediation:
          err.debugInfo?.surface === "escalate" ? "escalate" : "reconfigure",
        errorCode,
      };
    case err instanceof EmbeddingError:
      return {
        errorClass: "provider_error",
        remediation: "retry",
        errorCode,
        retryAfter,
      };
    default:
      return {
        errorClass: "internal_error",
        remediation: "escalate",
        errorCode: EMBED_ERROR_CODE.TRANSIENT,
      };
  }
}

export function classifyEmbedError(err: unknown): Classification {
  return projectError(toEmbeddingError(err));
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
