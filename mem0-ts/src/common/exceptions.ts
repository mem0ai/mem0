/**
 * Structured exception classes for mem0 TypeScript SDK.
 *
 * Provides specific, actionable exceptions with error codes, suggestions,
 * and debug information. Maps HTTP status codes to appropriate exception types.
 *
 * @example
 * ```typescript
 * import { RateLimitError, MemoryNotFoundError } from 'mem0ai'
 *
 * try {
 *   await client.get(memoryId)
 * } catch (e) {
 *   if (e instanceof MemoryNotFoundError) {
 *     console.log(e.suggestion) // "The requested resource was not found"
 *   } else if (e instanceof RateLimitError) {
 *     await sleep(e.debugInfo.retryAfter ?? 60)
 *   }
 * }
 * ```
 */

export interface MemoryErrorOptions {
  details?: Record<string, unknown>;
  suggestion?: string;
  debugInfo?: Record<string, unknown>;
}

/**
 * Base exception for all memory-related errors.
 *
 * Every mem0 exception includes an error code for programmatic handling,
 * optional details, a user-friendly suggestion, and debug information.
 */
export class MemoryError extends Error {
  readonly errorCode: string;
  readonly details: Record<string, unknown>;
  readonly suggestion?: string;
  readonly debugInfo: Record<string, unknown>;

  constructor(
    message: string,
    errorCode: string,
    options: MemoryErrorOptions = {},
  ) {
    super(message);
    this.name = "MemoryError";
    this.errorCode = errorCode;
    this.details = options.details ?? {};
    this.suggestion = options.suggestion;
    this.debugInfo = options.debugInfo ?? {};

    // Fix prototype chain for instanceof checks
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

/** Raised when authentication fails (401, 403). */
export class AuthenticationError extends MemoryError {
  constructor(
    message: string,
    errorCode: string,
    options?: MemoryErrorOptions,
  ) {
    super(message, errorCode, options);
    this.name = "AuthenticationError";
  }
}

/** Raised when rate limits are exceeded (429). */
export class RateLimitError extends MemoryError {
  constructor(
    message: string,
    errorCode: string,
    options?: MemoryErrorOptions,
  ) {
    super(message, errorCode, options);
    this.name = "RateLimitError";
  }
}

/** Raised when input validation fails (400, 409, 422). */
export class ValidationError extends MemoryError {
  constructor(
    message: string,
    errorCode: string,
    options?: MemoryErrorOptions,
  ) {
    super(message, errorCode, options);
    this.name = "ValidationError";
  }
}

/** Raised when a memory is not found (404). */
export class MemoryNotFoundError extends MemoryError {
  constructor(
    message: string,
    errorCode: string,
    options?: MemoryErrorOptions,
  ) {
    super(message, errorCode, options);
    this.name = "MemoryNotFoundError";
  }
}

/** Raised when network connectivity issues occur (408, 502, 503, 504). */
export class NetworkError extends MemoryError {
  constructor(
    message: string,
    errorCode: string,
    options?: MemoryErrorOptions,
  ) {
    super(message, errorCode, options);
    this.name = "NetworkError";
  }
}

/** Raised when client configuration is invalid. */
export class ConfigurationError extends MemoryError {
  constructor(
    message: string,
    errorCode: string,
    options?: MemoryErrorOptions,
  ) {
    super(message, errorCode, options);
    this.name = "ConfigurationError";
  }
}

/** Raised when memory quota is exceeded (413). */
export class MemoryQuotaExceededError extends MemoryError {
  constructor(
    message: string,
    errorCode: string,
    options?: MemoryErrorOptions,
  ) {
    super(message, errorCode, options);
    this.name = "MemoryQuotaExceededError";
  }
}

/**
 * Coarse failure category for OSS Memory.add() embedding failures.
 * Assigned at the point of detection (not parsed from the message).
 * - provider: embed() / embedBatch() threw
 * - validation: vector returned non-finite or wrong-dimension
 * - internal: catch-all
 */
export type EmbeddingErrorClass = "provider" | "validation" | "internal";

/**
 * Raised when embedding one or more memory texts fails during OSS Memory.add(),
 * which would otherwise cause those memories to be silently dropped.
 * Mirrors the Python SDK EmbeddingError (see #5245 / #5509).
 *
 * Successful memories are persisted before this is thrown (preserve-then-raise).
 * Callers can retry only `failedTexts`; `persistedCount` is the number actually
 * committed via vector-store insert (not merely attempted).
 */
export class EmbeddingError extends MemoryError {
  /** Texts whose embeddings failed and were therefore not persisted. */
  readonly failedTexts: string[];
  /** Number of memories that embedded and were actually inserted. */
  readonly persistedCount: number;
  /** Coarse failure category collapsed as validation > provider > internal. */
  readonly errorClass: EmbeddingErrorClass;

  constructor(
    message: string,
    opts: {
      failedTexts?: string[];
      persistedCount?: number;
      errorClass?: EmbeddingErrorClass;
      suggestion?: string;
      details?: Record<string, unknown>;
      debugInfo?: Record<string, unknown>;
    } = {},
  ) {
    const failedTexts = opts.failedTexts ?? [];
    const persistedCount = opts.persistedCount ?? 0;
    const errorClass = opts.errorClass ?? "internal";
    super(message, "EMBED_001", {
      suggestion:
        opts.suggestion ??
        "Retry only the failed texts; successful memories were already persisted",
      details: {
        ...(opts.details ?? {}),
        failedTexts,
        persistedCount,
        errorClass,
      },
      debugInfo: opts.debugInfo,
    });
    this.name = "EmbeddingError";
    this.failedTexts = failedTexts;
    this.persistedCount = persistedCount;
    this.errorClass = errorClass;
  }
}

// ─── HTTP Status → Exception Mapping ─────────────────────

type MemoryErrorConstructor = new (
  message: string,
  errorCode: string,
  options?: MemoryErrorOptions,
) => MemoryError;

export const HTTP_STATUS_TO_EXCEPTION: Record<number, MemoryErrorConstructor> =
  {
    400: ValidationError,
    401: AuthenticationError,
    403: AuthenticationError,
    404: MemoryNotFoundError,
    408: NetworkError,
    409: ValidationError,
    413: MemoryQuotaExceededError,
    422: ValidationError,
    429: RateLimitError,
    500: MemoryError,
    502: NetworkError,
    503: NetworkError,
    504: NetworkError,
  };

const HTTP_SUGGESTIONS: Record<number, string> = {
  400: "Please check your request parameters and try again",
  401: "Please check your API key and authentication credentials",
  403: "You don't have permission to perform this operation",
  404: "The requested resource was not found",
  408: "Request timed out. Please try again",
  409: "Resource conflict. Please check your request",
  413: "Request too large. Please reduce the size of your request",
  422: "Invalid request data. Please check your input",
  429: "Rate limit exceeded. Please wait before making more requests",
  500: "Internal server error. Please try again later",
  502: "Service temporarily unavailable. Please try again later",
  503: "Service unavailable. Please try again later",
  504: "Gateway timeout. Please try again later",
};

/**
 * Create an appropriate exception based on HTTP response status code.
 *
 * @param statusCode - HTTP status code from the response
 * @param responseText - Response body text
 * @param options - Additional error context (details, debugInfo)
 * @returns An instance of the appropriate MemoryError subclass
 */
export function createExceptionFromResponse(
  statusCode: number,
  responseText: string,
  options: Omit<MemoryErrorOptions, "suggestion"> = {},
): MemoryError {
  const ExceptionClass = HTTP_STATUS_TO_EXCEPTION[statusCode] ?? MemoryError;
  const errorCode = `HTTP_${statusCode}`;
  const suggestion = HTTP_SUGGESTIONS[statusCode] ?? "Please try again later";

  return new ExceptionClass(
    responseText || `HTTP ${statusCode} error`,
    errorCode,
    { ...options, suggestion },
  );
}
