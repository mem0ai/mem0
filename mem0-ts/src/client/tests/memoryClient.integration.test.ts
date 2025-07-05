import { describe, it, beforeAll, expect, jest } from '@jest/globals';
import { MemoryClient } from "../mem0";
import dotenv from "dotenv";

dotenv.config();

const apiKey = process.env.MEM0_API_KEY || '';
const host = process.env.MEM0_API_HOST || "https://api.mem0.ai";

function randomString() {
  return (
    Math.random().toString(36).substring(2, 15) +
    Math.random().toString(36).substring(2, 15)
  );
}

// Utility to create an organization
async function createOrganization(apiKey, orgName) {
  const response = await fetch('https://api.mem0.ai/api/v1/orgs/organizations/', {
    method: 'POST',
    headers: {
      'Authorization': `Token ${apiKey}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ name: orgName })
  });
  if (!response.ok) {
    throw new Error(`Failed to create organization: ${await response.text()}`);
  }
  return response.json(); // { message, org_id }
}

// Utility to create a project in an organization
async function createProject(apiKey, orgId, projectName) {
  const response = await fetch(`https://api.mem0.ai/api/v1/orgs/organizations/${orgId}/projects/`, {
    method: 'POST',
    headers: {
      'Authorization': `Token ${apiKey}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ name: projectName })
  });
  if (!response.ok) {
    throw new Error(`Failed to create project: ${await response.text()}`);
  }
  return response.json(); // { message, project_id }
}

let client;
let orgId;
let projectId;

async function getOrganizations(apiKey) {
  const response = await fetch('https://api.mem0.ai/api/v1/orgs/organizations/', {
    method: 'GET',
    headers: { 'Authorization': `Token ${apiKey}` }
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json(); // Array of orgs
}

async function getProjects(apiKey, orgId) {
  const response = await fetch(`https://api.mem0.ai/api/v1/orgs/organizations/${orgId}/projects/`, {
    method: 'GET',
    headers: { 'Authorization': `Token ${apiKey}` }
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json(); // Array of projects
}

beforeAll(async () => {
  // Always use the first org and first project for all main tests
  const orgs = await getOrganizations(apiKey);
  if (!orgs.length) throw new Error('No organizations found for this API key');
  orgId = orgs[0].org_id;

  const projects = await getProjects(apiKey, orgId);
  if (!projects.length) throw new Error('No projects found for this organization');
  projectId = projects[0].project_id;

  client = new MemoryClient({ apiKey, host, organizationId: orgId, projectId });
});

describe("MemoryClient Integration Tests", () => {
  it("creates an organization", async () => {
    const orgName = 'Test Organization ' + Date.now();
    const orgRes = await createOrganization(apiKey, orgName);
    expect(typeof orgRes.org_id).toBe("string");
    // Do not use this org for other tests
  });

  it("creates a project in the organization", async () => {
    // Use the first org for project creation test, but do not use this project for other tests
    const projectName = 'Test Project ' + Date.now();
    const projRes = await createProject(apiKey, orgId, projectName);
    expect(typeof projRes.project_id).toBe("string");
  });

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
    const updateRes = await client.batchUpdate([{ memoryId, text: "Updated memory content for batch update." }]);
    expect(typeof updateRes).toBe("object");
    expect(updateRes).toHaveProperty("message");
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
    const deleteRes = await client.batchDelete([memoryId]);
    expect(typeof deleteRes).toBe("object");
    expect(deleteRes).toHaveProperty("message");
  });

  it("submits feedback for a memory", async () => {
    const tempUserId = randomString();
    const memoryMessages = [
      { role: "user" as const, content: "Remember that my favorite animal is the dolphin." },
      { role: "assistant" as const, content: "Okay, I will remember your favorite animal is the dolphin." }
    ];
    const res = await client.add(memoryMessages, { user_id: tempUserId });
    expect(res.length).toBeGreaterThan(0);
    const memoryId = res[0].id;
    // Explicitly pass org_id and project_id for feedback
    const feedbackRes = await client.feedback({
      memory_id: memoryId,
      feedback: null,
      org_id: orgId,
      project_id: projectId
    });
    expect(feedbackRes).toHaveProperty("id");
    expect(feedbackRes).toHaveProperty("feedback");
    expect(feedbackRes).toHaveProperty("feedback_reason");
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
    // Submit actual feedback (e.g., POSITIVE)
    const feedbackRes = await client.feedback({
      memory_id: memoryId,
      feedback: "POSITIVE",
      org_id: orgId,
      project_id: projectId
    });
    expect(feedbackRes).toHaveProperty("id");
    expect(feedbackRes.feedback).toBe("POSITIVE");
    expect(feedbackRes).toHaveProperty("feedback_reason");
  });

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

  it("gets organizations", async () => {
    const orgs = await getOrganizations(apiKey);
    expect(Array.isArray(orgs)).toBe(true);
    expect(orgs.length).toBeGreaterThan(0);
    expect(orgs[0]).toHaveProperty('org_id');
  });

  it("gets projects for the first organization", async () => {
    const projects = await getProjects(apiKey, orgId);
    expect(Array.isArray(projects)).toBe(true);
    expect(projects.length).toBeGreaterThan(0);
    expect(projects[0]).toHaveProperty('project_id');
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