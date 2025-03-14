import { MemoryClient } from "../mem0";
import dotenv from "dotenv";

dotenv.config();

const apiKey = process.env.MEM0_API_KEY || "";
// const client = new MemoryClient({ apiKey, host: 'https://api.mem0.ai', organizationId: "org_gRNd1RrQa4y52iK4tG8o59hXyVbaULikgq4kethC", projectId: "proj_7RfMkWs0PMgXYweGUNKqV9M9mgIRNt5XcupE7mSP" });
// const client = new MemoryClient({ apiKey, host: 'https://api.mem0.ai', organizationName: "saket-default-org", projectName: "default-project" });
const client = new MemoryClient({ apiKey, host: "https://api.mem0.ai" });

// Generate a random string
const randomString = () => {
  return (
    Math.random().toString(36).substring(2, 15) +
    Math.random().toString(36).substring(2, 15)
  );
};

describe("MemoryClient API", () => {
  let userId: string, memoryId: string;

  beforeAll(() => {
    userId = randomString();
  });

  const messages1 = [
    { role: "user", content: "Hey, I am Alex. I'm now a vegetarian." },
    { role: "assistant", content: "Hello Alex! Glad to hear!" },
  ];

  it("should add messages successfully", async () => {
    const res = await client.add(messages1, { user_id: userId || "" });

    // Validate the response contains an iterable list
    expect(Array.isArray(res)).toBe(true);

    // Validate the fields of the first message in the response
    const message = res[0];
    expect(typeof message.id).toBe("string");
    expect(typeof message.data?.memory).toBe("string");
    expect(typeof message.event).toBe("string");

    // Store the memory ID for later use
    memoryId = message.id;
  });

  it("should retrieve the specific memory by ID", async () => {
    const memory = await client.get(memoryId);

    // Validate that the memory fields have the correct types and values

    // Should be a string (memory id)
    expect(typeof memory.id).toBe("string");

    // Should be a string (the actual memory content)
    expect(typeof memory.memory).toBe("string");

    // Should be a string and equal to the userId
    expect(typeof memory.user_id).toBe("string");
    expect(memory.user_id).toBe(userId);

    // Should be null or any object (metadata)
    expect(
      memory.metadata === null || typeof memory.metadata === "object",
    ).toBe(true);

    // Should be an array of strings or null (categories)
    expect(Array.isArray(memory.categories) || memory.categories === null).toBe(
      true,
    );
    if (Array.isArray(memory.categories)) {
      memory.categories.forEach((category) => {
        expect(typeof category).toBe("string");
      });
    }

    // Should be a valid date (created_at)
    expect(new Date(memory.created_at || "").toString()).not.toBe(
      "Invalid Date",
    );

    // Should be a valid date (updated_at)
    expect(new Date(memory.updated_at || "").toString()).not.toBe(
      "Invalid Date",
    );
  });

  it("should retrieve all users successfully", async () => {
    const allUsers = await client.users();

    // Validate the number of users is a number
    expect(typeof allUsers.count).toBe("number");

    // Validate the structure of the first user
    const firstUser = allUsers.results[0];
    expect(typeof firstUser.id).toBe("string");
    expect(typeof firstUser.name).toBe("string");
    expect(typeof firstUser.created_at).toBe("string");
    expect(typeof firstUser.updated_at).toBe("string");
    expect(typeof firstUser.total_memories).toBe("number");
    expect(typeof firstUser.type).toBe("string");

    // Find the user with the name matching userId
    const entity = allUsers.results.find((user) => user.name === userId);
    expect(entity).not.toBeUndefined();

    // Store the entity ID for later use
    const entity_id = entity?.id;
    expect(typeof entity_id).toBe("string");
  });

  it("should retrieve all memories for the user", async () => {
    const res3 = await client.getAll({ user_id: userId });

    // Validate that res3 is an iterable list (array)
    expect(Array.isArray(res3)).toBe(true);

    if (res3.length > 0) {
      // Iterate through the first memory for validation (you can loop through all if needed)
      const memory = res3[0];

      // Should be a string (memory id)
      expect(typeof memory.id).toBe("string");

      // Should be a string (the actual memory content)
      expect(typeof memory.memory).toBe("string");

      // Should be a string and equal to the userId
      expect(typeof memory.user_id).toBe("string");
      expect(memory.user_id).toBe(userId);

      // Should be null or an object (metadata)
      expect(
        memory.metadata === null || typeof memory.metadata === "object",
      ).toBe(true);

      // Should be an array of strings or null (categories)
      expect(
        Array.isArray(memory.categories) || memory.categories === null,
      ).toBe(true);
      if (Array.isArray(memory.categories)) {
        memory.categories.forEach((category) => {
          expect(typeof category).toBe("string");
        });
      }

      // Should be a valid date (created_at)
      expect(new Date(memory.created_at || "").toString()).not.toBe(
        "Invalid Date",
      );

      // Should be a valid date (updated_at)
      expect(new Date(memory.updated_at || "").toString()).not.toBe(
        "Invalid Date",
      );
    } else {
      // If there are no memories, assert that the list is empty
      expect(res3.length).toBe(0);
    }
  });

  it("should search and return results based on provided query and filters (API version 2)", async () => {
    const searchOptionsV2 = {
      query: "What do you know about me?",
      filters: {
        OR: [{ user_id: userId }, { agent_id: "shopping-assistant" }],
      },
      threshold: 0.1,
      api_version: "v2",
    };

    const searchResultV2 = await client.search(
      "What do you know about me?",
      searchOptionsV2,
    );

    // Validate that searchResultV2 is an iterable list (array)
    expect(Array.isArray(searchResultV2)).toBe(true);

    if (searchResultV2.length > 0) {
      // Iterate through the first search result for validation (you can loop through all if needed)
      const memory = searchResultV2[0];

      // Should be a string (memory id)
      expect(typeof memory.id).toBe("string");

      // Should be a string (the actual memory content)
      expect(typeof memory.memory).toBe("string");

      if (memory.user_id) {
        // Should be a string and equal to userId
        expect(typeof memory.user_id).toBe("string");
        expect(memory.user_id).toBe(userId);
      }

      if (memory.agent_id) {
        // Should be a string (agent_id)
        expect(typeof memory.agent_id).toBe("string");
        expect(memory.agent_id).toBe("shopping-assistant");
      }

      // Should be null or an object (metadata)
      expect(
        memory.metadata === null || typeof memory.metadata === "object",
      ).toBe(true);

      // Should be an array of strings or null (categories)
      expect(
        Array.isArray(memory.categories) || memory.categories === null,
      ).toBe(true);
      if (Array.isArray(memory.categories)) {
        memory.categories.forEach((category) => {
          expect(typeof category).toBe("string");
        });
      }

      // Should be a valid date (created_at)
      expect(new Date(memory.created_at || "").toString()).not.toBe(
        "Invalid Date",
      );

      // Should be a valid date (updated_at)
      expect(new Date(memory.updated_at || "").toString()).not.toBe(
        "Invalid Date",
      );

      // Should be a number (score)
      expect(typeof memory.score).toBe("number");
    } else {
      // If no search results, assert that the list is empty
      expect(searchResultV2.length).toBe(0);
    }
  });

  it("should search and return results based on provided query (API version 1)", async () => {
    const searchResultV1 = await client.search("What is my name?", {
      user_id: userId,
    });

    // Validate that searchResultV1 is an iterable list (array)
    expect(Array.isArray(searchResultV1)).toBe(true);

    if (searchResultV1.length > 0) {
      // Iterate through the first search result for validation (you can loop through all if needed)
      const memory = searchResultV1[0];

      // Should be a string (memory id)
      expect(typeof memory.id).toBe("string");

      // Should be a string (the actual memory content)
      expect(typeof memory.memory).toBe("string");

      // Should be a string and equal to userId
      expect(typeof memory.user_id).toBe("string");
      expect(memory.user_id).toBe(userId);

      // Should be null or an object (metadata)
      expect(
        memory.metadata === null || typeof memory.metadata === "object",
      ).toBe(true);

      // Should be an array of strings or null (categories)
      expect(
        Array.isArray(memory.categories) || memory.categories === null,
      ).toBe(true);
      if (Array.isArray(memory.categories)) {
        memory.categories.forEach((category) => {
          expect(typeof category).toBe("string");
        });
      }

      // Should be a valid date (created_at)
      expect(new Date(memory.created_at || "").toString()).not.toBe(
        "Invalid Date",
      );

      // Should be a valid date (updated_at)
      expect(new Date(memory.updated_at || "").toString()).not.toBe(
        "Invalid Date",
      );

      // Should be a number (score)
      expect(typeof memory.score).toBe("number");
    } else {
      // If no search results, assert that the list is empty
      expect(searchResultV1.length).toBe(0);
    }
  });

  it("should retrieve history of a specific memory and validate the fields", async () => {
    const res22 = await client.history(memoryId);

    // Validate that res22 is an iterable list (array)
    expect(Array.isArray(res22)).toBe(true);

    if (res22.length > 0) {
      // Iterate through the first history entry for validation (you can loop through all if needed)
      const historyEntry = res22[0];

      // Should be a string (history entry id)
      expect(typeof historyEntry.id).toBe("string");

      // Should be a string (memory id related to the history entry)
      expect(typeof historyEntry.memory_id).toBe("string");

      // Should be a string and equal to userId
      expect(typeof historyEntry.user_id).toBe("string");
      expect(historyEntry.user_id).toBe(userId);

      // Should be a string or null (old memory)
      expect(
        historyEntry.old_memory === null ||
          typeof historyEntry.old_memory === "string",
      ).toBe(true);

      // Should be a string or null (new memory)
      expect(
        historyEntry.new_memory === null ||
          typeof historyEntry.new_memory === "string",
      ).toBe(true);

      // Should be an array of strings or null (categories)
      expect(
        Array.isArray(historyEntry.categories) ||
          historyEntry.categories === null,
      ).toBe(true);
      if (Array.isArray(historyEntry.categories)) {
        historyEntry.categories.forEach((category) => {
          expect(typeof category).toBe("string");
        });
      }

      // Should be a valid date (created_at)
      expect(new Date(historyEntry.created_at).toString()).not.toBe(
        "Invalid Date",
      );

      // Should be a valid date (updated_at)
      expect(new Date(historyEntry.updated_at).toString()).not.toBe(
        "Invalid Date",
      );

      // Should be a string, one of: ADD, UPDATE, DELETE, NOOP
      expect(["ADD", "UPDATE", "DELETE", "NOOP"]).toContain(historyEntry.event);

      // Validate conditions based on event type
      if (historyEntry.event === "ADD") {
        expect(historyEntry.old_memory).toBeNull();
        expect(historyEntry.new_memory).not.toBeNull();
      } else if (historyEntry.event === "UPDATE") {
        expect(historyEntry.old_memory).not.toBeNull();
        expect(historyEntry.new_memory).not.toBeNull();
      } else if (historyEntry.event === "DELETE") {
        expect(historyEntry.old_memory).not.toBeNull();
        expect(historyEntry.new_memory).toBeNull();
      }

      // Should be a list of objects or null (input)
      expect(
        Array.isArray(historyEntry.input) || historyEntry.input === null,
      ).toBe(true);
      if (Array.isArray(historyEntry.input)) {
        historyEntry.input.forEach((input) => {
          // Each input should be an object
          expect(typeof input).toBe("object");

          // Should have string content
          expect(typeof input.content).toBe("string");

          // Should have a role that is either 'user' or 'assistant'
          expect(["user", "assistant"]).toContain(input.role);
        });
      }
    } else {
      // If no history entries, assert that the list is empty
      expect(res22.length).toBe(0);
    }
  });

  it("should delete the user successfully", async () => {
    const allUsers = await client.users();
    const entity = allUsers.results.find((user) => user.name === userId);

    if (entity) {
      const deletedUser = await client.deleteUser(entity.id);

      // Validate the deletion message
      expect(deletedUser.message).toBe("Entity deleted successfully!");
    }
  });
});
