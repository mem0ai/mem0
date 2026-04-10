/// <reference types="jest" />
/**
 * OpenAI Embedder — unit tests (mocked OpenAI client).
 * Verifies that the `dimensions` parameter is only passed to the API
 * when the user explicitly configures `embeddingDims`.
 */

const mockEmbeddingsCreate = jest.fn();

jest.mock("openai", () => {
  return {
    __esModule: true,
    default: jest.fn().mockImplementation(() => ({
      embeddings: { create: mockEmbeddingsCreate },
    })),
  };
});

import { OpenAIEmbedder } from "../src/embeddings/openai";

const mockEmbedding = [0.1, 0.2, 0.3, 0.4, 0.5];

describe("OpenAIEmbedder (unit)", () => {
  beforeEach(() => {
    mockEmbeddingsCreate.mockReset();
    mockEmbeddingsCreate.mockResolvedValue({
      data: [{ embedding: mockEmbedding }],
    });
  });

  describe("dimensions parameter", () => {
    it("does NOT pass dimensions when embeddingDims is not set", async () => {
      const embedder = new OpenAIEmbedder({
        apiKey: "test-key",
      });

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
      const embedder = new OpenAIEmbedder({
        apiKey: "test-key",
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
      const embedder = new OpenAIEmbedder({
        apiKey: "test-key",
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

      const embedder = new OpenAIEmbedder({
        apiKey: "test-key",
      });

      await embedder.embedBatch(["hello", "world"]);

      const callArgs = mockEmbeddingsCreate.mock.calls[0][0];
      expect(callArgs).not.toHaveProperty("dimensions");
    });

    it("passes dimensions in embedBatch when embeddingDims is explicitly set", async () => {
      mockEmbeddingsCreate.mockResolvedValue({
        data: [{ embedding: mockEmbedding }, { embedding: mockEmbedding }],
      });

      const embedder = new OpenAIEmbedder({
        apiKey: "test-key",
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
      const embedder = new OpenAIEmbedder({
        apiKey: "test-key",
      });

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

      const embedder = new OpenAIEmbedder({
        apiKey: "test-key",
      });

      const result = await embedder.embedBatch(["text1", "text2"]);
      expect(result).toEqual(batch);
    });

    it("uses custom model when provided", async () => {
      const embedder = new OpenAIEmbedder({
        apiKey: "test-key",
        model: "text-embedding-3-large",
      });

      await embedder.embed("hello");

      const callArgs = mockEmbeddingsCreate.mock.calls[0][0];
      expect(callArgs.model).toBe("text-embedding-3-large");
    });
  });
});
