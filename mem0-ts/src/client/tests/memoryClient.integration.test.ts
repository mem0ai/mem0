import { describe, it, beforeAll, expect, jest } from '@jest/globals';
import { MemoryClient } from "../mem0";
import dotenv from "dotenv";

dotenv.config();

const apiKey = process.env.MEM0_API_KEY || '';  
const host = process.env.MEM0_API_HOST || "https://api.mem0.ai";
// const orgId = process.env.MEM0_ORG_ID || '';
// const projectId = process.env.MEM0_PROJECT_ID || '';

function randomString() {
  return (
    Math.random().toString(36).substring(2, 15) +
    Math.random().toString(36).substring(2, 15)
  );
}

let client;

beforeAll(async () => {
  // To use org/project-specific tests, pass orgId and projectId here:
  // client = new MemoryClient({ apiKey, host, organizationId: orgId, projectId });
  client = new MemoryClient({ apiKey, host });
  await client.ping();
});

describe("MemoryClient Integration Tests", () => {
  it("deletes a memory and returns a message", async () => {
    const tempUserId = randomString();
    const memoryMessages = [
      { role: "user" as const, content: "Remember that my dentist appointment is on August 5th at 2pm." },
      { role: "assistant" as const, content: "Okay, I will remember your dentist appointment is on August 5th at 2pm." }
    ];
    const res = await client.add(memoryMessages, { user_id: tempUserId });
    expect(res.length).toBeGreaterThan(0);
    const memoryId = res[0].id;
    const delRes = await client.delete(memoryId);
    expect(delRes).toHaveProperty("message");
  });

  it("batch updates memories", async () => {
    const tempUserId = randomString();
    const memoryMessages = [
      { role: "user" as const, content: "Remember that my favorite book is 'The Great Gatsby'." },
      { role: "assistant" as const, content: "Got it, your favorite book is 'The Great Gatsby'." }
    ];
    const res = await client.add(memoryMessages, { user_id: tempUserId });
    expect(res.length).toBeGreaterThan(0);
    const memoryId = res[0].id;
    // batchUpdate expects [{ memory_id, text }]
    const updateRes = await client.batchUpdate([{ memoryId: memoryId, text: "Updated memory content for batch update." }]);
    expect(typeof updateRes).toBe("object");
    expect(updateRes).toHaveProperty("message");
    expect(typeof updateRes.message).toBe("string");
    expect(updateRes.message.length).toBeGreaterThan(0);
  });

  it("batch deletes memories", async () => {
    const tempUserId = randomString();
    const memoryMessages = [
      { role: "user" as const, content: "Remember that my next car service is on December 10th at 9am." },
      { role: "assistant" as const, content: "Okay, I will remember your next car service is on December 10th at 9am." }
    ];
    const res = await client.add(memoryMessages, { user_id: tempUserId });
    expect(res.length).toBeGreaterThan(0);
    const memoryId = res[0].id;
    // batchDelete expects [memoryId]
    const deleteRes = await client.batchDelete([memoryId]);
    expect(typeof deleteRes).toBe("object");
    expect(deleteRes).toHaveProperty("message");
    expect(typeof deleteRes.message).toBe("string");
    expect(deleteRes.message.length).toBeGreaterThan(0);
  });

  // The following feedback tests require valid org_id and project_id to be set in the environment variables (MEM0_ORG_ID, MEM0_PROJECT_ID).
  // Uncomment and ensure these are set to run these tests.
  /*
  it("submits feedback for a memory", async () => {
    const tempUserId = randomString();
    const memoryMessages = [
      { role: "user" as const, content: "Remember that my favorite animal is the dolphin." },
      { role: "assistant" as const, content: "Okay, I will remember your favorite animal is the dolphin." }
    ];
    const res = await client.add(memoryMessages, { user_id: tempUserId });
    expect(res.length).toBeGreaterThan(0);
    const memoryId = res[0].id;
    const feedbackRes = await client.feedback({
      memory_id: memoryId,
      feedback: null
    });
    expect(feedbackRes).toHaveProperty("message");
  });

  it("submits actual feedback for a memory", async () => {
    const tempUserId = randomString();
    const memoryMessages = [
      { role: "user" as const, content: "Remember that my favorite fruit is mango." },
      { role: "assistant" as const, content: "Okay, I will remember your favorite fruit is mango." }
    ];
    const res = await client.add(memoryMessages, { user_id: tempUserId });
    expect(res.length).toBeGreaterThan(0);
    const memoryId = res[0].id;
    const feedbackRes = await client.feedback({
      memory_id: memoryId,
      feedback: "POSITIVE"
    });
    expect(feedbackRes).toHaveProperty("message");
  });
  */

  it("pings the API and sets telemetryId", async () => {
    const tempClient = new MemoryClient({ apiKey, host });
    await tempClient.ping();
    expect(typeof tempClient.telemetryId).toBe("string");
  });

  it("lists users", async () => {
    const users = await client.users();
    expect(users).toHaveProperty("results");
    expect(Array.isArray(users.results)).toBe(true);
  });

  // The following tests for deleteUser, deleteUsers, and webhooks are included for completeness.
  // They may require valid org/project setup and/or may not be supported in all environments.
  // Uncomment and adjust as needed for your environment.
  /*
  it("deletes a user by entity_id and entity_type", async () => {
    // You need a valid entity_id and entity_type for this test
    const delRes = await client.deleteUser({ entity_id: 123, entity_type: "user" });
    expect(delRes).toHaveProperty("message");
  });

  it("deletes users by user_id", async () => {
    const tempUserId = randomString();
    const delRes = await client.deleteUsers({ user_id: tempUserId });
    expect(delRes).toHaveProperty("message");
  });

  it("creates, gets, and deletes a webhook", async () => {
    // You need a valid projectId for this test
    const webhookPayload = {
      eventTypes: ["memory_add"],
      projectId: client.projectId,
      webhookId: "test-webhook-id",
      name: "Test Webhook",
      url: "https://example.com/webhook"
    };
    const createRes = await client.createWebhook(webhookPayload);
    expect(createRes).toHaveProperty("webhook_id");
    const getRes = await client.getWebhooks({ projectId: client.projectId });
    expect(Array.isArray(getRes)).toBe(true);
    const delRes = await client.deleteWebhook({ webhookId: createRes.webhook_id });
    expect(delRes).toHaveProperty("message");
  });
  */
}); 