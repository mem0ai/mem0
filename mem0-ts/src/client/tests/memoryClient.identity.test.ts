/**
 * MemoryClient unit tests — org/project identity resolution ordering.
 *
 * Each test calls the method under test as the first awaited operation on a
 * fresh client. Any earlier await on the instance resolves identity and voids
 * the test.
 */
import { MemoryClient } from "../mem0";
import { TEST_ORG_ID, TEST_PROJECT_ID } from "./helpers";
import { setupMockFetch, installConsoleSuppression } from "./setup";

installConsoleSuppression();

// Distinct key per client keeps each test off the module-scope identity cache.
let keySeq = 0;
const freshClient = () =>
  new MemoryClient({ apiKey: `test-api-key-identity-${keySeq++}` });

// Selects by path; the ping and PostHog calls also land in the mock.
const findUrl = (mock: jest.Mock, needle: string): string => {
  const url = mock.mock.calls
    .map((c: [string, RequestInit]) => c[0])
    .find((u: string) => u.includes(needle));
  expect(url).toBeDefined();
  return url as string;
};

describe("MemoryClient - project-scoped URLs on a fresh client", () => {
  test("getProject uses the resolved org and project ids", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/api/v1/orgs/organizations/", {
      status: 200,
      body: { custom_instructions: "Be helpful" },
    });
    const mock = setupMockFetch(extra);

    await freshClient().getProject({ fields: ["custom_instructions"] });

    const url = findUrl(mock, "/api/v1/orgs/organizations/");
    expect(url).toContain(`/api/v1/orgs/organizations/${TEST_ORG_ID}/`);
    expect(url).toContain(`/projects/${TEST_PROJECT_ID}/`);
  });

  test("updateProject uses the resolved org and project ids", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/api/v1/orgs/organizations/", {
      status: 200,
      body: { custom_instructions: "Updated" },
    });
    const mock = setupMockFetch(extra);

    await freshClient().updateProject({ customInstructions: "Updated" });

    const url = findUrl(mock, "/api/v1/orgs/organizations/");
    expect(url).toContain(`/api/v1/orgs/organizations/${TEST_ORG_ID}/`);
    expect(url).toContain(`/projects/${TEST_PROJECT_ID}/`);
  });

  test("getWebhooks targets the resolved project, not null", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/api/v1/webhooks/projects/", { status: 200, body: [] });
    const mock = setupMockFetch(extra);

    await freshClient().getWebhooks();

    const url = findUrl(mock, "/api/v1/webhooks/projects/");
    expect(url).toContain(`/api/v1/webhooks/projects/${TEST_PROJECT_ID}/`);
    expect(url).not.toContain("/projects/null/");
    expect(url).not.toContain("/projects/undefined/");
  });

  test("createWebhook targets the resolved project, not null", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/api/v1/webhooks/projects/", {
      status: 200,
      body: { webhook_id: "wh_1" },
    });
    const mock = setupMockFetch(extra);

    await freshClient().createWebhook({
      name: "hook",
      url: "https://example.com/hook",
      eventTypes: ["memory_add"],
    });

    const url = findUrl(mock, "/api/v1/webhooks/projects/");
    expect(url).toContain(`/api/v1/webhooks/projects/${TEST_PROJECT_ID}/`);
    expect(url).not.toContain("/projects/null/");
    expect(url).not.toContain("/projects/undefined/");
  });

  test("an explicit projectId is honored without waiting on identity", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/api/v1/webhooks/projects/", { status: 200, body: [] });
    const mock = setupMockFetch(extra);

    await freshClient().getWebhooks({ projectId: "proj_explicit_789" });

    expect(findUrl(mock, "/api/v1/webhooks/projects/")).toContain(
      "/api/v1/webhooks/projects/proj_explicit_789/",
    );
  });
});

describe("MemoryClient - memory endpoints do not wait on identity", () => {
  test("search completes while the ping is still pending", async () => {
    // The ping never settles.
    const mock = jest.fn((url: string) => {
      if (url.includes("/v1/ping/")) return new Promise(() => {});
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ results: [] }),
        text: () => Promise.resolve(""),
      });
    });
    global.fetch = mock as unknown as typeof global.fetch;

    await expect(
      freshClient().search("query", { filters: { user_id: "alice" } }),
    ).resolves.toBeDefined();

    expect(findUrl(mock, "/v3/memories/search/")).toBeDefined();
  });
});
