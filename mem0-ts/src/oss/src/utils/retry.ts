/**
 * Optional retry layer for transient provider failures.
 *
 * LLM and embedding calls fail intermittently in production — provider rate
 * limits (429), gateway/5xx blips, and network resets — and a single failure
 * otherwise fails the whole `add()` / `search()`. `retryCall` wraps a
 * zero-argument async callable with bounded exponential backoff and full
 * jitter, honoring a server-directed `Retry-After` when present. It is opt-in
 * (see `maxRetries` in the LLM/embedder config; `0` keeps the old
 * single-attempt behavior) and dependency-free, so it can live in the core SDK.
 */

/** HTTP status codes worth retrying: rate limit, request timeout, and 5xx. */
const TRANSIENT_STATUS = new Set([408, 409, 425, 429, 500, 502, 503, 504]);

/** Node socket/DNS error codes that indicate a transient network failure. */
const TRANSIENT_CODES = new Set([
  "ECONNRESET",
  "ETIMEDOUT",
  "ECONNREFUSED",
  "EPIPE",
  "ENOTFOUND",
  "EAI_AGAIN",
  "EHOSTUNREACH",
  "ENETUNREACH",
]);

/** Provider SDK error class names that map to transient conditions. */
const TRANSIENT_NAMES = new Set([
  "APIConnectionError",
  "APIConnectionTimeoutError",
  "APITimeoutError",
  "InternalServerError",
  "RateLimitError",
]);

/**
 * Best-effort classification of an error as a transient (retryable) provider
 * failure. Recognizes an HTTP status (`status`/`statusCode`), a Node network
 * error `code`, a provider SDK error class `name`, and unwraps a nested
 * `cause` (the OpenAI SDK wraps socket errors in `APIConnectionError`).
 */
export function isTransientError(err: unknown, depth = 0): boolean {
  if (!err || typeof err !== "object" || depth > 3) return false;
  const e = err as Record<string, any>;

  const status = e.status ?? e.statusCode ?? e.response?.status;
  if (typeof status === "number" && TRANSIENT_STATUS.has(status)) return true;
  if (typeof e.code === "string" && TRANSIENT_CODES.has(e.code)) return true;
  if (typeof e.name === "string" && TRANSIENT_NAMES.has(e.name)) return true;

  if (e.cause && e.cause !== e) return isTransientError(e.cause, depth + 1);
  return false;
}

/** Read a header off either a `Headers`-like object or a plain record. */
function readHeader(headers: any, key: string): string | undefined {
  if (!headers) return undefined;
  if (typeof headers.get === "function") {
    const v = headers.get(key);
    return v == null ? undefined : String(v);
  }
  const v = headers[key] ?? headers[key.toLowerCase()];
  return v == null ? undefined : String(v);
}

/**
 * Server-directed retry delay in milliseconds from a provider error, or `null`
 * when absent/unparseable. Mirrors the OpenAI SDK precedence: `retry-after-ms`
 * (milliseconds) first, then `retry-after` as either numeric seconds or an
 * HTTP-date.
 */
export function getRetryAfterMs(
  err: unknown,
  now: () => number = Date.now,
): number | null {
  const headers = (err as any)?.headers ?? (err as any)?.response?.headers;
  if (!headers) return null;

  const ms = readHeader(headers, "retry-after-ms");
  if (ms !== undefined) {
    const n = Number(ms);
    if (Number.isFinite(n) && n >= 0) return n;
  }

  const ra = readHeader(headers, "retry-after");
  if (ra !== undefined) {
    const secs = Number(ra);
    if (Number.isFinite(secs) && secs >= 0) return secs * 1000;
    const date = Date.parse(ra);
    if (!Number.isNaN(date)) return Math.max(0, date - now());
  }
  return null;
}

export interface RetryOptions {
  /** Number of retries after the first attempt. Must be >= 1 to have effect. */
  maxRetries: number;
  /** Base backoff delay in ms (doubled each attempt). Default 500. */
  initialDelayMs?: number;
  /** Ceiling for any single backoff delay in ms. Default 30000. */
  maxDelayMs?: number;
  /** Override transient-error classification (testing / custom providers). */
  isTransient?: (e: unknown) => boolean;
  /** Override the server `Retry-After` extractor. */
  retryAfterMs?: (e: unknown) => number | null;
  /** Injectable sleep (testing). */
  sleep?: (ms: number) => Promise<void>;
  /** Injectable RNG in [0, 1) for jitter (testing). */
  random?: () => number;
}

const defaultSleep = (ms: number): Promise<void> =>
  new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Run `fn`, retrying on transient errors with exponential backoff and full
 * jitter. A server `Retry-After` (capped at `maxDelayMs`) takes precedence over
 * computed backoff. Non-transient errors, and the final attempt's error, are
 * rethrown unchanged so callers see the original provider exception.
 */
export async function retryCall<T>(
  fn: () => Promise<T>,
  options: RetryOptions,
): Promise<T> {
  const initialDelayMs = options.initialDelayMs ?? 500;
  const maxDelayMs = options.maxDelayMs ?? 30_000;
  const isTransient = options.isTransient ?? isTransientError;
  const retryAfterMs = options.retryAfterMs ?? getRetryAfterMs;
  const sleep = options.sleep ?? defaultSleep;
  const random = options.random ?? Math.random;

  let attempt = 0;
  // eslint-disable-next-line no-constant-condition
  while (true) {
    try {
      return await fn();
    } catch (err) {
      if (attempt >= options.maxRetries || !isTransient(err)) {
        throw err;
      }

      const serverDelay = retryAfterMs(err);
      let delay: number;
      if (serverDelay != null && serverDelay >= 0) {
        delay = Math.min(serverDelay, maxDelayMs);
      } else {
        // Exponential backoff (initialDelay * 2^attempt) with full jitter,
        // i.e. a random point in [0, backoff], to avoid synchronized retries.
        const backoff = Math.min(maxDelayMs, initialDelayMs * 2 ** attempt);
        delay = random() * backoff;
      }

      await sleep(delay);
      attempt += 1;
    }
  }
}

/**
 * Resolve retry settings from a provider config, or `null` when retries are
 * disabled. `maxRetries` is opt-in: `undefined`/`0` disables the layer; a
 * defined value that is not a non-negative integer is a configuration error.
 */
export function resolveRetryOptions(config: {
  maxRetries?: number;
  retryInitialDelayMs?: number;
  retryMaxDelayMs?: number;
}): RetryOptions | null {
  const { maxRetries } = config;
  if (maxRetries === undefined || maxRetries === null) return null;
  if (
    typeof maxRetries !== "number" ||
    !Number.isInteger(maxRetries) ||
    maxRetries < 0
  ) {
    throw new Error(
      `maxRetries must be a non-negative integer, got ${JSON.stringify(maxRetries)}`,
    );
  }
  if (maxRetries === 0) return null;

  return {
    maxRetries,
    initialDelayMs: positiveOr(config.retryInitialDelayMs, 500),
    maxDelayMs: positiveOr(config.retryMaxDelayMs, 30_000),
  };
}

function positiveOr(value: number | undefined, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) && value > 0
    ? value
    : fallback;
}
