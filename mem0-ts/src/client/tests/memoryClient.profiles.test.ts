/**
 * MemoryClient unit tests — profiles.
 * Verifies request construction and the verbatim round-trip of user-controlled
 * profile/schema keys, not mock response echo.
 */
import { MemoryClient } from "../mem0";
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

  test("defaults to user and encodes the entity id", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v2/entities/agent/", {
      status: 200,
      body: { profile: {}, status: "pending", entity_type: "agent" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.getProfile({ entityId: "a/b", entityType: "agent" });

    const call = findFetchCall(mock, "/v2/entities/agent/a%2Fb/profile/");
    expect(call).toBeDefined();
  });
});

describe("MemoryClient - generateProfile()", () => {
  test("posts entity_type and entity_id to the trigger route", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v2/profiles/trigger/", {
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

    const call = findFetchCall(mock, "/v2/profiles/trigger/", "POST");
    expect(call).toBeDefined();
    const body = getFetchBody(call!);
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
        schema,
        custom_instructions: "Focus on durable preferences",
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

    // Mixed casing goes out exactly as written.
    expect(body.schema).toEqual(schema);
    expect(body.custom_instructions).toBe("Focus on durable preferences");
    expect(body.enabled).toBe(true);
    expect(result.schema).toEqual(schema);
    expect(result.customInstructions).toBe("Focus on durable preferences");
  });

  test("omits fields the caller did not set", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v2/profiles/settings/", {
      status: 200,
      body: { enabled: false, schema: null, custom_instructions: null },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.updateProfileSettings({ enabled: false });

    const call = findFetchCall(mock, "/v2/profiles/settings/", "POST");
    const body = getFetchBody(call!);
    expect(body.enabled).toBe(false);
    expect("schema" in body).toBe(false);
    expect("custom_instructions" in body).toBe(false);
  });

  test("getProfileSettings reads the v2 route", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v2/profiles/settings/", {
      status: 200,
      body: {
        enabled: true,
        schema: { properties: { favorite_topics: { type: "array" } } },
        custom_instructions: null,
      },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const result = await client.getProfileSettings();

    expect(findFetchCall(mock, "/v2/profiles/settings/")).toBeDefined();
    expect(result.enabled).toBe(true);
    expect(result.schema).toEqual({
      properties: { favorite_topics: { type: "array" } },
    });
  });
});

describe("MemoryClient - sampleProfiles() / regenerateProfiles()", () => {
  test("sampleProfiles omits limit when unset", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v2/profiles/samples/", {
      status: 202,
      body: { message: "Sampling 5 users.", sampled: 5, results: [] },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.sampleProfiles();

    const call = findFetchCall(mock, "/v2/profiles/samples/", "POST");
    expect(getFetchBody(call!)).toEqual({});
  });

  test("sampleProfiles passes an explicit limit", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v2/profiles/samples/", {
      status: 202,
      body: { message: "Sampling 3 users.", sampled: 3, results: [] },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const result = await client.sampleProfiles({ limit: 3 });

    const call = findFetchCall(mock, "/v2/profiles/samples/", "POST");
    expect(getFetchBody(call!).limit).toBe(3);
    expect(result.sampled).toBe(3);
  });

  test("regenerateProfiles posts to the regenerate route", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v2/profiles/regenerate/", {
      status: 202,
      body: {
        status: "accepted",
        message: "Regenerating profiles.",
        project_id: "proj_abc",
        existing_profile_count: 12,
      },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const result = await client.regenerateProfiles();

    expect(
      findFetchCall(mock, "/v2/profiles/regenerate/", "POST"),
    ).toBeDefined();
    expect(result.existingProfileCount).toBe(12);
    expect(result.projectId).toBe("proj_abc");
  });
});
