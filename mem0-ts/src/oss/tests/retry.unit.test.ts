/// <reference types="jest" />
/**
 * Unit tests for the dependency-free retry core (utils/retry.ts).
 */
import {
  isTransientError,
  getRetryAfterMs,
  retryCall,
  resolveRetryOptions,
} from "../src/utils/retry";

// A deterministic harness: no real timers, fixed jitter.
function harness(overrides: Partial<Parameters<typeof retryCall>[1]> = {}) {
  const slept: number[] = [];
  return {
    slept,
    options: {
      maxRetries: 3,
      initialDelayMs: 100,
      maxDelayMs: 10_000,
      sleep: async (ms: number) => {
        slept.push(ms);
      },
      random: () => 0.5, // full jitter picks the midpoint
      ...overrides,
    },
  };
}

const httpError = (status: number, headers?: Record<string, string>) =>
  Object.assign(new Error(`HTTP ${status}`), { status, headers });

describe("isTransientError", () => {
  it("treats rate-limit and 5xx statuses as transient", () => {
    expect(isTransientError(httpError(429))).toBe(true);
    expect(isTransientError(httpError(500))).toBe(true);
    expect(isTransientError(httpError(503))).toBe(true);
    expect(isTransientError(httpError(408))).toBe(true);
  });

  it("does not retry client errors like 400/401/404", () => {
    expect(isTransientError(httpError(400))).toBe(false);
    expect(isTransientError(httpError(401))).toBe(false);
    expect(isTransientError(httpError(404))).toBe(false);
  });

  it("treats network error codes as transient", () => {
    expect(
      isTransientError(Object.assign(new Error(), { code: "ECONNRESET" })),
    ).toBe(true);
    expect(
      isTransientError(Object.assign(new Error(), { code: "ETIMEDOUT" })),
    ).toBe(true);
    expect(
      isTransientError(Object.assign(new Error(), { code: "ENOENT" })),
    ).toBe(false);
  });

  it("recognizes provider SDK error class names and nested causes", () => {
    expect(
      isTransientError(
        Object.assign(new Error(), { name: "APIConnectionError" }),
      ),
    ).toBe(true);
    const wrapped = Object.assign(new Error("outer"), {
      cause: Object.assign(new Error("inner"), { code: "ECONNRESET" }),
    });
    expect(isTransientError(wrapped)).toBe(true);
  });

  it("returns false for non-error values", () => {
    expect(isTransientError(null)).toBe(false);
    expect(isTransientError("boom")).toBe(false);
    expect(isTransientError(undefined)).toBe(false);
  });
});

describe("getRetryAfterMs", () => {
  it("prefers retry-after-ms (milliseconds)", () => {
    expect(getRetryAfterMs(httpError(429, { "retry-after-ms": "1500" }))).toBe(
      1500,
    );
  });

  it("reads retry-after as seconds", () => {
    expect(getRetryAfterMs(httpError(429, { "retry-after": "2" }))).toBe(2000);
  });

  it("reads retry-after as an HTTP-date relative to now", () => {
    const now = () => 1_000_000;
    const when = new Date(1_000_000 + 3000).toUTCString();
    const ms = getRetryAfterMs(httpError(503, { "retry-after": when }), now);
    // HTTP-date has 1s resolution, so allow a small window.
    expect(ms).toBeGreaterThanOrEqual(2000);
    expect(ms).toBeLessThanOrEqual(3000);
  });

  it("returns null when absent or unparseable", () => {
    expect(getRetryAfterMs(httpError(429))).toBeNull();
    expect(
      getRetryAfterMs(httpError(429, { "retry-after": "soon" })),
    ).toBeNull();
  });
});

describe("retryCall", () => {
  it("returns immediately on success without sleeping", async () => {
    const { options, slept } = harness();
    const fn = jest.fn().mockResolvedValue("ok");
    await expect(retryCall(fn, options)).resolves.toBe("ok");
    expect(fn).toHaveBeenCalledTimes(1);
    expect(slept).toEqual([]);
  });

  it("retries a transient error and eventually succeeds", async () => {
    const { options, slept } = harness();
    const fn = jest
      .fn()
      .mockRejectedValueOnce(httpError(503))
      .mockRejectedValueOnce(httpError(429))
      .mockResolvedValue("ok");
    await expect(retryCall(fn, options)).resolves.toBe("ok");
    expect(fn).toHaveBeenCalledTimes(3);
    // full jitter at random()=0.5: 0.5 * (100 * 2^attempt) = 50, 100
    expect(slept).toEqual([50, 100]);
  });

  it("does not retry a non-transient error", async () => {
    const { options, slept } = harness();
    const fn = jest.fn().mockRejectedValue(httpError(400));
    await expect(retryCall(fn, options)).rejects.toMatchObject({ status: 400 });
    expect(fn).toHaveBeenCalledTimes(1);
    expect(slept).toEqual([]);
  });

  it("rethrows the original error after exhausting maxRetries", async () => {
    const { options, slept } = harness({ maxRetries: 2 });
    const fn = jest.fn().mockRejectedValue(httpError(500));
    await expect(retryCall(fn, options)).rejects.toMatchObject({ status: 500 });
    expect(fn).toHaveBeenCalledTimes(3); // 1 initial + 2 retries
    expect(slept).toHaveLength(2);
  });

  it("honors a server Retry-After over computed backoff, capped at maxDelayMs", async () => {
    const { options, slept } = harness({ maxDelayMs: 5000 });
    const fn = jest
      .fn()
      .mockRejectedValueOnce(httpError(429, { "retry-after-ms": "999999" }))
      .mockResolvedValue("ok");
    await expect(retryCall(fn, options)).resolves.toBe("ok");
    expect(slept).toEqual([5000]); // 999999 capped to maxDelayMs
  });

  it("caps exponential backoff at maxDelayMs", async () => {
    const { options, slept } = harness({
      maxRetries: 5,
      initialDelayMs: 1000,
      maxDelayMs: 3000,
      random: () => 1, // no jitter reduction, so delay == backoff
    });
    const fn = jest.fn().mockRejectedValue(httpError(503));
    await expect(retryCall(fn, options)).rejects.toBeDefined();
    // 1000, 2000, 3000(capped), 3000, 3000
    expect(slept).toEqual([1000, 2000, 3000, 3000, 3000]);
  });
});

describe("resolveRetryOptions", () => {
  it("returns null (disabled) for undefined or 0", () => {
    expect(resolveRetryOptions({})).toBeNull();
    expect(resolveRetryOptions({ maxRetries: 0 })).toBeNull();
  });

  it("returns options for a positive integer", () => {
    expect(resolveRetryOptions({ maxRetries: 3 })).toMatchObject({
      maxRetries: 3,
      initialDelayMs: 500,
      maxDelayMs: 30_000,
    });
  });

  it("carries custom delays through", () => {
    expect(
      resolveRetryOptions({
        maxRetries: 2,
        retryInitialDelayMs: 250,
        retryMaxDelayMs: 5000,
      }),
    ).toMatchObject({ initialDelayMs: 250, maxDelayMs: 5000 });
  });

  it("throws on a negative or non-integer maxRetries", () => {
    expect(() => resolveRetryOptions({ maxRetries: -1 })).toThrow(
      /non-negative integer/,
    );
    expect(() => resolveRetryOptions({ maxRetries: 1.5 })).toThrow(
      /non-negative integer/,
    );
  });
});
