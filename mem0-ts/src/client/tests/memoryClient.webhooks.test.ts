/**
 * MemoryClient unit tests — getWebhooks, createWebhook, updateWebhook, deleteWebhook.
 * Tests verify request URL, HTTP method, and payload serialization.
 * One expect per test case.
 */
import { MemoryClient } from "../mem0";
import { WebhookEvent } from "../mem0.types";
import { TEST_API_KEY, TEST_PROJECT_ID } from "./helpers";
import {
  setupMockFetch,
  findFetchCall,
  getFetchBody,
  installConsoleSuppression,
} from "./setup";

installConsoleSuppression();

// ─── Helpers ──────────────────────────────────────────────
function webhookMock(extra?: Map<string, { status: number; body: unknown }>) {
  return setupMockFetch(extra);
}

function createClient() {
  return new MemoryClient({
    apiKey: TEST_API_KEY,
  });
}

// ─── getWebhooks ──────────────────────────────────────────
describe("MemoryClient - getWebhooks", () => {
  test("sends GET to /api/v1/webhooks/projects/:id/", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/api/v1/webhooks/projects/", { status: 200, body: [] });
    const mock = webhookMock(extra);
    const client = createClient();
    await client.getWebhooks();

    const call = mock.mock.calls.find(
      (c: [string, RequestInit]) =>
        c[0].includes("/api/v1/webhooks/projects/") && !c[1]?.method,
    );
    expect(call).toBeDefined();
  });
});

// ─── createWebhook ────────────────────────────────────────
describe("MemoryClient - createWebhook", () => {
  async function callCreate() {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/api/v1/webhooks/projects/", {
      status: 200,
      body: { webhook_id: "wh_new" },
    });
    const mock = webhookMock(extra);
    const client = createClient();
    await client.createWebhook({
      name: "new-hook",
      url: "https://example.com",
      eventTypes: [WebhookEvent.MEMORY_ADDED],
    });
    return mock;
  }

  test("sends POST to /api/v1/webhooks/projects/:id/", async () => {
    const mock = await callCreate();
    expect(findFetchCall(mock, "/api/v1/webhooks/", "POST")).toBeDefined();
  });

  test("body contains name", async () => {
    const mock = await callCreate();
    const body = getFetchBody(
      findFetchCall(mock, "/api/v1/webhooks/", "POST")!,
    );
    expect(body.name).toBe("new-hook");
  });

  test("body contains url", async () => {
    const mock = await callCreate();
    const body = getFetchBody(
      findFetchCall(mock, "/api/v1/webhooks/", "POST")!,
    );
    expect(body.url).toBe("https://example.com");
  });

  test("body contains event_types in snake_case", async () => {
    const mock = await callCreate();
    const body = getFetchBody(
      findFetchCall(mock, "/api/v1/webhooks/", "POST")!,
    );
    expect(body.event_types).toStrictEqual([WebhookEvent.MEMORY_ADDED]);
  });

  test("body does not contain camelCase eventTypes", async () => {
    const mock = await callCreate();
    const body = getFetchBody(
      findFetchCall(mock, "/api/v1/webhooks/", "POST")!,
    );
    expect(body.eventTypes).toBeUndefined();
  });

  test("body does not contain webhookId", async () => {
    const mock = await callCreate();
    const body = getFetchBody(
      findFetchCall(mock, "/api/v1/webhooks/", "POST")!,
    );
    expect(body.webhookId).toBeUndefined();
  });

  test("defaults to the ping-resolved project", async () => {
    const mock = await callCreate();
    const call = findFetchCall(mock, "/api/v1/webhooks/", "POST")!;
    expect(call[0]).toContain(`/api/v1/webhooks/projects/${TEST_PROJECT_ID}/`);
  });

  test("targets an explicit projectId when provided in the payload", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/api/v1/webhooks/projects/", {
      status: 200,
      body: { webhook_id: "wh_new" },
    });
    const mock = webhookMock(extra);
    const client = createClient();
    await client.createWebhook({
      name: "new-hook",
      url: "https://example.com",
      eventTypes: [WebhookEvent.MEMORY_ADDED],
      projectId: "proj_custom_789",
    });

    const call = findFetchCall(mock, "/api/v1/webhooks/", "POST")!;
    expect(call[0]).toContain("/api/v1/webhooks/projects/proj_custom_789/");
  });

  test("throws when no project can be resolved (never posts to /projects/undefined/)", async () => {
    // A ping response with no project_id leaves the client without a project.
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/ping/", { status: 200, body: { status: "ok" } });
    extra.set("/api/v1/webhooks/projects/", { status: 200, body: {} });
    webhookMock(extra);
    const client = createClient();

    await expect(
      client.createWebhook({
        name: "n",
        url: "https://example.com",
        eventTypes: [WebhookEvent.MEMORY_ADDED],
      }),
    ).rejects.toThrow(/projectId is required/);
  });
});

// ─── updateWebhook ────────────────────────────────────────
describe("MemoryClient - updateWebhook", () => {
  async function callUpdate() {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/api/v1/webhooks/wh_1/", {
      status: 200,
      body: { message: "Webhook updated" },
    });
    const mock = webhookMock(extra);
    const client = createClient();
    await client.updateWebhook({
      webhookId: "wh_1",
      name: "updated-hook",
      url: "https://new-url.com",
      eventTypes: [WebhookEvent.MEMORY_ADDED],
    });
    return mock;
  }

  test("sends PUT to /api/v1/webhooks/:id/", async () => {
    const mock = await callUpdate();
    expect(findFetchCall(mock, "/api/v1/webhooks/wh_1/", "PUT")).toBeDefined();
  });

  test("body contains name", async () => {
    const mock = await callUpdate();
    const body = getFetchBody(
      findFetchCall(mock, "/api/v1/webhooks/wh_1/", "PUT")!,
    );
    expect(body.name).toBe("updated-hook");
  });

  test("body contains url", async () => {
    const mock = await callUpdate();
    const body = getFetchBody(
      findFetchCall(mock, "/api/v1/webhooks/wh_1/", "PUT")!,
    );
    expect(body.url).toBe("https://new-url.com");
  });

  test("body contains event_types in snake_case", async () => {
    const mock = await callUpdate();
    const body = getFetchBody(
      findFetchCall(mock, "/api/v1/webhooks/wh_1/", "PUT")!,
    );
    expect(body.event_types).toStrictEqual([WebhookEvent.MEMORY_ADDED]);
  });

  test("body does not contain camelCase eventTypes", async () => {
    const mock = await callUpdate();
    const body = getFetchBody(
      findFetchCall(mock, "/api/v1/webhooks/wh_1/", "PUT")!,
    );
    expect(body.eventTypes).toBeUndefined();
  });

  test("body does not contain webhookId", async () => {
    const mock = await callUpdate();
    const body = getFetchBody(
      findFetchCall(mock, "/api/v1/webhooks/wh_1/", "PUT")!,
    );
    expect(body.webhookId).toBeUndefined();
  });
});

// ─── deleteWebhook ────────────────────────────────────────
describe("MemoryClient - deleteWebhook", () => {
  test("sends DELETE to /api/v1/webhooks/:id/", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/api/v1/webhooks/wh_1/", {
      status: 200,
      body: { message: "Webhook deleted" },
    });
    const mock = webhookMock(extra);
    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.deleteWebhook({ webhookId: "wh_1" });

    expect(
      findFetchCall(mock, "/api/v1/webhooks/wh_1/", "DELETE"),
    ).toBeDefined();
  });

  test("accepts a bare id string", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/api/v1/webhooks/wh_2/", {
      status: 200,
      body: { message: "Webhook deleted" },
    });
    const mock = webhookMock(extra);
    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.deleteWebhook("wh_2" as any);

    expect(
      findFetchCall(mock, "/api/v1/webhooks/wh_2/", "DELETE"),
    ).toBeDefined();
  });

  test("throws on an empty webhookId instead of serializing the object into the URL", async () => {
    webhookMock();
    const client = new MemoryClient({ apiKey: TEST_API_KEY });

    await expect(client.deleteWebhook({ webhookId: "" })).rejects.toThrow(
      /webhookId is required/,
    );
  });
});
