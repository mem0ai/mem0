/**
 * MemoryClient unit tests — getProject, updateProject, exports, feedback.
 * Tests verify request construction and validation behavior.
 */
import { MemoryClient } from "../mem0";
import { Feedback } from "../mem0.types";
import { createMockFetch, TEST_API_KEY } from "./helpers";
import {
  setupMockFetch,
  findFetchCall,
  getFetchBody,
  installConsoleSuppression,
} from "./setup";

installConsoleSuppression();

// ─── getProject() ───────────────────────────────────────

describe("MemoryClient - getProject()", () => {
  test("throws when organizationId and projectId not set (ping returns no org)", async () => {
    const responses = new Map<string, { status: number; body: unknown }>();
    responses.set("/v1/ping/", { status: 200, body: { status: "ok" } });
    global.fetch = createMockFetch(responses);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    try {
      await client.ping();
    } catch {
      // ping might throw — but orgId stays null
    }

    await expect(
      client.getProject({ fields: ["custom_instructions"] }),
    ).rejects.toThrow("organizationId and projectId must be set");
  });

  test("sends GET to /api/v1/orgs/organizations/:orgId/projects/:projId/", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/api/v1/orgs/organizations/", {
      status: 200,
      body: { custom_instructions: "Be helpful" },
    });
    const mock = setupMockFetch(extra);

    // org/project come from ping mock response
    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.ping();
    await client.getProject({ fields: ["custom_instructions"] });

    const call = mock.mock.calls.find(
      (c: [string, RequestInit]) =>
        c[0].includes("/api/v1/orgs/organizations/") && !c[1]?.method,
    );
    expect(call).toBeDefined();
    expect(call![0]).toContain("fields=custom_instructions");
  });
});

// ─── updateProject() ────────────────────────────────────

describe("MemoryClient - updateProject()", () => {
  test("sends PATCH to /api/v1/orgs/organizations/:orgId/projects/:projId/", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/api/v1/orgs/organizations/", {
      status: 200,
      body: { custom_instructions: "Updated" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.ping();
    await client.updateProject({
      custom_instructions: "Updated instructions",
    });

    const call = findFetchCall(mock, "/api/v1/orgs/organizations/", "PATCH");
    expect(call).toBeDefined();
  });

  test("includes custom_instructions in PATCH body", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/api/v1/orgs/organizations/", {
      status: 200,
      body: { custom_instructions: "Updated" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.ping();
    await client.updateProject({
      custom_instructions: "Updated instructions",
    });

    const call = findFetchCall(mock, "/api/v1/orgs/organizations/", "PATCH");
    expect(getFetchBody(call!).custom_instructions).toBe(
      "Updated instructions",
    );
  });
});

// ─── feedback() ─────────────────────────────────────────

describe("MemoryClient - feedback()", () => {
  test("sends POST to /v1/feedback/ with payload", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/feedback/", {
      status: 200,
      body: { message: "Feedback recorded" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.feedback({
      memoryId: "mem_123",
      feedback: Feedback.POSITIVE,
      feedbackReason: "Very helpful",
    });

    const call = findFetchCall(mock, "/v1/feedback/", "POST");
    expect(call).toBeDefined();
  });

  test("includes memory_id, feedback, and reason in body", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/feedback/", {
      status: 200,
      body: { message: "Feedback recorded" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.feedback({
      memoryId: "mem_123",
      feedback: Feedback.POSITIVE,
      feedbackReason: "Very helpful",
    });

    const call = findFetchCall(mock, "/v1/feedback/", "POST");
    const body = getFetchBody(call!);
    expect(body.memory_id).toBe("mem_123");
    expect(body.feedback).toBe("POSITIVE");
    expect(body.feedback_reason).toBe("Very helpful");
  });
});

// ─── Memory Exports ─────────────────────────────────────

describe("MemoryClient - Memory Exports", () => {
  test("createMemoryExport throws when missing filters or schema", async () => {
    setupMockFetch();
    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await expect(
      client.createMemoryExport({
        filters: null as never,
        schema: null as never,
      }),
    ).rejects.toThrow("Missing filters or schema");
  });

  test("createMemoryExport sends POST to /v1/exports/", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/exports/", {
      status: 200,
      body: { message: "Export created", id: "exp_123" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.createMemoryExport({
      schema: { fields: ["memory", "user_id"] },
      filters: { user_id: "u1" },
    });

    expect(findFetchCall(mock, "/v1/exports/", "POST")).toBeDefined();
  });

  test("getMemoryExport throws when missing both id and filters", async () => {
    setupMockFetch();
    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await expect(client.getMemoryExport({} as never)).rejects.toThrow(
      "Missing memoryExportId or filters",
    );
  });

  test("getMemoryExport sends POST to /v1/exports/get/", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/exports/get/", {
      status: 200,
      body: { message: "Export data", id: "exp_123" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.getMemoryExport({ memoryExportId: "exp_123" });

    expect(findFetchCall(mock, "/v1/exports/get/", "POST")).toBeDefined();
  });
});
