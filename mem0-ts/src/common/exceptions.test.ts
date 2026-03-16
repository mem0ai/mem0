import {
  MemoryError,
  AuthenticationError,
  RateLimitError,
  ValidationError,
  MemoryNotFoundError,
  NetworkError,
  ConfigurationError,
  MemoryQuotaExceededError,
  VectorStoreError,
  GraphStoreError,
  EmbeddingError,
  LLMError,
  DatabaseError,
  DependencyError,
  createExceptionFromResponse,
  HTTP_STATUS_TO_EXCEPTION,
} from "./exceptions";

describe("MemoryError", () => {
  test("creates error with all fields", () => {
    const error = new MemoryError("test error", "MEM_001", {
      details: { operation: "add" },
      suggestion: "Try again",
      debugInfo: { requestId: "req_123" },
    });

    expect(error).toBeInstanceOf(Error);
    expect(error.message).toBe("test error");
    expect(error.errorCode).toBe("MEM_001");
    expect(error.details).toEqual({ operation: "add" });
    expect(error.suggestion).toBe("Try again");
    expect(error.debugInfo).toEqual({ requestId: "req_123" });
    expect(error.name).toBe("MemoryError");
  });

  test("creates error with defaults for optional fields", () => {
    const error = new MemoryError("test error", "MEM_001");

    expect(error.details).toEqual({});
    expect(error.suggestion).toBeUndefined();
    expect(error.debugInfo).toEqual({});
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
    { Class: VectorStoreError, name: "VectorStoreError" },
    { Class: GraphStoreError, name: "GraphStoreError" },
    { Class: EmbeddingError, name: "EmbeddingError" },
    { Class: LLMError, name: "LLMError" },
    { Class: DatabaseError, name: "DatabaseError" },
    { Class: DependencyError, name: "DependencyError" },
  ] as const;

  test.each(subclasses)("$name extends MemoryError", ({ Class, name }) => {
    const error = new Class("test", "CODE_001");
    expect(error).toBeInstanceOf(MemoryError);
    expect(error).toBeInstanceOf(Error);
    expect(error.name).toBe(name);
  });

  test.each(subclasses)("$name supports instanceof checks", ({ Class }) => {
    const error = new Class("test", "CODE_001");
    expect(error instanceof Class).toBe(true);
  });
});

describe("OSS exception defaults", () => {
  test("VectorStoreError has default error code and suggestion", () => {
    const error = new VectorStoreError("store failed");
    expect(error.errorCode).toBe("VECTOR_001");
    expect(error.suggestion).toBe(
      "Please check your vector store configuration and connection",
    );
  });

  test("GraphStoreError has default error code and suggestion", () => {
    const error = new GraphStoreError("graph failed");
    expect(error.errorCode).toBe("GRAPH_001");
    expect(error.suggestion).toBe(
      "Please check your graph store configuration and connection",
    );
  });

  test("EmbeddingError has default error code and suggestion", () => {
    const error = new EmbeddingError("embed failed");
    expect(error.errorCode).toBe("EMBED_001");
    expect(error.suggestion).toBe(
      "Please check your embedding model configuration",
    );
  });

  test("LLMError has default error code and suggestion", () => {
    const error = new LLMError("llm failed");
    expect(error.errorCode).toBe("LLM_001");
    expect(error.suggestion).toBe(
      "Please check your LLM configuration and API key",
    );
  });

  test("DatabaseError has default error code and suggestion", () => {
    const error = new DatabaseError("db failed");
    expect(error.errorCode).toBe("DB_001");
    expect(error.suggestion).toBe(
      "Please check your database configuration and connection",
    );
  });

  test("DependencyError has default error code and suggestion", () => {
    const error = new DependencyError("missing dep");
    expect(error.errorCode).toBe("DEPS_001");
    expect(error.suggestion).toBe("Please install the required dependencies");
  });
});

describe("createExceptionFromResponse", () => {
  test("maps 401 to AuthenticationError", () => {
    const error = createExceptionFromResponse(401, "Unauthorized");
    expect(error).toBeInstanceOf(AuthenticationError);
    expect(error.errorCode).toBe("HTTP_401");
    expect(error.suggestion).toBe(
      "Please check your API key and authentication credentials",
    );
  });

  test("maps 429 to RateLimitError with debugInfo", () => {
    const error = createExceptionFromResponse(429, "Too many requests", {
      debugInfo: { retryAfter: 60 },
    });
    expect(error).toBeInstanceOf(RateLimitError);
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

  test("maps 502/503/504 to NetworkError", () => {
    for (const code of [502, 503, 504]) {
      const error = createExceptionFromResponse(code, "Service unavailable");
      expect(error).toBeInstanceOf(NetworkError);
    }
  });

  test("maps 500 to MemoryError", () => {
    const error = createExceptionFromResponse(500, "Internal error");
    expect(error).toBeInstanceOf(MemoryError);
    expect(error.errorCode).toBe("HTTP_500");
  });

  test("maps unknown status to MemoryError", () => {
    const error = createExceptionFromResponse(418, "I am a teapot");
    expect(error).toBeInstanceOf(MemoryError);
    expect(error.errorCode).toBe("HTTP_418");
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
  test("contains all expected mappings", () => {
    expect(HTTP_STATUS_TO_EXCEPTION[400]).toBe(ValidationError);
    expect(HTTP_STATUS_TO_EXCEPTION[401]).toBe(AuthenticationError);
    expect(HTTP_STATUS_TO_EXCEPTION[403]).toBe(AuthenticationError);
    expect(HTTP_STATUS_TO_EXCEPTION[404]).toBe(MemoryNotFoundError);
    expect(HTTP_STATUS_TO_EXCEPTION[408]).toBe(NetworkError);
    expect(HTTP_STATUS_TO_EXCEPTION[409]).toBe(ValidationError);
    expect(HTTP_STATUS_TO_EXCEPTION[413]).toBe(MemoryQuotaExceededError);
    expect(HTTP_STATUS_TO_EXCEPTION[422]).toBe(ValidationError);
    expect(HTTP_STATUS_TO_EXCEPTION[429]).toBe(RateLimitError);
    expect(HTTP_STATUS_TO_EXCEPTION[500]).toBe(MemoryError);
    expect(HTTP_STATUS_TO_EXCEPTION[502]).toBe(NetworkError);
    expect(HTTP_STATUS_TO_EXCEPTION[503]).toBe(NetworkError);
    expect(HTTP_STATUS_TO_EXCEPTION[504]).toBe(NetworkError);
  });
});
