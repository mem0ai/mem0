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

/**
 * One dropped text. Plain data so it survives a JSON round-trip.
 *
 * `index` locates the failure in the call that produced it, so two identical
 * texts in one `add()` stay distinguishable. Every entry carries one, and every
 * entry from a single call is in the same coordinate space:
 *
 * - `infer: false` — position in the `messages` array the caller passed, so
 *   `messages[f.index]` is the message that failed. System messages keep their
 *   slot.
 * - `infer: true` — position in the extracted text list sent to `embedBatch`.
 *   That list is built by mem0, not the caller, so the index separates
 *   duplicate facts but does *not* lead back to the message that produced one:
 *   extraction carries no per-fact provenance.
 */
export interface EmbeddingFailure {
  text: string;
  index: number;
  errorClass: ErrorClass;
  remediation: Remediation;
  errorCode?: EmbedErrorCode;
  retryAfter?: number;
  error: string;
}

/**
 * What `add()` returns. `failed` is always present. An empty array means no
 * memory was dropped on a covered path, never that nothing could have been.
 *
 * Covered today: LLM extraction (`infer: true`), raw writes (`infer: false`),
 * and vector-store insert failures on both. Entity-linking embeds are NOT yet
 * covered and still fail quietly (tracked separately); they never produce a
 * memory row, so a dropped entity costs recall, not stored content.
 */
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

// A structurally-bad *returned* vector is validation_error; remediation differs.
// A *missing* vector is not a bad vector. The provider returned nothing for
// that text (a short embedBatch), which is a provider fault and the single most
// retryable failure in the taxonomy, so it is classified where it was caused.
export function classifyValidation(reason: ValidationReason): Classification {
  if (reason === "undefined") {
    return {
      errorClass: "provider_error",
      remediation: "retry",
      errorCode: EMBED_ERROR_CODE.TRANSIENT,
    };
  }
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

  // A thrown error is always provider_error (the call failed, no vector to
  // inspect); the transient/non-transient split rides remediation. A bad
  // *returned* vector is the only validation_error, handled by classifyValidation.
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
        // Other non-transient 4xx (bad request, quota): provider, not retry-safe.
        return new EmbeddingError(message, C.AUTH, {
          debugInfo: { surface: "escalate" },
        });
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

  // Message is a last resort and only nudges transient-vs-escalate; a thrown
  // error is never validation_error (R2 — don't read structural words off prose).
  const msg = message.toLowerCase();
  switch (true) {
    case /rate.?limit|too many requests/.test(msg):
      return new RateLimitError(message, C.TRANSIENT, { debugInfo });
    case /timeout|timed out|socket hang up|temporarily unavailable|50[234]/.test(
      msg,
    ):
      return new NetworkError(message, C.TRANSIENT, { debugInfo });
  }

  return new EmbeddingError(message, C.TRANSIENT, { debugInfo });
}

function isEmbedCode(c: string): c is EmbedErrorCode {
  return (
    c === EMBED_ERROR_CODE.TRANSIENT ||
    c === EMBED_ERROR_CODE.VALIDATION ||
    c === EMBED_ERROR_CODE.AUTH ||
    c === EMBED_ERROR_CODE.INTERNAL
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
        remediation:
          err.debugInfo?.surface === "escalate" ? "escalate" : "retry",
        errorCode,
        retryAfter,
      };
    default:
      return {
        errorClass: "internal_error",
        remediation: "escalate",
        errorCode: EMBED_ERROR_CODE.INTERNAL,
      };
  }
}

export function classifyEmbedError(err: unknown): Classification {
  return projectError(toEmbeddingError(err));
}
