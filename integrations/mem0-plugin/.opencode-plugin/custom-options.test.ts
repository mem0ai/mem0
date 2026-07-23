/**
 * Tests for the custom-options feature.
 *
 * Strategy: initialize Mem0Plugin once per describe block, then call
 * plugin tools (add_memory / search_memories) to trigger real fetch calls.
 * This verifies the full end-to-end path without depending on module-internal
 * state or async fire-and-forget ping timing.
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import Mem0Plugin from "./opencode-mem0";

// ─── Env snapshot / restore ───────────────────────────────

const FIXED_KEYS = ["MEM0_API_KEY", "MEM0_HOST", "MEM0_API_URL", "MEM0_TELEMETRY"] as const;
const savedEnv: Record<string, string | undefined> = {};
const savedFetch = globalThis.fetch;

beforeEach(() => {
  for (const key of Object.keys(process.env)) {
    if (key.startsWith("MEM0_HEADER_") || FIXED_KEYS.includes(key as any)) {
      savedEnv[key] = process.env[key];
    }
  }
});

afterEach(() => {
  for (const key of Object.keys(process.env)) {
    if (!key.startsWith("MEM0_HEADER_")) continue;
    if (savedEnv[key] === undefined) delete process.env[key];
    else process.env[key] = savedEnv[key];
  }
  for (const key of FIXED_KEYS) {
    if (savedEnv[key] === undefined) delete process.env[key];
    else process.env[key] = savedEnv[key];
  }
  globalThis.fetch = savedFetch;
});

// ─── Helpers ──────────────────────────────────────────────

interface Req { url: string; headers: Record<string, string> }

/**
 * Stub globalThis.fetch, capturing url + headers of every call.
 * Returns a standard success body for ping, add, search.
 */
function captureFetch(): Req[] {
  const reqs: Req[] = [];
  globalThis.fetch = (async (input: any, init?: RequestInit) => {
    const url = typeof input === "string" ? input
      : input instanceof URL ? input.toString()
      : input.url;
    const headers = Object.fromEntries(
      Object.entries((init?.headers as Record<string, string>) ?? {}),
    );
    reqs.push({ url, headers });

    // Return appropriate body depending on the endpoint
    let body: unknown = { status: "ok", userEmail: "test@mem0.dev" };
    if (url.includes("/memories/add/")) body = { results: [] };
    if (url.includes("/memories/search/")) body = { results: [] };

    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }) as typeof fetch;
  return reqs;
}

function pluginCtx() {
  return {
    client: { app: { log: async () => {} } },
    $: () => ({ quiet: async () => ({ stdout: "" }) }),
  } as any;
}

/** Initialize plugin and call add_memory to trigger a real fetch. */
async function initAndAdd(extraEnv: Record<string, string> = {}): Promise<Req[]> {
  for (const [k, v] of Object.entries(extraEnv)) process.env[k] = v;
  process.env.MEM0_API_KEY = "test-key";
  process.env.MEM0_TELEMETRY = "false";

  const reqs = captureFetch();
  const plugin = await Mem0Plugin(pluginCtx());
  await plugin.tool.add_memory.execute({ text: "hello" });
  return reqs;
}

// ─── Custom Host ──────────────────────────────────────────

describe("Custom Host Support", () => {
  test("default host api.mem0.ai is used when no env var is set", async () => {
    delete process.env.MEM0_HOST;
    delete process.env.MEM0_API_URL;
    const reqs = await initAndAdd();
    expect(reqs.some((r) => r.url.includes("api.mem0.ai"))).toBe(true);
  });

  test("MEM0_HOST overrides default host", async () => {
    const reqs = await initAndAdd({ MEM0_HOST: "http://my-host.example.com" });
    expect(reqs.some((r) => r.url.startsWith("http://my-host.example.com"))).toBe(true);
  });

  test("MEM0_API_URL is used when MEM0_HOST is absent", async () => {
    delete process.env.MEM0_HOST;
    const reqs = await initAndAdd({ MEM0_API_URL: "http://my-apiurl.example.com" });
    expect(reqs.some((r) => r.url.startsWith("http://my-apiurl.example.com"))).toBe(true);
  });

  test("MEM0_HOST takes precedence over MEM0_API_URL", async () => {
    const reqs = await initAndAdd({
      MEM0_HOST: "http://host-wins.example.com",
      MEM0_API_URL: "http://url-loses.example.com",
    });
    expect(reqs.some((r) => r.url.startsWith("http://host-wins.example.com"))).toBe(true);
    expect(reqs.every((r) => !r.url.startsWith("http://url-loses.example.com"))).toBe(true);
  });

  test("trailing slashes are stripped from the custom host", async () => {
    const reqs = await initAndAdd({ MEM0_HOST: "http://slash.example.com///" });
    expect(reqs.every((r) => !r.url.includes("///"))).toBe(true);
    expect(reqs.some((r) => r.url.startsWith("http://slash.example.com/"))).toBe(true);
  });
});

// ─── Custom Headers via MEM0_HEADER_* ─────────────────────

describe("Custom Headers — MEM0_HEADER_* env vars", () => {
  test("single MEM0_HEADER_* is sent in the add_memory request", async () => {
    const reqs = await initAndAdd({ MEM0_HEADER_X_MY_TOKEN: "secret-token" });
    const addReq = reqs.find((r) => r.url.includes("/memories/add/"));
    expect(addReq).toBeDefined();
    expect(addReq!.headers["X-My-Token"]).toBe("secret-token");
  });

  test("multiple MEM0_HEADER_* vars are all forwarded", async () => {
    const reqs = await initAndAdd({
      MEM0_HEADER_X_ORG_ID: "org-123",
      MEM0_HEADER_X_TENANT: "acme",
    });
    const addReq = reqs.find((r) => r.url.includes("/memories/add/"));
    expect(addReq!.headers["X-Org-Id"]).toBe("org-123");
    expect(addReq!.headers["X-Tenant"]).toBe("acme");
  });

  test("header name: underscores → hyphens, title-cased (X_FOO_BAR → X-Foo-Bar)", async () => {
    const reqs = await initAndAdd({ MEM0_HEADER_X_FOO_BAR: "baz" });
    const addReq = reqs.find((r) => r.url.includes("/memories/add/"));
    expect(addReq!.headers["X-Foo-Bar"]).toBe("baz");
  });

  test("Authorization header is never overridden by MEM0_HEADER_AUTHORIZATION", async () => {
    const reqs = await initAndAdd({ MEM0_HEADER_AUTHORIZATION: "Token attacker" });
    const addReq = reqs.find((r) => r.url.includes("/memories/add/"));
    // _fetchWithErrorHandling writes Authorization last → SDK value always wins
    expect(addReq!.headers["Authorization"]).toBe("Token test-key");
  });

  test("no MEM0_HEADER_* vars → no extra headers in request", async () => {
    for (const key of Object.keys(process.env)) {
      if (key.startsWith("MEM0_HEADER_")) delete process.env[key];
    }
    const reqs = await initAndAdd();
    const addReq = reqs.find((r) => r.url.includes("/memories/add/"));
    const extra = Object.keys(addReq!.headers).filter(
      (k) => !["Authorization", "Content-Type", "Mem0-User-ID"].includes(k),
    );
    expect(extra).toHaveLength(0);
  });
});

// ─── Combined host + headers ──────────────────────────────

describe("Combined Custom Host and Headers", () => {
  test("custom host and custom header are both applied in the same request", async () => {
    const reqs = await initAndAdd({
      MEM0_HOST: "http://combined.example.com",
      MEM0_HEADER_X_COMBINED: "yes",
    });
    const addReq = reqs.find((r) => r.url.includes("/memories/add/"));
    expect(addReq!.url.startsWith("http://combined.example.com")).toBe(true);
    expect(addReq!.headers["X-Combined"]).toBe("yes");
  });
});
