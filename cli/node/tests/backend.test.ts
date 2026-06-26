import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { PlatformBackend } from "../src/backend/platform.js";
import type { PlatformConfig } from "../src/config.js";

describe("PlatformBackend URL Encoding", () => {
  let backend: PlatformBackend;
  const mockFetch = vi.fn().mockResolvedValue({
    status: 200,
    ok: true,
    json: async () => ({}),
    headers: {
      get: () => null,
    },
  });

  beforeEach(() => {
    vi.stubGlobal("fetch", mockFetch);
    const config: PlatformConfig = {
      apiKey: "test-api-key",
      baseUrl: "https://api.mem0.ai",
    };
    backend = new PlatformBackend(config);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("get() encodes memoryId", async () => {
    const memoryId = "mem/123?active#frag";
    const encodedId = encodeURIComponent(memoryId);

    await backend.get(memoryId);

    expect(mockFetch).toHaveBeenCalledWith(
      `https://api.mem0.ai/v1/memories/${encodedId}/?source=CLI`,
      expect.any(Object),
    );
  });

  it("update() encodes memoryId", async () => {
    const memoryId = "mem/123?active#frag";
    const encodedId = encodeURIComponent(memoryId);

    await backend.update(memoryId, "updated content");

    expect(mockFetch).toHaveBeenCalledWith(
      `https://api.mem0.ai/v1/memories/${encodedId}/`,
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({ text: "updated content", source: "CLI" }),
      }),
    );
  });

  it("delete() encodes memoryId", async () => {
    const memoryId = "mem/123?active#frag";
    const encodedId = encodeURIComponent(memoryId);

    await backend.delete(memoryId);

    expect(mockFetch).toHaveBeenCalledWith(
      `https://api.mem0.ai/v1/memories/${encodedId}/?source=CLI`,
      expect.objectContaining({
        method: "DELETE",
      }),
    );
  });

  it("deleteEntities() encodes entityType and entityId", async () => {
    const userId = "user/123?active#frag";
    const agentId = "agent/456?active#frag";
    const encodedUserId = encodeURIComponent(userId);
    const encodedAgentId = encodeURIComponent(agentId);

    await backend.deleteEntities({
      userId,
      agentId,
    });

    expect(mockFetch).toHaveBeenCalledWith(
      `https://api.mem0.ai/v2/entities/user/${encodedUserId}/?source=CLI`,
      expect.objectContaining({
        method: "DELETE",
      }),
    );

    expect(mockFetch).toHaveBeenCalledWith(
      `https://api.mem0.ai/v2/entities/agent/${encodedAgentId}/?source=CLI`,
      expect.objectContaining({
        method: "DELETE",
      }),
    );
  });

  it("getEvent() encodes eventId", async () => {
    const eventId = "evt/123?active#frag";
    const encodedId = encodeURIComponent(eventId);

    await backend.getEvent(eventId);

    expect(mockFetch).toHaveBeenCalledWith(
      `https://api.mem0.ai/v1/event/${encodedId}/`,
      expect.objectContaining({
        method: "GET",
      }),
    );
  });
});
