/**
 * Tests for the Platform backend (mem0 Platform API client).
 */

import { describe, it, expect, vi } from "vitest";
import { PlatformBackend } from "../src/backend/platform.js";
import { createDefaultConfig } from "../src/config.js";

function makeBackend(): PlatformBackend {
  // apiKey/baseUrl only build request headers; every test spies on _request,
  // so no real network calls are made.
  return new PlatformBackend(createDefaultConfig().platform);
}

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
