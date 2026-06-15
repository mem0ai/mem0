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

// Stable error codes for embedding failures (parallels the Python SDK).
export const EMBED_ERROR_CODE = {
  TRANSIENT: "EMBED_001", // provider blip (429, 5xx, network) — retry may work
  VALIDATION: "EMBED_002", // bad input/vector (wrong dim, NaN) — retry won't help
  AUTH: "EMBED_003", // auth/permission — needs operator action
} as const;

export type EmbedErrorCode =
  (typeof EMBED_ERROR_CODE)[keyof typeof EMBED_ERROR_CODE];

/**
 * Raised when one or more texts fail to embed during `add()`. The TypeScript
 * parallel of Python's `EmbeddingError`.
 *
 * Successfully-embedded memories are persisted before this is thrown, so a
 * caller catching it can retry only the dropped texts via `failedTexts` rather
 * than re-adding the whole batch.
 */
export class EmbeddingError extends MemoryError {
  /** Texts that failed to embed and were not persisted. */
  readonly failedTexts: string[];
  /** Number of memories persisted by the call before this was thrown. */
  readonly persistedCount: number;

  constructor(
    message: string,
    errorCode: string = EMBED_ERROR_CODE.TRANSIENT,
    options: MemoryErrorOptions & {
      failedTexts?: string[];
      persistedCount?: number;
    } = {},
  ) {
    const { failedTexts = [], persistedCount = 0, ...rest } = options;
    super(message, errorCode, rest);
    this.name = "EmbeddingError";
    this.failedTexts = failedTexts;
    this.persistedCount = persistedCount;
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
