/**
 * MemoryClient unit tests — users, deleteUser, deleteUsers.
 * Tests verify entity type routing and request construction.
 */
import { MemoryClient } from "../mem0";
import { createMockUser, createMockAllUsers, TEST_API_KEY } from "./helpers";
import {
  setupMockFetch,
  findFetchCall,
  installConsoleSuppression,
} from "./setup";

installConsoleSuppression();

// ─── users() ────────────────────────────────────────────

describe("MemoryClient - users()", () => {
  test("sends GET to /v1/entities/", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/entities/", {
      status: 200,
      body: createMockAllUsers([createMockUser()]),
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.users();

    const call = mock.mock.calls.find(
      (c: [string, RequestInit]) =>
        c[0].includes("/v1/entities/") && !c[1]?.method,
    );
    expect(call).toBeDefined();
  });
});

// ─── deleteUsers() ──────────────────────────────────────

describe("MemoryClient - deleteUsers()", () => {
  function createClientWithMockedAxios() {
    setupMockFetch();
    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const axiosDeleteMock = jest
      .fn()
      .mockResolvedValue({ data: { message: "Deleted" } });
    client.client.delete = axiosDeleteMock;
    return { client, axiosDeleteMock };
  }

  test("routes userId to DELETE /v2/entities/user/:name/", async () => {
    const { client, axiosDeleteMock } = createClientWithMockedAxios();
    await client.deleteUsers({ userId: "u1" });

    expect(axiosDeleteMock).toHaveBeenCalledWith("/v2/entities/user/u1/");
  });

  test("routes agentId to DELETE /v2/entities/agent/:name/", async () => {
    const { client, axiosDeleteMock } = createClientWithMockedAxios();
    await client.deleteUsers({ agentId: "agent_1" });

    expect(axiosDeleteMock).toHaveBeenCalledWith("/v2/entities/agent/agent_1/");
  });

  test("routes appId to DELETE /v2/entities/app/:name/", async () => {
    const { client, axiosDeleteMock } = createClientWithMockedAxios();
    await client.deleteUsers({ appId: "app_1" });

    expect(axiosDeleteMock).toHaveBeenCalledWith("/v2/entities/app/app_1/");
  });

  test("routes runId to DELETE /v2/entities/run/:name/", async () => {
    const { client, axiosDeleteMock } = createClientWithMockedAxios();
    await client.deleteUsers({ runId: "run_1" });

    expect(axiosDeleteMock).toHaveBeenCalledWith("/v2/entities/run/run_1/");
  });

  test("returns 'Entity deleted successfully.' for single entity", async () => {
    const { client } = createClientWithMockedAxios();
    const result = await client.deleteUsers({ userId: "u1" });
    expect(result.message).toBe("Entity deleted successfully.");
  });

  test("returns 'All users, agents, apps and runs deleted.' when no params given", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/entities/", {
      status: 200,
      body: createMockAllUsers([createMockUser({ name: "u1", type: "user" })]),
    });
    setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    client.client.delete = jest
      .fn()
      .mockResolvedValue({ data: { message: "Deleted" } });

    const result = await client.deleteUsers();
    expect(result.message).toBe("All users, agents, apps and runs deleted.");
  });

  test("throws when no entities exist to delete", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/entities/", {
      status: 200,
      body: createMockAllUsers([]),
    });
    setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    client.client.delete = jest.fn();

    await expect(client.deleteUsers()).rejects.toThrow("No entities to delete");
  });
});

// ─── deleteUser() (deprecated) ──────────────────────────

describe("MemoryClient - deleteUser() (deprecated)", () => {
  test("sends DELETE to /v1/entities/:type/:id/", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/entities/user/123/", {
      status: 200,
      body: { message: "Entity deleted successfully!" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.deleteUser({
      entityId: 123 as never,
      entityType: "user",
    });

    expect(
      findFetchCall(mock, "/v1/entities/user/123/", "DELETE"),
    ).toBeDefined();
  });

  test("defaults entityType to 'user' when empty", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/entities/user/456/", {
      status: 200,
      body: { message: "Entity deleted successfully!" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.deleteUser({ entityId: 456 as never, entityType: "" });

    expect(
      findFetchCall(mock, "/v1/entities/user/456/", "DELETE"),
    ).toBeDefined();
  });
});
