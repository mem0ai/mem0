/**
 * MemoryClient unit tests — getWebhooks, createWebhook, updateWebhook, deleteWebhook.
 * Tests verify request URL and HTTP method, not mock response values.
 */
import { MemoryClient } from "../mem0";
import { WebhookEvent } from "../mem0.types";
import { TEST_API_KEY, TEST_ORG_ID, TEST_PROJECT_ID } from "./helpers";
import {
  setupMockFetch,
  findFetchCall,
  getFetchBody,
  installConsoleSuppression,
} from "./setup";

installConsoleSuppression();

describe("MemoryClient - Webhooks", () => {
  test("getWebhooks sends GET to /api/v1/webhooks/projects/:id/", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/api/v1/webhooks/projects/", { status: 200, body: [] });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({
      apiKey: TEST_API_KEY,
      organizationId: TEST_ORG_ID,
      projectId: TEST_PROJECT_ID,
    });
    await client.getWebhooks();

    const call = mock.mock.calls.find(
      (c: [string, RequestInit]) =>
        c[0].includes("/api/v1/webhooks/projects/") && !c[1]?.method,
    );
    expect(call).toBeDefined();
  });

  test("createWebhook sends POST to /api/v1/webhooks/projects/:id/", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/api/v1/webhooks/projects/", {
      status: 200,
      body: { webhook_id: "wh_new" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({
      apiKey: TEST_API_KEY,
      organizationId: TEST_ORG_ID,
      projectId: TEST_PROJECT_ID,
    });
    await client.createWebhook({
      name: "new-hook",
      url: "https://example.com",
      eventTypes: [WebhookEvent.MEMORY_ADDED],
    });

    expect(findFetchCall(mock, "/api/v1/webhooks/", "POST")).toBeDefined();
  });

  test("createWebhook includes webhook payload in body with snake_case keys", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/api/v1/webhooks/projects/", {
      status: 200,
      body: { webhook_id: "wh_new" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({
      apiKey: TEST_API_KEY,
      organizationId: TEST_ORG_ID,
      projectId: TEST_PROJECT_ID,
    });
    await client.createWebhook({
      name: "new-hook",
      url: "https://example.com",
      eventTypes: [WebhookEvent.MEMORY_ADDED],
    });

    const call = findFetchCall(mock, "/api/v1/webhooks/", "POST");
    const body = getFetchBody(call!);
    expect(body.name).toBe("new-hook");
    expect(body.url).toBe("https://example.com");
    expect(body.event_types).toEqual([WebhookEvent.MEMORY_ADDED]);
    expect(body.eventTypes).toBeUndefined();
    expect(body.projectId).toBeUndefined();
    expect(body.webhookId).toBeUndefined();
  });

  test("updateWebhook sends PUT to /api/v1/webhooks/:id/", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/api/v1/webhooks/wh_1/", {
      status: 200,
      body: { message: "Webhook updated" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({
      apiKey: TEST_API_KEY,
      organizationId: TEST_ORG_ID,
      projectId: TEST_PROJECT_ID,
    });
    await client.updateWebhook({
      webhookId: "wh_1",
      name: "updated-hook",
      url: "https://new-url.com",
      eventTypes: [WebhookEvent.MEMORY_ADDED],
    });

    expect(findFetchCall(mock, "/api/v1/webhooks/wh_1/", "PUT")).toBeDefined();
  });

  test("updateWebhook includes updated fields in body with snake_case keys", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/api/v1/webhooks/wh_1/", {
      status: 200,
      body: { message: "Webhook updated" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({
      apiKey: TEST_API_KEY,
      organizationId: TEST_ORG_ID,
      projectId: TEST_PROJECT_ID,
    });
    await client.updateWebhook({
      webhookId: "wh_1",
      name: "updated-hook",
      url: "https://new-url.com",
      eventTypes: [WebhookEvent.MEMORY_ADDED],
    });

    const call = findFetchCall(mock, "/api/v1/webhooks/wh_1/", "PUT");
    const body = getFetchBody(call!);
    expect(body.name).toBe("updated-hook");
    expect(body.url).toBe("https://new-url.com");
    expect(body.event_types).toEqual([WebhookEvent.MEMORY_ADDED]);
    expect(body.project_id).toBeUndefined();
    expect(body.eventTypes).toBeUndefined();
    expect(body.projectId).toBeUndefined();
    expect(body.webhookId).toBeUndefined();
  });

  test("deleteWebhook sends DELETE to /api/v1/webhooks/:id/", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/api/v1/webhooks/wh_1/", {
      status: 200,
      body: { message: "Webhook deleted" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.deleteWebhook({ webhookId: "wh_1" });

    expect(
      findFetchCall(mock, "/api/v1/webhooks/wh_1/", "DELETE"),
    ).toBeDefined();
  });
});
