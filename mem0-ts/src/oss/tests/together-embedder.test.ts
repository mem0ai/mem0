/// <reference types="jest" />
/**
 * Together Embedder — unit tests (mocked OpenAI client).
 * Together exposes an OpenAI-compatible embeddings endpoint, so the embedder
 * reuses the `openai` client with a Together baseURL. These tests verify the
 * default model / baseURL, request shape, and batch ordering.
 */

const mockEmbeddingsCreate = jest.fn();
const mockOpenAICtor = jest.fn();

jest.mock("openai", () => {
  return {
    __esModule: true,
    default: jest.fn().mockImplementation((opts: any) => {
      mockOpenAICtor(opts);
      return { embeddings: { create: mockEmbeddingsCreate } };
    }),
  };
});

import { TogetherEmbedder } from "../src/embeddings/together";

const mockEmbedding = [0.1, 0.2, 0.3, 0.4, 0.5];

describe("TogetherEmbedder (unit)", () => {
  beforeEach(() => {
    mockEmbeddingsCreate.mockReset();
    mockOpenAICtor.mockReset();
    mockEmbeddingsCreate.mockResolvedValue({
      data: [{ index: 0, embedding: mockEmbedding }],
    });
  });

  describe("configuration", () => {
    it("defaults to the Together baseURL and model", async () => {
      const embedder = new TogetherEmbedder({ apiKey: "test-key" });
      await embedder.embed("hello");

      expect(mockOpenAICtor).toHaveBeenCalledTimes(1);
      expect(mockOpenAICtor.mock.calls[0][0]).toMatchObject({
        apiKey: "test-key",
        baseURL: "https://api.together.xyz/v1",
      });

      const callArgs = mockEmbeddingsCreate.mock.calls[0][0];
      expect(callArgs).toEqual({
        model: "togethercomputer/m2-bert-80M-8k-retrieval",
        input: "hello",
      });
    });

    it("honors a custom model and baseURL", async () => {
      const embedder = new TogetherEmbedder({
        apiKey: "test-key",
        model: "BAAI/bge-large-en-v1.5",
        baseURL: "https://proxy.example.com/v1",
      });
      await embedder.embed("hello");

      expect(mockOpenAICtor.mock.calls[0][0]).toMatchObject({
        baseURL: "https://proxy.example.com/v1",
      });
      expect(mockEmbeddingsCreate.mock.calls[0][0].model).toBe(
        "BAAI/bge-large-en-v1.5",
      );
    });

    it("never forwards a dimensions parameter", async () => {
      const embedder = new TogetherEmbedder({
        apiKey: "test-key",
        embeddingDims: 768,
      });
      await embedder.embed("hello");

      const callArgs = mockEmbeddingsCreate.mock.calls[0][0];
      expect(callArgs).not.toHaveProperty("dimensions");
    });
  });

  describe("basic functionality", () => {
    it("embed() returns the embedding vector", async () => {
      const embedder = new TogetherEmbedder({ apiKey: "test-key" });
      const result = await embedder.embed("hello");
      expect(result).toEqual(mockEmbedding);
    });

    it("embedBatch() returns [] for empty input without calling the API", async () => {
      const embedder = new TogetherEmbedder({ apiKey: "test-key" });
      const result = await embedder.embedBatch([]);
      expect(result).toEqual([]);
      expect(mockEmbeddingsCreate).not.toHaveBeenCalled();
    });

    it("embedBatch() sorts results by index", async () => {
      mockEmbeddingsCreate.mockResolvedValue({
        data: [
          { index: 1, embedding: [0.3, 0.4] },
          { index: 0, embedding: [0.1, 0.2] },
        ],
      });

      const embedder = new TogetherEmbedder({ apiKey: "test-key" });
      const result = await embedder.embedBatch(["text1", "text2"]);
      expect(result).toEqual([
        [0.1, 0.2],
        [0.3, 0.4],
      ]);
    });

    it("embedBatch() throws when the count mismatches the input", async () => {
      mockEmbeddingsCreate.mockResolvedValue({
        data: [{ index: 0, embedding: [0.1, 0.2] }],
      });

      const embedder = new TogetherEmbedder({ apiKey: "test-key" });
      await expect(embedder.embedBatch(["a", "b"])).rejects.toThrow(
        /returned 1 embeddings for 2 texts/,
      );
    });
  });
});
