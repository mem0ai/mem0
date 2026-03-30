/// <reference types="jest" />
/**
 * OpenAI Embedder — unit tests verifying dimensions param is passed correctly.
 */

import { OpenAIEmbedder } from "../src/embeddings/openai";

const mockEmbedding = [0.1, 0.2, 0.3, 0.4, 0.5];
const mockCreate = jest.fn().mockResolvedValue({
  data: [{ embedding: mockEmbedding }],
});

jest.mock("openai", () => {
  return {
    __esModule: true,
    default: jest.fn().mockImplementation(() => ({
      embeddings: { create: mockCreate },
    })),
  };
});

describe("OpenAIEmbedder (unit)", () => {
  beforeEach(() => {
    mockCreate.mockClear();
  });

  describe("dimensions parameter", () => {
    it("passes dimensions to API when embeddingDims is set", async () => {
      const embedder = new OpenAIEmbedder({
        apiKey: "test-key",
        model: "text-embedding-3-small",
        embeddingDims: 512,
      });

      await embedder.embed("test text");

      expect(mockCreate).toHaveBeenCalledWith(
        expect.objectContaining({ dimensions: 512 }),
      );
    });

    it("does NOT pass dimensions when embeddingDims is not set", async () => {
      const embedder = new OpenAIEmbedder({
        apiKey: "test-key",
        model: "text-embedding-3-small",
      });

      await embedder.embed("test text");

      const callArgs = mockCreate.mock.calls[0][0];
      expect(callArgs).not.toHaveProperty("dimensions");
    });

    it("passes dimensions in embedBatch when embeddingDims is set", async () => {
      mockCreate.mockResolvedValueOnce({
        data: [
          { embedding: mockEmbedding },
          { embedding: mockEmbedding },
        ],
      });

      const embedder = new OpenAIEmbedder({
        apiKey: "test-key",
        embeddingDims: 1536,
      });

      await embedder.embedBatch(["text1", "text2"]);

      expect(mockCreate).toHaveBeenCalledWith(
        expect.objectContaining({ dimensions: 1536 }),
      );
    });

    it("does NOT pass dimensions in embedBatch when embeddingDims is not set", async () => {
      mockCreate.mockResolvedValueOnce({
        data: [{ embedding: mockEmbedding }],
      });

      const embedder = new OpenAIEmbedder({
        apiKey: "test-key",
      });

      await embedder.embedBatch(["text1"]);

      const callArgs = mockCreate.mock.calls[0][0];
      expect(callArgs).not.toHaveProperty("dimensions");
    });
  });

  describe("basic functionality", () => {
    it("embed() returns the embedding vector", async () => {
      const embedder = new OpenAIEmbedder({ apiKey: "test-key" });

      const result = await embedder.embed("hello world");

      expect(result).toEqual(mockEmbedding);
      expect(mockCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          model: "text-embedding-3-small",
          input: "hello world",
        }),
      );
    });

    it("embedBatch() returns array of embeddings", async () => {
      mockCreate.mockResolvedValueOnce({
        data: [
          { embedding: [0.1, 0.2] },
          { embedding: [0.3, 0.4] },
        ],
      });

      const embedder = new OpenAIEmbedder({ apiKey: "test-key" });

      const result = await embedder.embedBatch(["a", "b"]);

      expect(result).toEqual([[0.1, 0.2], [0.3, 0.4]]);
      expect(mockCreate).toHaveBeenCalledWith(
        expect.objectContaining({ input: ["a", "b"] }),
      );
    });

    it("uses custom model when provided", async () => {
      const embedder = new OpenAIEmbedder({
        apiKey: "test-key",
        model: "text-embedding-v4",
      });

      await embedder.embed("test");

      expect(mockCreate).toHaveBeenCalledWith(
        expect.objectContaining({ model: "text-embedding-v4" }),
      );
    });
  });
});
