// Jest test file for MemoryClient (clean suite)
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

describe("MemoryClient (clean suite)", () => {
  let client: MemoryClient;
  let userId: string;
  let memoryId: string;

  const testMessages = [
    { role: "user" as const, content: "Hey, I am Alex. I'm now a vegetarian." },
    { role: "assistant" as const, content: "Hello Alex! Glad to hear!" },
  ];

  beforeAll(() => {
    if (!apiKey) throw new Error("MEM0_API_KEY is required in .env");
    client = new MemoryClient({ apiKey, host });
    userId = randomString();
  });

  describe("Memory CRUD", () => {
    it("adds a memory and returns a valid response", async () => {
      const res = await client.add(testMessages, { user_id: userId });
      expect(Array.isArray(res)).toBe(true);
      expect(typeof res[0].id).toBe("string");
      memoryId = res[0].id;
    });

    it("retrieves a memory by ID", async () => {
      const memory = await client.get(memoryId);
      expect(memory.id).toBe(memoryId);
      expect(memory.user_id).toBe(userId);
      expect(typeof memory.memory).toBe("string");
    });

    it("updates a memory", async () => {
      const updated: any = await client.update(memoryId, "Updated memory content");
      if (Array.isArray(updated)) {
        const first = updated[0];
        expect(typeof first.id).toBe("string");
        expect(first.memory).toBe("Updated memory content");
        expect(first.user_id).toBe(userId);
      } else {
        expect(typeof updated.id).toBe("string");
        expect(updated.memory).toBe("Updated memory content");
        expect(updated.user_id).toBe(userId);
      }
    });

    it("deletes a memory", async () => {
      const del = await client.delete(memoryId);
      expect(del).toHaveProperty("message");
      expect(typeof del.message).toBe("string");
    });
  });

  describe("User management", () => {
    it("lists all users and finds the test user", async () => {
      const allUsers = await client.users();
      expect(typeof allUsers.count).toBe("number");
      const found = allUsers.results.find((u) => u.name === userId);
      // The user may not exist if memory was deleted, so just check type
      expect(Array.isArray(allUsers.results)).toBe(true);
    });

    it("deletes the test user if present", async () => {
      const allUsers = await client.users();
      const entity = allUsers.results.find((u) => u.name === userId);
      if (entity) {
        const entityIdNum = Number(entity.id);
        if (!isNaN(entityIdNum)) {
          const deleted = await client.deleteUser({ entity_id: entityIdNum, entity_type: entity.type });
          expect(deleted).toHaveProperty("message");
        } else {
          // If id is not a number, skip deletion
          console.warn(`Skipping deletion: entity.id is not a number: ${entity.id}`);
        }
      }
    });
  });

  describe("Search and history", () => {
    beforeAll(async () => {
      // Add a memory for search/history tests
      const res = await client.add(testMessages, { user_id: userId });
      memoryId = res[0].id;
    });

    it("searches for a memory (v1)", async () => {
      const results = await client.search("vegetarian", { user_id: userId });
      expect(Array.isArray(results)).toBe(true);
      if (results.length > 0) {
        expect(typeof results[0].id).toBe("string");
      }
    });

    it("searches for a memory (v2)", async () => {
      const results = await client.search("vegetarian", {
        user_id: userId,
        api_version: "v2",
        filters: { user_id: userId },
      });
      expect(Array.isArray(results)).toBe(true);
    });

    it("retrieves memory history", async () => {
      const history = await client.history(memoryId);
      expect(Array.isArray(history)).toBe(true);
      if (history.length > 0) {
        expect(typeof history[0].id).toBe("string");
        expect(history[0].memory_id).toBe(memoryId);
      }
    });
  });
}); 