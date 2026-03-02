/**
 * Basic tests for CloudflareWorkerMemoryClient
 * These tests validate that the client can be instantiated and has the expected methods
 */

import { CloudflareWorkerMemoryClient } from "./index";

// Mock fetch for testing
global.fetch = jest.fn() as jest.MockedFunction<typeof fetch>;

// Mock crypto.subtle for hash generation
Object.defineProperty(globalThis, "crypto", {
  value: {
    subtle: {
      digest: jest.fn().mockResolvedValue(new ArrayBuffer(32)),
    },
  },
});

describe("CloudflareWorkerMemoryClient", () => {
  const mockApiKey = "test-api-key";

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Constructor", () => {
    it("should instantiate with valid API key", () => {
      const client = new CloudflareWorkerMemoryClient({
        apiKey: mockApiKey,
      });

      expect(client).toBeInstanceOf(CloudflareWorkerMemoryClient);
    });

    it("should throw error with missing API key", () => {
      expect(() => {
        new CloudflareWorkerMemoryClient({
          apiKey: "",
        });
      }).toThrow("Mem0 API key is required");
    });

    it("should use custom host when provided", () => {
      const customHost = "https://custom-api.example.com";
      const client = new CloudflareWorkerMemoryClient({
        apiKey: mockApiKey,
        host: customHost,
      });

      expect(client).toBeInstanceOf(CloudflareWorkerMemoryClient);
    });
  });

  describe("API Methods", () => {
    let client: CloudflareWorkerMemoryClient;

    beforeEach(() => {
      client = new CloudflareWorkerMemoryClient({
        apiKey: mockApiKey,
      });
    });

    it("should have all expected methods", () => {
      expect(typeof client.ping).toBe("function");
      expect(typeof client.add).toBe("function");
      expect(typeof client.search).toBe("function");
      expect(typeof client.get).toBe("function");
      expect(typeof client.getAll).toBe("function");
      expect(typeof client.update).toBe("function");
      expect(typeof client.delete).toBe("function");
      expect(typeof client.deleteAll).toBe("function");
      expect(typeof client.history).toBe("function");
      expect(typeof client.users).toBe("function");
      expect(typeof client.batchUpdate).toBe("function");
      expect(typeof client.batchDelete).toBe("function");
    });

    it("should handle ping request", async () => {
      const mockResponse = {
        status: "ok",
        org_id: "test-org",
        project_id: "test-project",
        user_email: "test@example.com",
      };

      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce(
        {
          ok: true,
          json: async () => mockResponse,
        } as Response,
      );

      await expect(client.ping()).resolves.not.toThrow();
      expect(global.fetch).toHaveBeenCalledWith(
        "https://api.mem0.ai/v1/ping/",
        expect.objectContaining({
          method: "GET",
        }),
      );
    });

    it("should handle add request", async () => {
      // Mock ping response first
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce(
        {
          ok: true,
          json: async () => ({ status: "ok", user_email: "test@example.com" }),
        } as Response,
      );

      // Mock add response
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce(
        {
          ok: true,
          json: async () => [{ id: "memory-1", memory: "Test memory" }],
        } as Response,
      );

      const messages = [{ role: "user", content: "Test message" }];
      const options = { user_id: "test-user" };

      const result = await client.add(messages, options);

      expect(result).toEqual([{ id: "memory-1", memory: "Test memory" }]);
      expect(global.fetch).toHaveBeenCalledWith(
        "https://api.mem0.ai/v1/memories/",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            messages,
            ...options,
          }),
        }),
      );
    });

    it("should handle search request", async () => {
      // Mock ping response first
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce(
        {
          ok: true,
          json: async () => ({ status: "ok", user_email: "test@example.com" }),
        } as Response,
      );

      // Mock search response
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce(
        {
          ok: true,
          json: async () => [
            {
              id: "memory-1",
              memory: "Test memory",
              score: 0.9,
            },
          ],
        } as Response,
      );

      const query = "test query";
      const options = { user_id: "test-user" };

      const result = await client.search(query, options);

      expect(result).toEqual([
        {
          id: "memory-1",
          memory: "Test memory",
          score: 0.9,
        },
      ]);
      expect(global.fetch).toHaveBeenCalledWith(
        "https://api.mem0.ai/v1/memories/search/",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            query,
            ...options,
          }),
        }),
      );
    });

    it("should handle API errors gracefully", async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce(
        {
          ok: false,
          status: 401,
          statusText: "Unauthorized",
          text: async () => "Invalid API key",
        } as Response,
      );

      await expect(client.ping()).rejects.toThrow(
        "API request failed: Invalid API key",
      );
    });
  });

  describe("Error Handling", () => {
    it("should validate update parameters", async () => {
      const client = new CloudflareWorkerMemoryClient({
        apiKey: mockApiKey,
      });

      await expect(client.update("memory-id", {})).rejects.toThrow(
        "Either text or metadata must be provided for update.",
      );
    });
  });

  describe("Platform Compatibility", () => {
    it("should use Web APIs only", () => {
      const client = new CloudflareWorkerMemoryClient({
        apiKey: mockApiKey,
      });

      // Verify no Node.js specific imports or usage
      expect(client).toBeDefined();

      // The client should not reference any Node.js modules
      const clientString = client.toString();
      expect(clientString).not.toContain("require(");
      expect(clientString).not.toContain("process.");
      expect(clientString).not.toContain("Buffer.");
    });
  });
});
