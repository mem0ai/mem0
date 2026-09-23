/**
 * MemoryClient unit tests — profiles.
 * Verifies request construction and the verbatim round-trip of user-controlled
 * profile/schema keys, not mock response echo.
 */
import { MemoryClient } from "../mem0";
import type { ProfileStatus } from "../mem0.types";
import { TEST_API_KEY } from "./helpers";
import {
  setupMockFetch,
  findFetchCall,
  getFetchBody,
  installConsoleSuppression,
} from "./setup";

installConsoleSuppression();

describe("MemoryClient - getProfile()", () => {
  test("reads the v2 entity route and keeps profile keys verbatim", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v2/entities/user/alice/profile/", {
      status: 200,
      body: {
        // Customer schema keys: camel-casing these would break the schema they wrote.
        profile: {
          favorite_topics: ["hiking"],
          work_style: { preferred_hours: "mornings" },
        },
        status: "succeeded",
        entity_type: "user",
        entity_id: "alice",
        updated_at: "2026-02-08T00:00:00Z",
        generation_count: 3,
      },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const result = await client.getProfile({ entityId: "alice" });

    const call = findFetchCall(mock, "/v2/entities/user/alice/profile/");
    expect(call).toBeDefined();

    expect(result.profile).toEqual({
      favorite_topics: ["hiking"],
      work_style: { preferred_hours: "mornings" },
    });
    expect(result.entityType).toBe("user");
    expect(result.entityId).toBe("alice");
    expect(result.generationCount).toBe(3);
    expect(result.status).toBe("succeeded");
  });

  test("status keeps its wire spelling", async () => {
    // A status is a VALUE, not a key, so the client does not camel-case it.
    // Declaring the union as `insufficientData` made tsc reject the comparison
    // that works and accept one that can never be true.
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v2/entities/user/bob/profile/", {
      status: 200,
      body: {
        profile: {},
        status: "insufficient_data",
        entity_type: "user",
        entity_id: "bob",
      },
    });
    setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const result = await client.getProfile({ entityId: "bob" });

    expect(result.status).toBe("insufficient_data");
    // Assignable without a cast: the declared union must contain the wire value.
    const status: ProfileStatus = result.status;
    expect(status).not.toBe("insufficientData");
  });

  test("scopes to user and encodes the entity id", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v2/entities/user/", {
      status: 200,
      body: { profile: {}, status: "pending", entity_type: "user" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.getProfile({ entityId: "a/b" });

    const call = findFetchCall(mock, "/v2/entities/user/a%2Fb/profile/");
    expect(call).toBeDefined();
  });
});

describe("MemoryClient - generateProfile()", () => {
  test("sends operation trigger with the entity to the jobs collection", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v2/profiles/jobs/", {
      status: 202,
      body: {
        message: "Profile generation started.",
        entity_type: "user",
        entity_id: "alice",
        profile_id: "p_1",
        status: "PENDING",
      },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const result = await client.generateProfile({ entityId: "alice" });

    const call = findFetchCall(mock, "/v2/profiles/jobs/", "POST");
    expect(call).toBeDefined();
    const body = getFetchBody(call!);
    expect(body.operation).toBe("trigger");
    expect(body.entity_type).toBe("user");
    expect(body.entity_id).toBe("alice");
    expect(result.profileId).toBe("p_1");
  });
});

describe("MemoryClient - profile settings", () => {
  test("sends schema property names verbatim and returns them unchanged", async () => {
    const schema = {
      type: "object",
      properties: {
        favorite_topics: {
          type: "array",
          description: "Topics the user returns to",
          items: { type: "string" },
        },
        workStyle: {
          type: "string",
          description: "How the user prefers to work",
        },
      },
    };

    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v2/profiles/settings/", {
      status: 200,
      body: {
        enabled: true,
        entities: {
          user: {
            schema,
            custom_instructions: "Focus on durable preferences",
          },
        },
      },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const result = await client.updateProfileSettings({
      enabled: true,
      schema,
      customInstructions: "Focus on durable preferences",
    });

    const call = findFetchCall(mock, "/v2/profiles/settings/", "POST");
    expect(call).toBeDefined();
    const body = getFetchBody(call!);

    // Mixed casing goes out exactly as written, nested under the entity type.
    expect(body.entities.user.schema).toEqual(schema);
    expect(body.entities.user.custom_instructions).toBe(
      "Focus on durable preferences",
    );
    expect(body.enabled).toBe(true);
    // A flat schema is rejected by the API with "Unsupported settings".
    expect("schema" in body).toBe(false);

    // And the customer's property names survive the round trip.
    expect(result.entities?.user?.schema).toEqual(schema);
    expect(result.entities?.user?.customInstructions).toBe(
      "Focus on durable preferences",
    );
  });

  test("scopes entity-level settings under user", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v2/profiles/settings/", {
      status: 200,
      body: { enabled: true },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.updateProfileSettings({
      schema: { type: "object", properties: {} },
    });

    const body = getFetchBody(
      findFetchCall(mock, "/v2/profiles/settings/", "POST")!,
    );
    expect(Object.keys(body.entities)).toEqual(["user"]);
  });

  test("omits fields the caller did not set", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v2/profiles/settings/", {
      status: 200,
      body: {
        enabled: false,
        entities: { user: { schema: null, custom_instructions: null } },
      },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.updateProfileSettings({ enabled: false });

    const call = findFetchCall(mock, "/v2/profiles/settings/", "POST");
    const body = getFetchBody(call!);
    expect(body.enabled).toBe(false);
    // Nothing entity-scoped was passed, so no entities key is sent at all.
    expect("entities" in body).toBe(false);
    expect("schema" in body).toBe(false);
    expect("custom_instructions" in body).toBe(false);
  });

  test("getProfileSettings reads the v2 route", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v2/profiles/settings/", {
      status: 200,
      body: {
        enabled: true,
        entities: {
          user: {
            schema: { properties: { favorite_topics: { type: "array" } } },
            custom_instructions: null,
          },
        },
        capabilities: { full_rebuild: false },
      },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const result = await client.getProfileSettings();

    expect(findFetchCall(mock, "/v2/profiles/settings/")).toBeDefined();
    expect(result.enabled).toBe(true);
    expect(result.entities?.user?.schema).toEqual({
      properties: { favorite_topics: { type: "array" } },
    });
    expect(result.capabilities?.fullRebuild).toBe(false);
  });
});

describe("MemoryClient - sampleProfiles()", () => {
  test("sampleProfiles omits limit when unset", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v2/profiles/jobs/", {
      status: 202,
      body: {
        job_id: "job_1",
        status: "QUEUED",
        status_url: "/v2/profiles/jobs/job_1/",
        operation: "sample",
        entity_type: "user",
        sampled: 5,
        results: [],
      },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.sampleProfiles();

    const call = findFetchCall(mock, "/v2/profiles/jobs/", "POST");
    // Every job names an entity kind: the API refuses one that does not.
    expect(getFetchBody(call!)).toEqual({
      operation: "sample",
      entity_type: "user",
    });
  });

  test("sampleProfiles passes an explicit limit", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v2/profiles/jobs/", {
      status: 202,
      body: {
        job_id: "job_2",
        status: "QUEUED",
        status_url: "/v2/profiles/jobs/job_2/",
        operation: "sample",
        entity_type: "user",
        sampled: 3,
        results: [],
      },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const result = await client.sampleProfiles({ limit: 3 });

    const call = findFetchCall(mock, "/v2/profiles/jobs/", "POST");
    expect(getFetchBody(call!).operation).toBe("sample");
    expect(getFetchBody(call!).limit).toBe(3);
    expect(getFetchBody(call!).entity_type).toBe("user");
    expect(result.sampled).toBe(3);
  });
});
