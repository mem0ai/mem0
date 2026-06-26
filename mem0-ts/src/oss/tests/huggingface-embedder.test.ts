/// <reference types="jest" />

const mockFeatureExtraction = jest.fn();

jest.mock("@huggingface/inference", () => ({
  HfInference: jest.fn().mockImplementation(() => ({
    featureExtraction: mockFeatureExtraction,
  })),
}));

import { HuggingFaceEmbedder } from "../src/embeddings/huggingface";

const mockEmbedding = [0.1, 0.2, 0.3, 0.4, 0.5];

describe("HuggingFaceEmbedder (unit)", () => {
  beforeEach(() => {
    mockFeatureExtraction.mockReset();
    mockFeatureExtraction.mockResolvedValue(mockEmbedding);
  });

  describe("embed", () => {
    it("returns embedding vector for a single text", async () => {
      const embedder = new HuggingFaceEmbedder({
        apiKey: "hf-test-key",
      });

      const result = await embedder.embed("hello world");

      expect(result).toEqual(mockEmbedding);
      expect(mockFeatureExtraction).toHaveBeenCalledTimes(1);
      expect(mockFeatureExtraction).toHaveBeenCalledWith({
        model: "sentence-transformers/all-MiniLM-L6-v2",
        inputs: "hello world",
      });
    });

    it("uses default model when none is configured", async () => {
      const embedder = new HuggingFaceEmbedder({
        apiKey: "hf-test-key",
      });

      await embedder.embed("test");

      const callArgs = mockFeatureExtraction.mock.calls[0][0];
      expect(callArgs.model).toBe("sentence-transformers/all-MiniLM-L6-v2");
    });

    it("uses custom model when configured", async () => {
      const embedder = new HuggingFaceEmbedder({
        apiKey: "hf-test-key",
        model: "BAAI/bge-small-en-v1.5",
      });

      await embedder.embed("test");

      const callArgs = mockFeatureExtraction.mock.calls[0][0];
      expect(callArgs.model).toBe("BAAI/bge-small-en-v1.5");
    });

    it("handles nested array response from featureExtraction", async () => {
      mockFeatureExtraction.mockResolvedValue([[0.1, 0.2, 0.3]]);

      const embedder = new HuggingFaceEmbedder({
        apiKey: "hf-test-key",
      });

      const result = await embedder.embed("hello");
      expect(result).toEqual([0.1, 0.2, 0.3]);
    });

    it("throws on unexpected scalar response", async () => {
      mockFeatureExtraction.mockResolvedValue(42);

      const embedder = new HuggingFaceEmbedder({
        apiKey: "hf-test-key",
      });

      await expect(embedder.embed("hello")).rejects.toThrow(
        "Unexpected response format from HuggingFace featureExtraction",
      );
    });
  });

  describe("embedBatch", () => {
    it("returns array of embeddings for multiple texts", async () => {
      const embedder = new HuggingFaceEmbedder({
        apiKey: "hf-test-key",
      });

      const result = await embedder.embedBatch(["hello", "world", "test"]);

      expect(result).toHaveLength(3);
      expect(result[0]).toEqual(mockEmbedding);
      expect(result[1]).toEqual(mockEmbedding);
      expect(result[2]).toEqual(mockEmbedding);
    });

    it("returns empty array for empty input", async () => {
      const embedder = new HuggingFaceEmbedder({
        apiKey: "hf-test-key",
      });

      const result = await embedder.embedBatch([]);

      expect(result).toEqual([]);
      expect(mockFeatureExtraction).not.toHaveBeenCalled();
    });

    it("calls featureExtraction once per text", async () => {
      const embedder = new HuggingFaceEmbedder({
        apiKey: "hf-test-key",
      });

      await embedder.embedBatch(["text1", "text2", "text3"]);

      expect(mockFeatureExtraction).toHaveBeenCalledTimes(3);
      expect(mockFeatureExtraction).toHaveBeenCalledWith({
        model: "sentence-transformers/all-MiniLM-L6-v2",
        inputs: "text1",
      });
      expect(mockFeatureExtraction).toHaveBeenCalledWith({
        model: "sentence-transformers/all-MiniLM-L6-v2",
        inputs: "text2",
      });
      expect(mockFeatureExtraction).toHaveBeenCalledWith({
        model: "sentence-transformers/all-MiniLM-L6-v2",
        inputs: "text3",
      });
    });
  });
});
