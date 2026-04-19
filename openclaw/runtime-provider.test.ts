import { beforeEach, describe, expect, it, vi } from "vitest";

import { createProvider, mem0ConfigSchema } from "./index.ts";


describe("runtime provider config", () => {
  it("parses runtime mode with baseUrl", () => {
    const cfg = mem0ConfigSchema.parse({
      mode: "runtime",
      runtime: {
        baseUrl: "http://localhost:8080",
      },
    });

    expect(cfg.mode).toBe("runtime");
    expect(cfg.runtime?.baseUrl).toBe("http://localhost:8080");
  });
});

describe("MemoryRuntimeProvider", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("bootstraps namespace scope once and searches through memory-runtime", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/v1/adapters/openclaw/bootstrap")) {
        return new Response(
          JSON.stringify({
            adapter: "openclaw",
            source_system: "openclaw",
            namespace_id: "ns-1",
            namespace_name: "alice:agent:researcher",
            agent_id: "agent-1",
            agent_name: "primary",
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        );
      }

      if (url.endsWith("/v1/adapters/openclaw/search")) {
        const body = JSON.parse(String(init?.body));
        expect(body.namespace_id).toBe("ns-1");
        expect(body.agent_id).toBe("agent-1");
        expect(body.query).toBe("what stack do we use");
        return new Response(
          JSON.stringify({
            adapter: "openclaw",
            source_system: "openclaw",
            results: [
              {
                id: "ep-1",
                memory: "assistant: Use Postgres and Redis.",
                resource_kind: "episode",
                space_type: "project-space",
                score: 9.5,
              },
            ],
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        );
      }

      throw new Error(`Unexpected fetch URL: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const provider = createProvider(
      mem0ConfigSchema.parse({
        mode: "runtime",
        runtime: { baseUrl: "http://runtime.test" },
      }),
      { resolvePath: (p: string) => p } as any,
    );

    const first = await provider.search("what stack do we use", { user_id: "alice:agent:researcher" });
    const second = await provider.search("what stack do we use", { user_id: "alice:agent:researcher" });

    expect(first).toHaveLength(1);
    expect(first[0]?.id).toBe("rt:ns-1:episode:ep-1");
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(second[0]?.id).toBe("rt:ns-1:episode:ep-1");
  });

  it("adds via events endpoint and resolves encoded ids for get/delete", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/v1/adapters/openclaw/bootstrap")) {
        return new Response(
          JSON.stringify({
            adapter: "openclaw",
            source_system: "openclaw",
            namespace_id: "ns-2",
            namespace_name: "alice",
            agent_id: "agent-2",
            agent_name: "primary",
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        );
      }

      if (url.endsWith("/v1/adapters/openclaw/events")) {
        return new Response(
          JSON.stringify({
            adapter: "openclaw",
            source_system: "openclaw",
            event: {
              id: "evt-1",
              episode_id: "ep-2",
              source_system: "openclaw",
            },
          }),
          { status: 201, headers: { "content-type": "application/json" } },
        );
      }

      if (url.includes("/v1/adapters/openclaw/memories/ep-2")) {
        if (init?.method === "GET") {
          return new Response(
            JSON.stringify({
              id: "ep-2",
              memory: "assistant: Durable fact",
              resource_kind: "episode",
              space_type: "project-space",
            }),
            { status: 200, headers: { "content-type": "application/json" } },
          );
        }
        if (init?.method === "DELETE") {
          return new Response(null, { status: 204 });
        }
      }

      throw new Error(`Unexpected fetch URL: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const provider = createProvider(
      mem0ConfigSchema.parse({
        mode: "runtime",
        runtime: { baseUrl: "http://runtime.test" },
      }),
      { resolvePath: (p: string) => p } as any,
    );

    const addResult = await provider.add([{ role: "user", content: "Durable fact" }], { user_id: "alice" });
    expect(addResult.results[0]?.id).toBe("rt:ns-2:episode:ep-2");

    const item = await provider.get("rt:ns-2:episode:ep-2");
    expect(item.memory).toContain("Durable fact");

    await expect(provider.delete("rt:ns-2:episode:ep-2")).resolves.toBeUndefined();
  });
});
