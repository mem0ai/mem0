/**
 * Tests for the Backend interface module: error classes and type-level
 * interface verification.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import {
  AuthError,
  NotFoundError,
  APIError,
  type Backend,
  type AddOptions,
  type SearchOptions,
  type ListOptions,
  type DeleteOptions,
  type EntityIds,
} from "../backend/base.ts";
import { PlatformBackend } from "../backend/platform.ts";

// ---------------------------------------------------------------------------
// AuthError
// ---------------------------------------------------------------------------
describe("AuthError", () => {
  it("uses the default message when none is provided", () => {
    const err = new AuthError();
    expect(err.message).toBe(
      "Authentication failed. Your API key may be invalid or expired.",
    );
  });

  it("accepts a custom message", () => {
    const err = new AuthError("Token revoked");
    expect(err.message).toBe("Token revoked");
  });

  it("has name 'AuthError'", () => {
    const err = new AuthError();
    expect(err.name).toBe("AuthError");
  });

  it("is an instance of Error", () => {
    const err = new AuthError();
    expect(err).toBeInstanceOf(Error);
  });
});

// ---------------------------------------------------------------------------
// NotFoundError
// ---------------------------------------------------------------------------
describe("NotFoundError", () => {
  it("includes the path in the message", () => {
    const err = new NotFoundError("/v1/memories/abc-123");
    expect(err.message).toBe("Resource not found: /v1/memories/abc-123");
  });

  it("has name 'NotFoundError'", () => {
    const err = new NotFoundError("/any");
    expect(err.name).toBe("NotFoundError");
  });

  it("is an instance of Error", () => {
    const err = new NotFoundError("/any");
    expect(err).toBeInstanceOf(Error);
  });
});

// ---------------------------------------------------------------------------
// APIError
// ---------------------------------------------------------------------------
describe("APIError", () => {
  it("includes both path and detail in the message", () => {
    const err = new APIError("/v1/memories", "Invalid JSON body");
    expect(err.message).toBe("Bad request to /v1/memories: Invalid JSON body");
  });

  it("has name 'APIError'", () => {
    const err = new APIError("/x", "y");
    expect(err.name).toBe("APIError");
  });

  it("is an instance of Error", () => {
    const err = new APIError("/x", "y");
    expect(err).toBeInstanceOf(Error);
  });
});

// ---------------------------------------------------------------------------
// Backend interface — compile-time verification
// ---------------------------------------------------------------------------
describe("Backend interface (type-level)", () => {
  it("can be referenced as a type", () => {
    // This test verifies that the Backend type and option interfaces
    // import correctly and are usable at the type level.
    const _backendRef: Backend | undefined = undefined;
    const _addOpts: AddOptions = {};
    const _searchOpts: SearchOptions = {};
    const _listOpts: ListOptions = {};
    const _deleteOpts: DeleteOptions = {};
    const _entityIds: EntityIds = {};

    // If this file compiles and this test runs, the interface is valid.
    expect(_backendRef).toBeUndefined();
    expect(_addOpts).toBeDefined();
    expect(_searchOpts).toBeDefined();
    expect(_listOpts).toBeDefined();
    expect(_deleteOpts).toBeDefined();
    expect(_entityIds).toBeDefined();
  });
});

// ---------------------------------------------------------------------------
// PlatformBackend
// ---------------------------------------------------------------------------
describe("PlatformBackend", () => {
  const BASE_URL = "https://api.mem0.ai";
  const API_KEY = "test-api-key-123";

  function createBackend(): PlatformBackend {
    return new PlatformBackend({ apiKey: API_KEY, baseUrl: BASE_URL });
  }

  function mockFetchResponse(
    status: number,
    body: unknown,
    statusText = "OK",
  ): typeof fetch {
    return vi.fn().mockResolvedValue({
      ok: status >= 200 && status < 300,
      status,
      statusText,
      json: vi.fn().mockResolvedValue(body),
    }) as unknown as typeof fetch;
  }

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  // -- Constructor ---------------------------------------------------------
  it("creates an instance with apiKey and baseUrl", () => {
    const backend = createBackend();
    expect(backend).toBeInstanceOf(PlatformBackend);
  });

  it("strips trailing slashes from baseUrl", () => {
    const backend = new PlatformBackend({
      apiKey: API_KEY,
      baseUrl: "https://api.mem0.ai///",
    });
    // We can verify by calling status and checking the base_url in the response
    const mock = mockFetchResponse(200, { status: "ok" });
    vi.stubGlobal("fetch", mock);
    return backend.status().then((result) => {
      expect(result.base_url).toBe("https://api.mem0.ai");
    });
  });

  // -- add() ---------------------------------------------------------------
  it("add() sends POST to /v1/memories/ with correct body structure", async () => {
    const mock = mockFetchResponse(200, { id: "mem-1", memory: "test" });
    vi.stubGlobal("fetch", mock);

    const backend = createBackend();
    const result = await backend.add("Remember this", undefined, {
      userId: "user-1",
    });

    expect(mock).toHaveBeenCalledOnce();
    const [url, opts] = (mock as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("https://api.mem0.ai/v1/memories/");
    expect(opts.method).toBe("POST");
    expect(opts.headers).toMatchObject({
      Authorization: `Token ${API_KEY}`,
      "Content-Type": "application/json",
    });

    const body = JSON.parse(opts.body);
    expect(body.messages).toEqual([{ role: "user", content: "Remember this" }]);
    expect(body.user_id).toBe("user-1");
    expect(result).toEqual({ id: "mem-1", memory: "test" });
  });

  it("add() passes messages directly when provided", async () => {
    const mock = mockFetchResponse(200, { id: "mem-2" });
    vi.stubGlobal("fetch", mock);

    const messages = [
      { role: "user", content: "Hi" },
      { role: "assistant", content: "Hello!" },
    ];
    const backend = createBackend();
    await backend.add(undefined, messages);

    const body = JSON.parse(
      (mock as ReturnType<typeof vi.fn>).mock.calls[0][1].body,
    );
    expect(body.messages).toEqual(messages);
  });

  // -- search() ------------------------------------------------------------
  it("search() sends POST to /v2/memories/search/", async () => {
    const mock = mockFetchResponse(200, [
      { id: "mem-1", score: 0.95, memory: "test" },
    ]);
    vi.stubGlobal("fetch", mock);

    const backend = createBackend();
    const results = await backend.search("find this", { userId: "u1" });

    expect(mock).toHaveBeenCalledOnce();
    const [url, opts] = (mock as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("https://api.mem0.ai/v2/memories/search/");
    expect(opts.method).toBe("POST");

    const body = JSON.parse(opts.body);
    expect(body.query).toBe("find this");
    expect(body.top_k).toBe(10);
    expect(body.threshold).toBe(0.3);
    expect(body.filters).toEqual({ user_id: "u1" });
    expect(results).toEqual([{ id: "mem-1", score: 0.95, memory: "test" }]);
  });

  it("search() unwraps results from object envelope", async () => {
    const mock = mockFetchResponse(200, {
      results: [{ id: "mem-1" }],
    });
    vi.stubGlobal("fetch", mock);

    const backend = createBackend();
    const results = await backend.search("query");
    expect(results).toEqual([{ id: "mem-1" }]);
  });

  // -- get() ---------------------------------------------------------------
  it("get() sends GET to /v1/memories/{id}/", async () => {
    const mock = mockFetchResponse(200, { id: "mem-abc", memory: "test" });
    vi.stubGlobal("fetch", mock);

    const backend = createBackend();
    const result = await backend.get("mem-abc");

    expect(mock).toHaveBeenCalledOnce();
    const [url, opts] = (mock as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("https://api.mem0.ai/v1/memories/mem-abc/");
    expect(opts.method).toBe("GET");
    expect(result).toEqual({ id: "mem-abc", memory: "test" });
  });

  // -- delete() with memoryId ----------------------------------------------
  it("delete() with memoryId sends DELETE to /v1/memories/{id}/", async () => {
    const mock = mockFetchResponse(200, { deleted: true });
    vi.stubGlobal("fetch", mock);

    const backend = createBackend();
    const result = await backend.delete("mem-del-1");

    expect(mock).toHaveBeenCalledOnce();
    const [url, opts] = (mock as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("https://api.mem0.ai/v1/memories/mem-del-1/");
    expect(opts.method).toBe("DELETE");
    expect(result).toEqual({ deleted: true });
  });

  // -- delete() with all=true ----------------------------------------------
  it("delete() with all=true sends DELETE to /v1/memories/ with scope params", async () => {
    const mock = mockFetchResponse(200, { deleted: 5 });
    vi.stubGlobal("fetch", mock);

    const backend = createBackend();
    const result = await backend.delete(undefined, {
      all: true,
      userId: "user-1",
      agentId: "agent-1",
    });

    expect(mock).toHaveBeenCalledOnce();
    const [url, opts] = (mock as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(
      "https://api.mem0.ai/v1/memories/?user_id=user-1&agent_id=agent-1",
    );
    expect(opts.method).toBe("DELETE");
    expect(result).toEqual({ deleted: 5 });
  });

  // -- status() ------------------------------------------------------------
  it("status() returns connected:true on successful ping", async () => {
    const mock = mockFetchResponse(200, { status: "ok" });
    vi.stubGlobal("fetch", mock);

    const backend = createBackend();
    const result = await backend.status();

    expect(result.connected).toBe(true);
    expect(result.backend).toBe("platform");
    expect(result.base_url).toBe(BASE_URL);
  });

  it("status() returns connected:false on failure", async () => {
    const mock = vi
      .fn()
      .mockRejectedValue(new Error("Network error")) as unknown as typeof fetch;
    vi.stubGlobal("fetch", mock);

    const backend = createBackend();
    const result = await backend.status();

    expect(result.connected).toBe(false);
    expect(result.backend).toBe("platform");
    expect(result.error).toBe("Network error");
  });

  // -- Error handling ------------------------------------------------------
  it("throws AuthError on 401", async () => {
    const mock = mockFetchResponse(401, {}, "Unauthorized");
    vi.stubGlobal("fetch", mock);

    const backend = createBackend();
    await expect(backend.get("mem-1")).rejects.toThrow(AuthError);
  });

  it("throws NotFoundError on 404", async () => {
    const mock = mockFetchResponse(404, {}, "Not Found");
    vi.stubGlobal("fetch", mock);

    const backend = createBackend();
    await expect(backend.get("mem-nonexistent")).rejects.toThrow(NotFoundError);
  });

  it("throws APIError on 400", async () => {
    const mock = mockFetchResponse(
      400,
      { detail: "Invalid request body" },
      "Bad Request",
    );
    vi.stubGlobal("fetch", mock);

    const backend = createBackend();
    await expect(backend.add("bad data")).rejects.toThrow(APIError);
  });

  it("throws generic Error on other non-ok status", async () => {
    const mock = mockFetchResponse(
      500,
      { detail: "Internal server error" },
      "Internal Server Error",
    );
    vi.stubGlobal("fetch", mock);

    const backend = createBackend();
    await expect(backend.get("mem-1")).rejects.toThrow("HTTP 500");
  });
});
