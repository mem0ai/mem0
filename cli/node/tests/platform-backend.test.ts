/**
 * Tests for the Platform backend (mem0 Platform API client).
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { PlatformBackend } from "../src/backend/platform.js";
import { createDefaultConfig } from "../src/config.js";

function makeBackend(): PlatformBackend {
  // apiKey/baseUrl only build request headers; every test spies on _request,
  // so no real network calls are made.
  return new PlatformBackend(createDefaultConfig().platform);
}

function mockFetch() {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    headers: { get: vi.fn().mockReturnValue(null) },
    json: vi.fn().mockResolvedValue({ message: "ok" }),
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

beforeEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("deleteEntities", () => {
  it("returns all results keyed by entity type for a multi-entity delete", async () => {
    const backend = makeBackend();
    const responses: Record<string, unknown> = {
      "/v2/entities/user/alice/": { message: "user deleted" },
      "/v2/entities/agent/bob/": { message: "agent deleted" },
    };
    const spy = vi
      // biome-ignore lint/suspicious/noExplicitAny: spying on a private method
      .spyOn(backend as any, "_request")
      .mockImplementation(async (_method: string, path: string) => responses[path]);

    const result = await backend.deleteEntities({ userId: "alice", agentId: "bob" });

    // Regression: previously only the last entity's response survived.
    expect(result).toEqual({
      user: { message: "user deleted" },
      agent: { message: "agent deleted" },
    });
    expect(spy).toHaveBeenCalledTimes(2);
  });

  it("keys a single-entity delete by its type", async () => {
    const backend = makeBackend();
    // biome-ignore lint/suspicious/noExplicitAny: spying on a private method
    vi.spyOn(backend as any, "_request").mockResolvedValue({ message: "user deleted" });

    const result = await backend.deleteEntities({ userId: "alice" });
    expect(result).toEqual({ user: { message: "user deleted" } });
  });

  it("throws when no entity id is provided", async () => {
    const backend = makeBackend();
    await expect(backend.deleteEntities({})).rejects.toThrow(
      "At least one entity ID is required",
    );
  });
});

describe("PlatformBackend path encoding", () => {
  it("encodes memory IDs before interpolating them into paths", async () => {
    const fetchMock = mockFetch();
    const backend = makeBackend();

    await backend.get("mem/a?b#c");
    await backend.update("mem/a?b#c", "updated");
    await backend.delete("mem/a?b#c");

    const urls = fetchMock.mock.calls.map((call) => call[0]);
    expect(urls).toEqual([
      "https://api.mem0.ai/v1/memories/mem%2Fa%3Fb%23c/?source=CLI",
      "https://api.mem0.ai/v1/memories/mem%2Fa%3Fb%23c/",
      "https://api.mem0.ai/v1/memories/mem%2Fa%3Fb%23c/?source=CLI",
    ]);
  });

  it("encodes entity and event IDs before interpolating them into paths", async () => {
    const fetchMock = mockFetch();
    const backend = makeBackend();

    await backend.deleteEntities({ userId: "org/team?active#frag" });
    await backend.getEvent("evt/a?b#c");

    const urls = fetchMock.mock.calls.map((call) => call[0]);
    expect(urls).toEqual([
      "https://api.mem0.ai/v2/entities/user/org%2Fteam%3Factive%23frag/?source=CLI",
      "https://api.mem0.ai/v1/event/evt%2Fa%3Fb%23c/",
    ]);
  });
});
