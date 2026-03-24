/**
 * MemoryClient unit tests — users, deleteUser, deleteUsers.
 * Tests verify entity type routing and request construction.
 */
import { MemoryClient } from "../mem0";
import {
  createMockUser,
  createMockAllUsers,
  TEST_API_KEY,
  TEST_ORG_ID,
  TEST_PROJECT_ID,
} from "./helpers";
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
    const client = new MemoryClient({
      apiKey: TEST_API_KEY,
      organizationId: TEST_ORG_ID,
      projectId: TEST_PROJECT_ID,
    });
    const axiosDeleteMock = jest
      .fn()
      .mockResolvedValue({ data: { message: "Deleted" } });
    client.client.delete = axiosDeleteMock;
    return { client, axiosDeleteMock };
  }

  test("routes user_id to DELETE /v2/entities/user/:name/", async () => {
    const { client, axiosDeleteMock } = createClientWithMockedAxios();
    await client.deleteUsers({ user_id: "u1" });

    expect(axiosDeleteMock).toHaveBeenCalledWith("/v2/entities/user/u1/", {
      params: expect.objectContaining({
        org_id: TEST_ORG_ID,
        project_id: TEST_PROJECT_ID,
      }),
    });
  });

  test("routes agent_id to DELETE /v2/entities/agent/:name/", async () => {
    const { client, axiosDeleteMock } = createClientWithMockedAxios();
    await client.deleteUsers({ agent_id: "agent_1" });

    expect(axiosDeleteMock).toHaveBeenCalledWith(
      "/v2/entities/agent/agent_1/",
      expect.any(Object),
    );
  });

  test("routes app_id to DELETE /v2/entities/app/:name/", async () => {
    const { client, axiosDeleteMock } = createClientWithMockedAxios();
    await client.deleteUsers({ app_id: "app_1" });

    expect(axiosDeleteMock).toHaveBeenCalledWith(
      "/v2/entities/app/app_1/",
      expect.any(Object),
    );
  });

  test("routes run_id to DELETE /v2/entities/run/:name/", async () => {
    const { client, axiosDeleteMock } = createClientWithMockedAxios();
    await client.deleteUsers({ run_id: "run_1" });

    expect(axiosDeleteMock).toHaveBeenCalledWith(
      "/v2/entities/run/run_1/",
      expect.any(Object),
    );
  });

  test("returns 'Entity deleted successfully.' for single entity", async () => {
    const { client } = createClientWithMockedAxios();
    const result = await client.deleteUsers({ user_id: "u1" });
    expect(result.message).toBe("Entity deleted successfully.");
  });

  test("returns 'All users, agents, apps and runs deleted.' when no params given", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/entities/", {
      status: 200,
      body: createMockAllUsers([createMockUser({ name: "u1", type: "user" })]),
    });
    setupMockFetch(extra);

    const client = new MemoryClient({
      apiKey: TEST_API_KEY,
      organizationId: TEST_ORG_ID,
      projectId: TEST_PROJECT_ID,
    });
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

    const client = new MemoryClient({
      apiKey: TEST_API_KEY,
      organizationId: TEST_ORG_ID,
      projectId: TEST_PROJECT_ID,
    });
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
      entity_id: 123 as never,
      entity_type: "user",
    });

    expect(
      findFetchCall(mock, "/v1/entities/user/123/", "DELETE"),
    ).toBeDefined();
  });

  test("defaults entity_type to 'user' when empty", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/entities/user/456/", {
      status: 200,
      body: { message: "Entity deleted successfully!" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.deleteUser({ entity_id: 456 as never, entity_type: "" });

    expect(
      findFetchCall(mock, "/v1/entities/user/456/", "DELETE"),
    ).toBeDefined();
  });
});
