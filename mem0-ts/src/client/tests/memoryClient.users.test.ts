/**
 * MemoryClient unit tests — users, deleteUser.
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
