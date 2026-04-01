/// <reference types="jest" />
/**
 * Azure OpenAI Embedder — unit tests (mocked Azure OpenAI client).
 * Verifies that the `dimensions` parameter is only passed to the API
 * when the user explicitly configures `embeddingDims`.
 */

const mockEmbeddingsCreate = jest.fn();

jest.mock("openai", () => {
  return {
    __esModule: true,
    AzureOpenAI: jest.fn().mockImplementation(() => ({
      embeddings: { create: mockEmbeddingsCreate },
    })),
  };
});

import { AzureOpenAIEmbedder } from "../src/embeddings/azure";

const mockEmbedding = [0.1, 0.2, 0.3, 0.4, 0.5];

const baseConfig = {
  apiKey: "test-key",
  modelProperties: { endpoint: "https://test.openai.azure.com" },
};

describe("AzureOpenAIEmbedder (unit)", () => {
  beforeEach(() => {
    mockEmbeddingsCreate.mockReset();
    mockEmbeddingsCreate.mockResolvedValue({
      data: [{ embedding: mockEmbedding }],
    });
  });

  describe("dimensions parameter", () => {
    it("does NOT pass dimensions when embeddingDims is not set", async () => {
      const embedder = new AzureOpenAIEmbedder(baseConfig);

      await embedder.embed("hello");

      expect(mockEmbeddingsCreate).toHaveBeenCalledTimes(1);
      const callArgs = mockEmbeddingsCreate.mock.calls[0][0];
      expect(callArgs).not.toHaveProperty("dimensions");
      expect(callArgs).toEqual({
        model: "text-embedding-3-small",
        input: "hello",
      });
    });

    it("passes dimensions when embeddingDims is explicitly set", async () => {
      const embedder = new AzureOpenAIEmbedder({
        ...baseConfig,
        embeddingDims: 1024,
      });

      await embedder.embed("hello");

      expect(mockEmbeddingsCreate).toHaveBeenCalledTimes(1);
      const callArgs = mockEmbeddingsCreate.mock.calls[0][0];
      expect(callArgs).toEqual({
        model: "text-embedding-3-small",
        input: "hello",
        dimensions: 1024,
      });
    });

    it("passes dimensions=1536 when embeddingDims is explicitly set to 1536", async () => {
      const embedder = new AzureOpenAIEmbedder({
        ...baseConfig,
        embeddingDims: 1536,
      });

      await embedder.embed("hello");

      const callArgs = mockEmbeddingsCreate.mock.calls[0][0];
      expect(callArgs).toHaveProperty("dimensions", 1536);
    });

    it("does NOT pass dimensions in embedBatch when embeddingDims is not set", async () => {
      mockEmbeddingsCreate.mockResolvedValue({
        data: [{ embedding: mockEmbedding }, { embedding: mockEmbedding }],
      });

      const embedder = new AzureOpenAIEmbedder(baseConfig);

      await embedder.embedBatch(["hello", "world"]);

      const callArgs = mockEmbeddingsCreate.mock.calls[0][0];
      expect(callArgs).not.toHaveProperty("dimensions");
    });

    it("passes dimensions in embedBatch when embeddingDims is explicitly set", async () => {
      mockEmbeddingsCreate.mockResolvedValue({
        data: [{ embedding: mockEmbedding }, { embedding: mockEmbedding }],
      });

      const embedder = new AzureOpenAIEmbedder({
        ...baseConfig,
        embeddingDims: 512,
      });

      await embedder.embedBatch(["hello", "world"]);

      const callArgs = mockEmbeddingsCreate.mock.calls[0][0];
      expect(callArgs).toEqual({
        model: "text-embedding-3-small",
        input: ["hello", "world"],
        dimensions: 512,
      });
    });
  });

  describe("basic functionality", () => {
    it("embed() returns the embedding vector", async () => {
      const embedder = new AzureOpenAIEmbedder(baseConfig);

      const result = await embedder.embed("hello");
      expect(result).toEqual(mockEmbedding);
    });

    it("embedBatch() returns vectors for multiple inputs", async () => {
      const batch = [
        [0.1, 0.2],
        [0.3, 0.4],
      ];
      mockEmbeddingsCreate.mockResolvedValue({
        data: batch.map((embedding) => ({ embedding })),
      });

      const embedder = new AzureOpenAIEmbedder(baseConfig);

      const result = await embedder.embedBatch(["text1", "text2"]);
      expect(result).toEqual(batch);
    });

    it("uses custom model when provided", async () => {
      const embedder = new AzureOpenAIEmbedder({
        ...baseConfig,
        model: "text-embedding-3-large",
      });

      await embedder.embed("hello");

      const callArgs = mockEmbeddingsCreate.mock.calls[0][0];
      expect(callArgs.model).toBe("text-embedding-3-large");
    });

    it("throws when API key is missing", () => {
      expect(() => {
        new AzureOpenAIEmbedder({
          modelProperties: { endpoint: "https://test.openai.azure.com" },
        });
      }).toThrow("Azure OpenAI requires both API key and endpoint");
    });

    it("throws when endpoint is missing", () => {
      expect(() => {
        new AzureOpenAIEmbedder({ apiKey: "test-key" });
      }).toThrow("Azure OpenAI requires both API key and endpoint");
    });
  });
});
