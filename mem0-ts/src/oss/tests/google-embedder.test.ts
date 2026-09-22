/// <reference types="jest" />
/**
 * Google Embedder — unit tests (mocked Google GenAI client).
 * Verifies that the `outputDimensionality` config is only passed to the API
 * when the user explicitly configures `embeddingDims`.
 */

const mockEmbedContent = jest.fn();

jest.mock("@google/genai", () => {
  return {
    __esModule: true,
    GoogleGenAI: jest.fn().mockImplementation(() => ({
      models: { embedContent: mockEmbedContent },
    })),
  };
});

import { GoogleEmbedder } from "../src/embeddings/google";

const mockEmbedding = [0.1, 0.2, 0.3, 0.4, 0.5];

describe("GoogleEmbedder (unit)", () => {
  beforeEach(() => {
    mockEmbedContent.mockReset();
    mockEmbedContent.mockResolvedValue({
      embeddings: [{ values: mockEmbedding }],
    });
  });

  describe("outputDimensionality parameter", () => {
    it("does NOT pass config when embeddingDims is not set", async () => {
      const embedder = new GoogleEmbedder({
        apiKey: "test-key",
      });

      await embedder.embed("hello");

      expect(mockEmbedContent).toHaveBeenCalledTimes(1);
      const callArgs = mockEmbedContent.mock.calls[0][0];
      expect(callArgs).not.toHaveProperty("config");
      expect(callArgs).toEqual({
        model: "gemini-embedding-001",
        contents: "hello",
      });
    });

    it("passes outputDimensionality when embeddingDims is explicitly set", async () => {
      const embedder = new GoogleEmbedder({
        apiKey: "test-key",
        embeddingDims: 768,
      });

      await embedder.embed("hello");

      expect(mockEmbedContent).toHaveBeenCalledTimes(1);
      const callArgs = mockEmbedContent.mock.calls[0][0];
      expect(callArgs).toEqual({
        model: "gemini-embedding-001",
        contents: "hello",
        config: { outputDimensionality: 768 },
      });
    });

    it("passes outputDimensionality=1536 when embeddingDims is explicitly set to 1536", async () => {
      const embedder = new GoogleEmbedder({
        apiKey: "test-key",
        embeddingDims: 1536,
      });

      await embedder.embed("hello");

      const callArgs = mockEmbedContent.mock.calls[0][0];
      expect(callArgs).toHaveProperty("config");
      expect(callArgs.config).toEqual({ outputDimensionality: 1536 });
    });

    it("does NOT pass config in embedBatch when embeddingDims is not set", async () => {
      mockEmbedContent.mockResolvedValue({
        embeddings: [{ values: mockEmbedding }, { values: mockEmbedding }],
      });

      const embedder = new GoogleEmbedder({
        apiKey: "test-key",
      });

      await embedder.embedBatch(["hello", "world"]);

      const callArgs = mockEmbedContent.mock.calls[0][0];
      expect(callArgs).not.toHaveProperty("config");
    });

    it("passes outputDimensionality in embedBatch when embeddingDims is explicitly set", async () => {
      mockEmbedContent.mockResolvedValue({
        embeddings: [{ values: mockEmbedding }, { values: mockEmbedding }],
      });

      const embedder = new GoogleEmbedder({
        apiKey: "test-key",
        embeddingDims: 512,
      });

      await embedder.embedBatch(["hello", "world"]);

      const callArgs = mockEmbedContent.mock.calls[0][0];
      expect(callArgs).toEqual({
        model: "gemini-embedding-001",
        contents: ["hello", "world"],
        config: { outputDimensionality: 512 },
      });
    });
  });

  describe("basic functionality", () => {
    it("embed() returns the embedding vector", async () => {
      const embedder = new GoogleEmbedder({
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
      mockEmbedContent.mockResolvedValue({
        embeddings: batch.map((values) => ({ values })),
      });

      const embedder = new GoogleEmbedder({
        apiKey: "test-key",
      });

      const result = await embedder.embedBatch(["text1", "text2"]);
      expect(result).toEqual(batch);
    });

    it("uses custom model when provided", async () => {
      const embedder = new GoogleEmbedder({
        apiKey: "test-key",
        model: "text-embedding-004",
      });

      await embedder.embed("hello");

      const callArgs = mockEmbedContent.mock.calls[0][0];
      expect(callArgs.model).toBe("text-embedding-004");
    });
  });
});
