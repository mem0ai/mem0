/// <reference types="jest" />
import { LMStudioEmbedder } from "../src/embeddings/lmstudio";

// Mock OpenAI before importing LMStudioEmbedder (which instantiates it)
const mockEmbedding = [0.1, 0.2, 0.3, 0.4, 0.5];
const mockCreate = jest.fn().mockResolvedValue({
  data: [{ embedding: mockEmbedding }],
});

jest.mock("openai", () => {
  return jest.fn().mockImplementation(() => ({
    embeddings: {
      create: mockCreate,
    },
  }));
});

describe("LMStudioEmbedder", () => {
  beforeEach(() => {
    mockCreate.mockClear();
  });

  describe("embed", () => {
    it("should embed text and return vector", async () => {
      const embedder = new LMStudioEmbedder({
        model: "nomic-embed-text-v1.5-GGUF",
        baseURL: "http://localhost:1234/v1",
      });

      const result = await embedder.embed("Sample text to embed.");

      expect(mockCreate).toHaveBeenCalledTimes(1);
      const [apiParams] = mockCreate.mock.calls[0];
      expect(apiParams).toEqual({
        model: "nomic-embed-text-v1.5-GGUF",
        input: "Sample text to embed.",
      });
      expect(apiParams.model).toBe("nomic-embed-text-v1.5-GGUF");
      expect(apiParams.input).toBe("Sample text to embed.");
      expect(result).toEqual(mockEmbedding);
    });

    it("should normalize newlines in text", async () => {
      const embedder = new LMStudioEmbedder({
        model: "test-model",
        baseURL: "http://localhost:1234/v1",
      });

      await embedder.embed("Line one\nLine two");

      const [apiParams] = mockCreate.mock.calls[0];
      expect(apiParams.model).toBe("test-model");
      expect(apiParams.input).toBe("Line one Line two");
    });

    it("should wrap API errors with a clear message", async () => {
      mockCreate.mockRejectedValueOnce(new Error("Connection refused"));

      const embedder = new LMStudioEmbedder({
        model: "test-model",
        baseURL: "http://localhost:1234/v1",
      });

      await expect(embedder.embed("text")).rejects.toThrow(
        "LM Studio embedder failed: Connection refused",
      );
    });
  });

  describe("embedBatch", () => {
    it("should embed multiple texts", async () => {
      const mockBatchEmbedding = [
        [0.1, 0.2],
        [0.3, 0.4],
      ];
      mockCreate.mockResolvedValueOnce({
        data: [
          { embedding: mockBatchEmbedding[0] },
          { embedding: mockBatchEmbedding[1] },
        ],
      });

      const embedder = new LMStudioEmbedder({
        model: "test-model",
        baseURL: "http://localhost:1234/v1",
      });

      const result = await embedder.embedBatch(["text1", "text2"]);

      expect(mockCreate).toHaveBeenCalledTimes(1);
      const [apiParams] = mockCreate.mock.calls[0];
      expect(apiParams.model).toBe("test-model");
      expect(apiParams.input).toEqual(["text1", "text2"]);
      expect(Array.isArray(apiParams.input)).toBe(true);
      expect(result).toEqual(mockBatchEmbedding);
    });
  });
});
