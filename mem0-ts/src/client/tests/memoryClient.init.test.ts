/**
 * MemoryClient unit tests — constructor, validation, ping.
 */
import { MemoryClient } from "../mem0";
import {
  MemoryNotFoundError,
  ValidationError,
  MemoryError,
} from "../../common/exceptions";
import {
  createMockFetch,
  TEST_API_KEY,
  TEST_HOST,
  TEST_ORG_ID,
  TEST_PROJECT_ID,
} from "./helpers";
import {
  setupMockFetch,
  installConsoleSuppression,
  MOCK_PING_RESPONSE,
} from "./setup";

installConsoleSuppression();

// ─── Initialization ──────────────────────────────────────

describe("MemoryClient - Initialization", () => {
  beforeEach(() => setupMockFetch());

  test("throws when API key is empty string", () => {
    expect(() => new MemoryClient({ apiKey: "" })).toThrow(
      "Mem0 API key is required",
    );
  });

  test("throws when API key is whitespace only", () => {
    expect(() => new MemoryClient({ apiKey: "   " })).toThrow(
      "Mem0 API key cannot be empty",
    );
  });

  test("throws when API key is not a string", () => {
    expect(
      () => new MemoryClient({ apiKey: 123 as unknown as string }),
    ).toThrow("Mem0 API key must be a string");
  });

  test("sets default host to https://api.mem0.ai", () => {
    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    expect(client.host).toBe("https://api.mem0.ai");
  });

  test("uses custom host when provided", () => {
    const client = new MemoryClient({ apiKey: TEST_API_KEY, host: TEST_HOST });
    expect(client.host).toBe(TEST_HOST);
  });

  test("sets Authorization header with Token prefix", () => {
    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    expect(client.headers["Authorization"]).toBe(`Token ${TEST_API_KEY}`);
  });

  test("creates axios client with 60s timeout", () => {
    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    expect(client.client.defaults.timeout).toBe(60000);
  });
});

// ─── Ping ────────────────────────────────────────────────

describe("MemoryClient - ping()", () => {
  test("sets telemetryId from user_email in response", async () => {
    setupMockFetch();
    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.ping();
    expect(client.telemetryId).toBe("test@example.com");
  });

  test("throws AuthenticationError on 401 response", async () => {
    const { AuthenticationError } = await import("../../common/exceptions");
    const responses = new Map<string, { status: number; body: unknown }>();
    responses.set("/v1/ping/", {
      status: 401,
      body: "Invalid API key",
    });
    global.fetch = createMockFetch(responses);

    const client = new MemoryClient({ apiKey: "bad-key" });
    await expect(client.ping()).rejects.toThrow(AuthenticationError);
  });

  test("throws on invalid (non-object) response format", async () => {
    const responses = new Map<string, { status: number; body: unknown }>();
    responses.set("/v1/ping/", { status: 200, body: "not an object" });
    global.fetch = createMockFetch(responses);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await expect(client.ping()).rejects.toThrow("Invalid response format");
  });

  test("throws on status !== ok in response", async () => {
    const responses = new Map<string, { status: number; body: unknown }>();
    responses.set("/v1/ping/", {
      status: 200,
      body: { status: "error", message: "API Key is invalid" },
    });
    global.fetch = createMockFetch(responses);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await expect(client.ping()).rejects.toThrow("API Key is invalid");
  });
});

// ─── Single constructor ping (no per-call ping) ──────────

describe("MemoryClient - single constructor ping", () => {
  const countPings = (mock: jest.Mock) =>
    mock.mock.calls.filter((c: [string, RequestInit]) =>
      c[0].includes("/v1/ping/"),
    ).length;

  test("pings at most once across constructor and multiple API calls", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/mem_1/", { status: 200, body: { id: "mem_1" } });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.get("mem_1");
    await client.get("mem_1");
    await client.get("mem_1");

    expect(countPings(mock)).toBe(1);
  });

  test("concurrent first calls do not trigger extra pings", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/mem_1/", { status: 200, body: { id: "mem_1" } });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await Promise.all([
      client.get("mem_1"),
      client.get("mem_1"),
      client.get("mem_1"),
    ]);

    expect(countPings(mock)).toBe(1);
  });

  test("does not re-ping per call when ping returns no user_email", async () => {
    const responses = new Map<string, { status: number; body: unknown }>();
    responses.set("/v1/ping/", { status: 200, body: { status: "ok" } });
    responses.set("/v1/memories/mem_1/", {
      status: 200,
      body: { id: "mem_1" },
    });
    const mock = createMockFetch(responses);
    global.fetch = mock;

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.get("mem_1");
    await client.get("mem_1");

    expect(countPings(mock)).toBe(1);
    expect(client.telemetryId).not.toBe("");
  });

  test("API calls still work when the ping endpoint is unavailable", async () => {
    const responses = new Map<string, { status: number; body: unknown }>();
    responses.set("/v1/ping/", { status: 500, body: "no ping here" });
    responses.set("/v1/memories/mem_1/", {
      status: 200,
      body: { id: "mem_1" },
    });
    const mock = createMockFetch(responses);
    global.fetch = mock;

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await expect(client.get("mem_1")).resolves.toEqual({ id: "mem_1" });
    await client.get("mem_1");

    expect(countPings(mock)).toBe(1);
  });
});

// ─── lazyInit option ──────────────────────────────────

describe("MemoryClient - lazyInit option", () => {
  const countPings = (mock: jest.Mock) =>
    mock.mock.calls.filter((c: [string, RequestInit]) =>
      c[0].includes("/v1/ping/"),
    ).length;

  test("never calls /v1/ping/ and API calls work", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/mem_1/", { status: 200, body: { id: "mem_1" } });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({
      apiKey: TEST_API_KEY,
      lazyInit: true,
    });
    await expect(client.get("mem_1")).resolves.toEqual({ id: "mem_1" });
    await client.get("mem_1");

    expect(countPings(mock)).toBe(0);
    expect(client.telemetryId).not.toBe("");
  });

  test("getProject resolves org/project ids with a single lazy ping", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/api/v1/orgs/organizations/", {
      status: 200,
      body: { custom_instructions: "Be helpful" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({
      apiKey: TEST_API_KEY,
      lazyInit: true,
    });
    await client.getProject({ fields: ["custom_instructions"] });
    await client.getProject({ fields: ["custom_instructions"] });

    expect(countPings(mock)).toBe(1);
    const call = mock.mock.calls.find((c: [string, RequestInit]) =>
      c[0].includes("/api/v1/orgs/organizations/"),
    );
    expect(call![0]).toContain(
      `/api/v1/orgs/organizations/${TEST_ORG_ID}/projects/${TEST_PROJECT_ID}/`,
    );
  });

  test("explicit ping() still works as an escape hatch", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/api/v1/orgs/organizations/", {
      status: 200,
      body: { custom_instructions: "Be helpful" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({
      apiKey: TEST_API_KEY,
      lazyInit: true,
    });
    await client.ping();
    await client.getProject({ fields: ["custom_instructions"] });

    expect(countPings(mock)).toBe(1);
    expect(client.telemetryId).toBe("test@example.com");
  });
});

// ─── Error Handling ──────────────────────────────────────

describe("MemoryClient - Error Handling", () => {
  test("404 throws MemoryNotFoundError with server response text", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/gone/", { status: 404, body: "Memory not found" });
    setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await expect(client.get("gone")).rejects.toThrow(MemoryNotFoundError);
    await expect(client.get("gone")).rejects.toThrow("Memory not found");
  });

  test("500 throws MemoryError with server response text", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/err/", {
      status: 500,
      body: "Internal server error",
    });
    setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await expect(client.get("err")).rejects.toThrow(MemoryError);
    await expect(client.get("err")).rejects.toThrow("Internal server error");
  });

  test("400 throws ValidationError with details from server", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/bad/", {
      status: 400,
      body: "Invalid request: user_id is required",
    });
    setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await expect(client.get("bad")).rejects.toThrow(ValidationError);
    await expect(client.get("bad")).rejects.toThrow(
      "Invalid request: user_id is required",
    );
  });

  test("Authorization header is included in fetch calls", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/mem_1/", {
      status: 200,
      body: { id: "mem_1" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.get("mem_1");

    const call = mock.mock.calls.find((c: [string, RequestInit]) =>
      c[0].includes("/v1/memories/mem_1/"),
    );
    const headers = call![1].headers as Record<string, string>;
    expect(headers["Authorization"]).toContain(TEST_API_KEY);
  });

  test("network failure (fetch throws) is propagated", async () => {
    global.fetch = jest.fn(async (url: string | URL | Request) => {
      const urlStr = typeof url === "string" ? url : url.toString();
      if (urlStr.includes("/v1/memories/net_err/")) {
        throw new TypeError("Failed to fetch");
      }
      if (urlStr.includes("/v1/ping/")) {
        return {
          ok: true,
          status: 200,
          json: async () => MOCK_PING_RESPONSE,
          text: async () => JSON.stringify(MOCK_PING_RESPONSE),
        } as Response;
      }
      return {
        ok: false,
        status: 404,
        text: async () => "Not found",
      } as Response;
    });

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await expect(client.get("net_err")).rejects.toThrow();
  });
});
