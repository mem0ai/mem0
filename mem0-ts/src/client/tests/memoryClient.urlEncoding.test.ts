/**
 * MemoryClient unit tests — URL encoding of dynamic path segments.
 */
import { MemoryClient } from "../mem0";
import { TEST_API_KEY } from "./helpers";
import {
  setupMockFetch,
  findFetchCall,
  installConsoleSuppression,
} from "./setup";

installConsoleSuppression();

describe("MemoryClient - URL Encoding of dynamic path segments", () => {
  let client: MemoryClient;

  beforeEach(() => {
    // Setup standard mock fetch to handle client initialization / pings
    setupMockFetch();
    client = new MemoryClient({ apiKey: TEST_API_KEY });
  });

  test("get() encodes memoryId", async () => {
    const memoryId = "mem/123?active#frag";
    const encodedId = encodeURIComponent(memoryId);
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set(`/v1/memories/${encodedId}/`, {
      status: 200,
      body: { id: memoryId, memory: "test" },
    });
    const mock = setupMockFetch(extra);

    await client.get(memoryId);

    expect(findFetchCall(mock, `/v1/memories/${encodedId}/`)).toBeDefined();
  });

  test("update() encodes memoryId", async () => {
    const memoryId = "mem/123?active#frag";
    const encodedId = encodeURIComponent(memoryId);
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set(`/v1/memories/${encodedId}/`, {
      status: 200,
      body: [{ id: memoryId, memory: "updated test" }],
    });
    const mock = setupMockFetch(extra);

    await client.update(memoryId, { text: "updated test" });

    expect(
      findFetchCall(mock, `/v1/memories/${encodedId}/`, "PUT"),
    ).toBeDefined();
  });

  test("delete() encodes memoryId", async () => {
    const memoryId = "mem/123?active#frag";
    const encodedId = encodeURIComponent(memoryId);
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set(`/v1/memories/${encodedId}/`, {
      status: 200,
      body: { message: "deleted" },
    });
    const mock = setupMockFetch(extra);

    await client.delete(memoryId);

    expect(
      findFetchCall(mock, `/v1/memories/${encodedId}/`, "DELETE"),
    ).toBeDefined();
  });

  test("history() encodes memoryId", async () => {
    const memoryId = "mem/123?active#frag";
    const encodedId = encodeURIComponent(memoryId);
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set(`/v1/memories/${encodedId}/history/`, {
      status: 200,
      body: [],
    });
    const mock = setupMockFetch(extra);

    await client.history(memoryId);

    expect(
      findFetchCall(mock, `/v1/memories/${encodedId}/history/`),
    ).toBeDefined();
  });

  test("deleteUser() encodes entity_id and entity_type", async () => {
    const entityType = "user/type";
    const entityId = "id/456?active#frag";
    const encodedType = encodeURIComponent(entityType);
    const encodedId = encodeURIComponent(entityId);
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set(`/v1/entities/${encodedType}/${encodedId}/`, {
      status: 200,
      body: { message: "deleted" },
    });
    const mock = setupMockFetch(extra);

    await client.deleteUser({
      entity_id: entityId as any,
      entity_type: entityType,
    });

    expect(
      findFetchCall(
        mock,
        `/v1/entities/${encodedType}/${encodedId}/`,
        "DELETE",
      ),
    ).toBeDefined();
  });

  test("deleteUsers() encodes entity name in axios delete call", async () => {
    const userId = "user/123?active#frag";
    const encodedUser = encodeURIComponent(userId);

    // Mock the axios delete method
    client.client.delete = jest.fn().mockResolvedValue({
      data: { message: "Entity deleted successfully." },
    });

    await client.deleteUsers({ userId });

    expect(client.client.delete).toHaveBeenCalledWith(
      `/v2/entities/user/${encodedUser}/`,
    );
  });

  test("updateWebhook() encodes webhookId", async () => {
    const webhookId = "hook/123?active#frag";
    const encodedId = encodeURIComponent(webhookId);
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set(`/api/v1/webhooks/${encodedId}/`, {
      status: 200,
      body: { message: "updated" },
    });
    const mock = setupMockFetch(extra);

    await client.updateWebhook({
      webhookId,
      name: "new hook name",
    });

    expect(
      findFetchCall(mock, `/api/v1/webhooks/${encodedId}/`, "PUT"),
    ).toBeDefined();
  });

  test("deleteWebhook() encodes webhookId", async () => {
    const webhookId = "hook/123?active#frag";
    const encodedId = encodeURIComponent(webhookId);
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set(`/api/v1/webhooks/${encodedId}/`, {
      status: 200,
      body: { message: "deleted" },
    });
    const mock = setupMockFetch(extra);

    await client.deleteWebhook({ webhookId });

    expect(
      findFetchCall(mock, `/api/v1/webhooks/${encodedId}/`, "DELETE"),
    ).toBeDefined();
  });
});
