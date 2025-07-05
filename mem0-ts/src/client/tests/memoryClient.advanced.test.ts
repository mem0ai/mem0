import { describe, it, beforeAll, expect, jest } from '@jest/globals';
import { MemoryClient } from "../mem0";
import dotenv from "dotenv";

dotenv.config();

jest.setTimeout(20000);

const apiKey = process.env.MEM0_API_KEY || "";
const host = process.env.MEM0_API_HOST || "https://api.mem0.ai";

function randomString() {
  return (
    Math.random().toString(36).substring(2, 15) +
    Math.random().toString(36).substring(2, 15)
  );
}

describe("MemoryClient Advanced Features", () => {
  let client: MemoryClient;

  beforeAll(() => {
    if (!apiKey) throw new Error("MEM0_API_KEY is required in .env");
    client = new MemoryClient({ apiKey, host });
  });

  it("adds a memory with metadata and retrieves it by metadata filter", async () => {
    const userId = randomString();
    const messages = [
      { role: "user" as const, content: "I love vegan food." },
      { role: "assistant" as const, content: "Noted your preference for vegan food." }
    ];
    await client.add(messages, { user_id: userId, metadata: { food: "vegan" } });

    const results = await client.search("vegan", {
      user_id: userId,
      filters: { metadata: { food: "vegan" } }
    });
    expect(results.length).toBeGreaterThan(0);
    expect(results[0].metadata?.food).toBe("vegan");
  });

  it("adds a memory for an agent and retrieves it", async () => {
    const agentId = randomString();
    const messages = [
      { role: "assistant" as const, content: "My name is Alice. I am an AI tutor." }
    ];
    await client.add(messages, { agent_id: agentId });

    const results = await client.search("Alice", { agent_id: agentId });
    expect(results.length).toBeGreaterThan(0);
    expect(results[0].memory).toContain("Alice");
  });

  it("adds a memory for both user and agent and retrieves for each", async () => {
    const userId = randomString();
    const agentId = randomString();
    const messages = [
      { role: "user" as const, content: "I'm travelling to San Francisco" },
      { role: "assistant" as const, content: "I'm going to Dubai next month." }
    ];
    await client.add(messages, { user_id: userId, agent_id: agentId });

    const userResults = await client.search("San Francisco", { user_id: userId });
    expect(userResults.length).toBeGreaterThan(0);

    const agentResults = await client.search("Dubai", { agent_id: agentId });
    expect(agentResults.length).toBeGreaterThan(0);
  });

  it("adds a memory in async mode", async () => {
    const userId = randomString();
    const messages = [
      { role: "user" as const, content: "I love hiking and outdoor activities" },
      { role: "assistant" as const, content: "I'll remember your interest in hiking." }
    ];
    await client.add(messages, { user_id: userId, async_mode: true });
    await new Promise(res => setTimeout(res, 3000));
    const results = await client.search("hiking", { user_id: userId });
    expect(results.length).toBeGreaterThan(0);
  });

  it("searches with advanced filters (v2)", async () => {
    const userId = randomString();
    await client.add([
      { role: "user" as const, content: "I am vegan and like Italian food." }
    ], {
      user_id: userId,
      metadata: { food: "vegan" }
    });

    const filters = {
      AND: [
        { metadata: { food: "vegan" } }
      ]
    };
    const results = await client.search("vegan", {
      user_id: userId,
      api_version: "v2",
      filters
    });
    expect(results.length).toBeGreaterThan(0);
  });

  it("retrieves paginated memories", async () => {
    const userId = randomString();
    for (let i = 0; i < 5; i++) {
      await client.add([{ role: "user" as const, content: `Memory ${i}` }], { user_id: userId });
    }
    const page1: any = await client.getAll({ user_id: userId, page: 1, page_size: 2 });
    // If getAll returns { results: [], count: N }, use results.length
    const arr = Array.isArray(page1) ? page1 : page1.results;
    expect(arr.length).toBeLessThanOrEqual(2);
  });

  it("batch updates and deletes memories", async () => {
    const userId = randomString();
    const addRes = await client.add([
      { role: "user" as const, content: "I like football" },
      { role: "user" as const, content: "I like basketball" }
    ], { user_id: userId });

    const updates = addRes.map((mem: any) => ({
      memoryId: mem.id,
      text: "Updated: " + (mem.memory || "")
    }));
    await client.batchUpdate(updates);

    const all = await client.getAll({ user_id: userId });
    expect(all.every((mem: any) => mem.memory.startsWith("Updated:"))).toBe(true);

    const ids = addRes.map((mem: any) => mem.id);
    await client.batchDelete(ids);

    const afterDelete = await client.getAll({ user_id: userId });
    expect(afterDelete.length).toBe(0);
  });

  it("deletes all memories for a user", async () => {
    const userId = randomString();
    await client.add([{ role: "user" as const, content: "Temp memory" }], { user_id: userId });
    await client.deleteAll({ user_id: userId });
    const afterDelete = await client.getAll({ user_id: userId });
    expect(afterDelete.length).toBe(0);
  });

  it("retrieves all users", async () => {
    const users = await client.users();
    expect(Array.isArray(users.results)).toBe(true);
  });
}); 