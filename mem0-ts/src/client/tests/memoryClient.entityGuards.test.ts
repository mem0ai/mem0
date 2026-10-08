/** MemoryClient unit tests for entity ID handling in add, deleteAll, and deleteUsers. */
import { MemoryClient } from "../mem0";
import { createMockAllUsers, createMockUser, TEST_API_KEY } from "./helpers";
import {
  setupMockFetch,
  findFetchCall,
  getFetchBody,
  installConsoleSuppression,
} from "./setup";

installConsoleSuppression();

const BLANK_IDS = ["", "   ", "\t\n"];
const ENTITY_KEYS = [
  "userId",
  "agentId",
  "appId",
  "runId",
  "user_id",
  "agent_id",
  "app_id",
  "run_id",
];

function mockDeleteAll() {
  const extra = new Map<string, { status: number; body: unknown }>();
  extra.set("/v1/memories/", { status: 200, body: { message: "Deleted" } });
  return setupMockFetch(extra);
}

describe("MemoryClient - deleteAll() blank entity IDs", () => {
  test.each(
    ENTITY_KEYS.flatMap((key) => BLANK_IDS.map((blank) => [key, blank])),
  )("rejects %s=%j without sending a request", async (key, blank) => {
    const mock = mockDeleteAll();
    const client = new MemoryClient({ apiKey: TEST_API_KEY });

    await expect(client.deleteAll({ [key]: blank } as never)).rejects.toThrow(
      key,
    );

    expect(findFetchCall(mock, "/v1/memories/", "DELETE")).toBeUndefined();
  });

  test("rejects a blank ID next to a valid ID", async () => {
    const mock = mockDeleteAll();
    const client = new MemoryClient({ apiKey: TEST_API_KEY });

    await expect(
      client.deleteAll({ userId: "u1", agentId: "" }),
    ).rejects.toThrow("agentId");

    expect(findFetchCall(mock, "/v1/memories/", "DELETE")).toBeUndefined();
  });

  test("error explains the risk and the wildcard", async () => {
    mockDeleteAll();
    const client = new MemoryClient({ apiKey: TEST_API_KEY });

    await expect(client.deleteAll({ userId: "" })).rejects.toThrow(
      /every memory in the project.*"\*"/,
    );
  });
});

describe("MemoryClient - deleteAll() valid inputs", () => {
  test("sends the entity ID as a query param", async () => {
    const mock = mockDeleteAll();
    const client = new MemoryClient({ apiKey: TEST_API_KEY });

    await client.deleteAll({ userId: "u1" });

    const call = findFetchCall(mock, "/v1/memories/?", "DELETE");
    expect(call![0]).toContain("user_id=u1");
  });

  test("still allows the explicit wildcard", async () => {
    const mock = mockDeleteAll();
    const client = new MemoryClient({ apiKey: TEST_API_KEY });

    await client.deleteAll({ userId: "*" });

    const call = findFetchCall(mock, "/v1/memories/?", "DELETE");
    expect(call![0]).toContain("user_id=*");
  });

  test("ignores undefined entity IDs", async () => {
    const mock = mockDeleteAll();
    const client = new MemoryClient({ apiKey: TEST_API_KEY });

    await client.deleteAll({ userId: "u1", agentId: undefined });

    const call = findFetchCall(mock, "/v1/memories/?", "DELETE");
    expect(call![0]).not.toContain("agent_id");
  });
});

describe("MemoryClient - deleteAll() rejects filters", () => {
  test("throws and sends no request", async () => {
    const mock = mockDeleteAll();
    const client = new MemoryClient({ apiKey: TEST_API_KEY });

    await expect(
      client.deleteAll({ filters: { user_id: "u1" } } as never),
    ).rejects.toThrow(/filters.*userId/);

    expect(findFetchCall(mock, "/v1/memories/", "DELETE")).toBeUndefined();
  });
});

describe("MemoryClient - deleteUsers() blank entity IDs", () => {
  test.each(
    ["userId", "agentId", "appId", "runId"].flatMap((key) =>
      BLANK_IDS.map((blank) => [key, blank]),
    ),
  )("rejects %s=%j before any request", async (key, blank) => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/entities/", {
      status: 200,
      body: createMockAllUsers([createMockUser()]),
    });
    const mock = setupMockFetch(extra);
    const client = new MemoryClient({ apiKey: TEST_API_KEY });

    await expect(client.deleteUsers({ [key]: blank })).rejects.toThrow(key);

    expect(findFetchCall(mock, "/v1/entities/")).toBeUndefined();
    expect(findFetchCall(mock, "/v2/entities/", "DELETE")).toBeUndefined();
  });
});

describe("MemoryClient - deleteUsers() valid inputs", () => {
  test("deletes the named entity", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v2/entities/user/u1/", {
      status: 200,
      body: { message: "ok" },
    });
    const mock = setupMockFetch(extra);
    const client = new MemoryClient({ apiKey: TEST_API_KEY });

    await client.deleteUsers({ userId: "u1" });

    expect(
      findFetchCall(mock, "/v2/entities/user/u1/", "DELETE"),
    ).toBeDefined();
  });

  test("with no IDs still deletes every listed entity", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/entities/", {
      status: 200,
      body: createMockAllUsers([
        createMockUser({ name: "u1", type: "user" }),
        createMockUser({ name: "a1", type: "agent" }),
      ]),
    });
    extra.set("/v2/entities/user/u1/", {
      status: 200,
      body: { message: "ok" },
    });
    extra.set("/v2/entities/agent/a1/", {
      status: 200,
      body: { message: "ok" },
    });
    const mock = setupMockFetch(extra);
    const client = new MemoryClient({ apiKey: TEST_API_KEY });

    await client.deleteUsers();

    expect(
      findFetchCall(mock, "/v2/entities/user/u1/", "DELETE"),
    ).toBeDefined();
    expect(
      findFetchCall(mock, "/v2/entities/agent/a1/", "DELETE"),
    ).toBeDefined();
  });
});

describe("MemoryClient - add() entity IDs", () => {
  function mockAdd() {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v3/memories/add/", { status: 200, body: [] });
    return setupMockFetch(extra);
  }

  test("rejects filters and sends no request", async () => {
    const mock = mockAdd();
    const client = new MemoryClient({ apiKey: TEST_API_KEY });

    await expect(
      client.add([{ role: "user", content: "hi" }], {
        filters: { user_id: "u1" },
      }),
    ).rejects.toThrow(/filters.*userId/);

    expect(findFetchCall(mock, "/v3/memories/add/", "POST")).toBeUndefined();
  });

  test("treats filters: undefined as not provided", async () => {
    const mock = mockAdd();
    const client = new MemoryClient({ apiKey: TEST_API_KEY });

    await client.add([{ role: "user", content: "hi" }], {
      userId: "u1",
      filters: undefined,
    });

    const call = findFetchCall(mock, "/v3/memories/add/", "POST");
    expect(getFetchBody(call!).user_id).toBe("u1");
  });

  test("sends top-level entity IDs in the body", async () => {
    const mock = mockAdd();
    const client = new MemoryClient({ apiKey: TEST_API_KEY });

    await client.add([{ role: "user", content: "hi" }], {
      userId: "u1",
      agentId: "a1",
      appId: "p1",
      runId: "r1",
    });

    const body = getFetchBody(
      findFetchCall(mock, "/v3/memories/add/", "POST")!,
    );
    expect(body).toMatchObject({
      user_id: "u1",
      agent_id: "a1",
      app_id: "p1",
      run_id: "r1",
    });
  });
});
