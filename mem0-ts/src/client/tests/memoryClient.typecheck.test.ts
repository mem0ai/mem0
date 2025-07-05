import { describe, it, beforeAll, expect, jest } from '@jest/globals';
import { MemoryClient } from "../mem0";
import dotenv from "dotenv";

dotenv.config();

jest.setTimeout(20000);

const apiKey = process.env.MEM0_API_KEY || '';  
const host = process.env.MEM0_API_HOST || "https://api.mem0.ai";

function randomString() {
  return (
    Math.random().toString(36).substring(2, 15) +
    Math.random().toString(36).substring(2, 15)
  );
}

// Utility function to check Memory type/shape
function checkMemoryType(mem: any) {
  expect(typeof mem.id).toBe("string");
  if (mem.messages) {
    expect(Array.isArray(mem.messages)).toBe(true);
    for (const msg of mem.messages) {
      expect(["user", "assistant"]).toContain(msg.role);
      expect(typeof msg.content === "string" || typeof msg.content === "object").toBe(true);
    }
  }
  if (mem.event) expect(typeof mem.event).toBe("string");
  if (mem.data) expect(typeof mem.data.memory).toBe("string");
  if (mem.memory) expect(typeof mem.memory).toBe("string");
  if (mem.user_id) expect(typeof mem.user_id).toBe("string");
  if (mem.categories) {
    expect(Array.isArray(mem.categories)).toBe(true);
    for (const cat of mem.categories) expect(typeof cat).toBe("string");
  }
  if (mem.created_at) expect(typeof mem.created_at === "string" || mem.created_at instanceof Date).toBe(true);
  if (mem.updated_at) expect(typeof mem.updated_at === "string" || mem.updated_at instanceof Date).toBe(true);
  if (mem.metadata !== undefined) expect(typeof mem.metadata === "object" || mem.metadata === null).toBe(true);
  if (mem.agent_id !== undefined) expect(typeof mem.agent_id === "string" || mem.agent_id === null).toBe(true);
  if (mem.app_id !== undefined) expect(typeof mem.app_id === "string" || mem.app_id === null).toBe(true);
  if (mem.run_id !== undefined) expect(typeof mem.run_id === "string" || mem.run_id === null).toBe(true);
}

describe("MemoryClient Type/Shape Checks", () => {
  let client: MemoryClient;
  let userId: string;
  let memoryId: string;
  const testMessages = [
    { role: "user" as const, content: "Hey assistant, can you remember that my flight to San Francisco is on June 15th at 10am?" },
    { role: "assistant" as const, content: "Got it! I will remember that your flight to San Francisco is on June 15th at 10am." },
    { role: "user" as const, content: "Also, remind me to pack a jacket because it might be cold there." },
    { role: "assistant" as const, content: "Sure! I'll remind you to pack a jacket for your San Francisco trip." },
  ];

  beforeAll(async () => {
    if (!apiKey) throw new Error("MEM0_API_KEY is required in .env");
    client = new MemoryClient({ apiKey, host });
    userId = randomString();
    const res = await client.add(testMessages, { user_id: userId });
    if (!Array.isArray(res) || !res[0] || !res[0].id) {
      console.error("Unexpected response from client.add:", res);
      throw new Error("client.add did not return a valid memory array");
    }
    memoryId = res[0].id;
  });

  it("basic add memory sanity check (no typecheck)", async () => {
    const res = await client.add(testMessages, { user_id: userId });
    expect(res).toBeTruthy();
  });

  it("checks type of memory returned by add", async () => {
    const tempUserId = randomString();
    const memoryMessages = [
      { role: "user" as const, content: "Remember my favorite color is blue." },
      { role: "assistant" as const, content: "Got it, your favorite color is blue." }
    ];
    const res = await client.add(memoryMessages, { user_id: tempUserId });
    expect(Array.isArray(res)).toBe(true);
    expect(res.length).toBeGreaterThan(0);
    checkMemoryType(res[0]);
  });

  it("checks type of memory returned by get", async () => {
    const memory = await client.get(memoryId);
    checkMemoryType(memory);
  });

  it("checks type of memory returned by update", async () => {
    const updated: any = await client.update(memoryId, "Updated type check");
    if (Array.isArray(updated)) {
      checkMemoryType(updated[0]);
    } else {
      checkMemoryType(updated);
    }
  });

  it("checks type of memory returned by search", async () => {
    const results = await client.search("San Francisco", { user_id: userId });
    expect(Array.isArray(results)).toBe(true);
    if (results.length > 0) checkMemoryType(results[0]);
  });

  it("checks type of memory returned by getAll", async () => {
    const all: any = await client.getAll({ user_id: userId });
    const arr = Array.isArray(all) ? all : all.results;
    if (arr.length > 0) checkMemoryType(arr[0]);
  });

  it("checks type of memory returned by history", async () => {
    const history = await client.history(memoryId);
    expect(Array.isArray(history)).toBe(true);
    if (history.length > 0) checkMemoryType(history[0]);
  });
}); 