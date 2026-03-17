import {
  MemoryError,
  AuthenticationError,
  RateLimitError,
  ValidationError,
  MemoryNotFoundError,
  NetworkError,
  ConfigurationError,
  MemoryQuotaExceededError,
  createExceptionFromResponse,
  HTTP_STATUS_TO_EXCEPTION,
} from "./exceptions";

describe("MemoryError", () => {
  const error = new MemoryError("test error", "MEM_001", {
    details: { operation: "add" },
    suggestion: "Try again",
    debugInfo: { requestId: "req_123" },
  });

  test("is an instance of Error", () => {
    expect(error).toBeInstanceOf(Error);
  });

  test("has correct message", () => {
    expect(error.message).toBe("test error");
  });

  test("has correct errorCode", () => {
    expect(error.errorCode).toBe("MEM_001");
  });

  test("has correct details", () => {
    expect(error.details).toEqual({ operation: "add" });
  });

  test("has correct suggestion", () => {
    expect(error.suggestion).toBe("Try again");
  });

  test("has correct debugInfo", () => {
    expect(error.debugInfo).toEqual({ requestId: "req_123" });
  });

  test("defaults details to empty object", () => {
    const err = new MemoryError("test error", "MEM_001");
    expect(err.details).toEqual({});
  });

  test("defaults suggestion to undefined", () => {
    const err = new MemoryError("test error", "MEM_001");
    expect(err.suggestion).toBeUndefined();
  });

  test("defaults debugInfo to empty object", () => {
    const err = new MemoryError("test error", "MEM_001");
    expect(err.debugInfo).toEqual({});
  });

  test("is throwable and catchable", () => {
    expect(() => {
      throw new MemoryError("fail", "MEM_001");
    }).toThrow("fail");
  });
});

describe("Exception subclasses", () => {
  const subclasses = [
    { Class: AuthenticationError, name: "AuthenticationError" },
    { Class: RateLimitError, name: "RateLimitError" },
    { Class: ValidationError, name: "ValidationError" },
    { Class: MemoryNotFoundError, name: "MemoryNotFoundError" },
    { Class: NetworkError, name: "NetworkError" },
    { Class: ConfigurationError, name: "ConfigurationError" },
    { Class: MemoryQuotaExceededError, name: "MemoryQuotaExceededError" },
  ] as const;

  test.each(subclasses)("$name extends MemoryError", ({ Class }) => {
    const error = new Class("test", "CODE_001");
    expect(error).toBeInstanceOf(MemoryError);
  });

  test.each(subclasses)("$name extends Error", ({ Class }) => {
    const error = new Class("test", "CODE_001");
    expect(error).toBeInstanceOf(Error);
  });

  test.each(subclasses)("$name has correct name", ({ Class, name }) => {
    const error = new Class("test", "CODE_001");
    expect(error.name).toBe(name);
  });

  test.each(subclasses)("$name supports instanceof checks", ({ Class }) => {
    const error = new Class("test", "CODE_001");
    expect(error instanceof Class).toBe(true);
  });
});

describe("createExceptionFromResponse", () => {
  test("maps 401 to AuthenticationError", () => {
    const error = createExceptionFromResponse(401, "Unauthorized");
    expect(error).toBeInstanceOf(AuthenticationError);
  });

  test("maps 401 to errorCode HTTP_401", () => {
    const error = createExceptionFromResponse(401, "Unauthorized");
    expect(error.errorCode).toBe("HTTP_401");
  });

  test("maps 401 to authentication suggestion", () => {
    const error = createExceptionFromResponse(401, "Unauthorized");
    expect(error.suggestion).toBe(
      "Please check your API key and authentication credentials",
    );
  });

  test("maps 429 to RateLimitError", () => {
    const error = createExceptionFromResponse(429, "Too many requests", {
      debugInfo: { retryAfter: 60 },
    });
    expect(error).toBeInstanceOf(RateLimitError);
  });

  test("maps 429 passes debugInfo through", () => {
    const error = createExceptionFromResponse(429, "Too many requests", {
      debugInfo: { retryAfter: 60 },
    });
    expect(error.debugInfo).toEqual({ retryAfter: 60 });
  });

  test("maps 404 to MemoryNotFoundError", () => {
    const error = createExceptionFromResponse(404, "Not found");
    expect(error).toBeInstanceOf(MemoryNotFoundError);
  });

  test("maps 400 to ValidationError", () => {
    const error = createExceptionFromResponse(400, "Bad request");
    expect(error).toBeInstanceOf(ValidationError);
  });

  test("maps 413 to MemoryQuotaExceededError", () => {
    const error = createExceptionFromResponse(413, "Quota exceeded");
    expect(error).toBeInstanceOf(MemoryQuotaExceededError);
  });

  test.each([502, 503, 504])("maps %i to NetworkError", (code) => {
    const error = createExceptionFromResponse(code, "Service unavailable");
    expect(error).toBeInstanceOf(NetworkError);
  });

  test("maps 500 to MemoryError", () => {
    const error = createExceptionFromResponse(500, "Internal error");
    expect(error).toBeInstanceOf(MemoryError);
  });

  test("maps 500 to errorCode HTTP_500", () => {
    const error = createExceptionFromResponse(500, "Internal error");
    expect(error.errorCode).toBe("HTTP_500");
  });

  test("maps unknown status to MemoryError", () => {
    const error = createExceptionFromResponse(418, "I am a teapot");
    expect(error).toBeInstanceOf(MemoryError);
  });

  test("maps unknown status to correct errorCode", () => {
    const error = createExceptionFromResponse(418, "I am a teapot");
    expect(error.errorCode).toBe("HTTP_418");
  });

  test("maps unknown status to retry suggestion", () => {
    const error = createExceptionFromResponse(418, "I am a teapot");
    expect(error.suggestion).toBe("Please try again later");
  });

  test("uses response text as message", () => {
    const error = createExceptionFromResponse(400, "Invalid user_id format");
    expect(error.message).toBe("Invalid user_id format");
  });

  test("falls back to generic message when response text is empty", () => {
    const error = createExceptionFromResponse(500, "");
    expect(error.message).toBe("HTTP 500 error");
  });

  test("passes details through", () => {
    const error = createExceptionFromResponse(400, "Bad request", {
      details: { field: "user_id", value: "" },
    });
    expect(error.details).toEqual({ field: "user_id", value: "" });
  });
});

describe("HTTP_STATUS_TO_EXCEPTION", () => {
  test("maps 400 to ValidationError", () => {
    expect(HTTP_STATUS_TO_EXCEPTION[400]).toBe(ValidationError);
  });

  test("maps 401 to AuthenticationError", () => {
    expect(HTTP_STATUS_TO_EXCEPTION[401]).toBe(AuthenticationError);
  });

  test("maps 403 to AuthenticationError", () => {
    expect(HTTP_STATUS_TO_EXCEPTION[403]).toBe(AuthenticationError);
  });

  test("maps 404 to MemoryNotFoundError", () => {
    expect(HTTP_STATUS_TO_EXCEPTION[404]).toBe(MemoryNotFoundError);
  });

  test("maps 408 to NetworkError", () => {
    expect(HTTP_STATUS_TO_EXCEPTION[408]).toBe(NetworkError);
  });

  test("maps 409 to ValidationError", () => {
    expect(HTTP_STATUS_TO_EXCEPTION[409]).toBe(ValidationError);
  });

  test("maps 413 to MemoryQuotaExceededError", () => {
    expect(HTTP_STATUS_TO_EXCEPTION[413]).toBe(MemoryQuotaExceededError);
  });

  test("maps 422 to ValidationError", () => {
    expect(HTTP_STATUS_TO_EXCEPTION[422]).toBe(ValidationError);
  });

  test("maps 429 to RateLimitError", () => {
    expect(HTTP_STATUS_TO_EXCEPTION[429]).toBe(RateLimitError);
  });

  test("maps 500 to MemoryError", () => {
    expect(HTTP_STATUS_TO_EXCEPTION[500]).toBe(MemoryError);
  });

  test("maps 502 to NetworkError", () => {
    expect(HTTP_STATUS_TO_EXCEPTION[502]).toBe(NetworkError);
  });

  test("maps 503 to NetworkError", () => {
    expect(HTTP_STATUS_TO_EXCEPTION[503]).toBe(NetworkError);
  });

  test("maps 504 to NetworkError", () => {
    expect(HTTP_STATUS_TO_EXCEPTION[504]).toBe(NetworkError);
  });
});
