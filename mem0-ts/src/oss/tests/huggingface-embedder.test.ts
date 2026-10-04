/// <reference types="jest" />
/**
 * HuggingFace Embedder unit tests (mocked OpenAI client).
 * The TS provider targets a HuggingFace TEI / OpenAI-compatible inference
 * endpoint, so it reuses the `openai` client with a HuggingFace baseURL.
 * These tests verify the required base URL, request shape, and batch ordering.
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

import { HuggingFaceEmbedder } from "../src/embeddings/huggingface";

const mockEmbedding = [0.1, 0.2, 0.3, 0.4, 0.5];

describe("HuggingFaceEmbedder (unit)", () => {
  const OLD_ENV = process.env;

  beforeEach(() => {
    mockEmbeddingsCreate.mockReset();
    mockOpenAICtor.mockReset();
    mockEmbeddingsCreate.mockResolvedValue({
      data: [{ index: 0, embedding: mockEmbedding }],
    });
    process.env = { ...OLD_ENV };
    delete process.env.HUGGINGFACE_BASE_URL;
  });

  afterAll(() => {
    process.env = OLD_ENV;
  });

  describe("configuration", () => {
    it("throws when no inference endpoint is configured", () => {
      expect(() => new HuggingFaceEmbedder({ apiKey: "test-key" })).toThrow(
        /requires an inference endpoint/,
      );
    });

    it("uses huggingfaceBaseUrl and the default model", async () => {
      const embedder = new HuggingFaceEmbedder({
        apiKey: "test-key",
        huggingfaceBaseUrl: "http://localhost:8080/v1",
      });
      await embedder.embed("hello");

      expect(mockOpenAICtor.mock.calls[0][0]).toMatchObject({
        apiKey: "test-key",
        baseURL: "http://localhost:8080/v1",
      });
      const callArgs = mockEmbeddingsCreate.mock.calls[0][0];
      expect(callArgs).toEqual({ model: "tei", input: "hello" });
    });

    it("falls back to baseURL and honors a custom model", async () => {
      const embedder = new HuggingFaceEmbedder({
        baseURL: "https://tei.example.com/v1",
        model: "BAAI/bge-small-en-v1.5",
      });
      await embedder.embed("hello");

      expect(mockOpenAICtor.mock.calls[0][0]).toMatchObject({
        baseURL: "https://tei.example.com/v1",
      });
      expect(mockEmbeddingsCreate.mock.calls[0][0].model).toBe(
        "BAAI/bge-small-en-v1.5",
      );
    });

    it("reads HUGGINGFACE_BASE_URL from the environment", async () => {
      process.env.HUGGINGFACE_BASE_URL = "http://env-host:8080/v1";
      const embedder = new HuggingFaceEmbedder({ apiKey: "test-key" });
      await embedder.embed("hello");

      expect(mockOpenAICtor.mock.calls[0][0]).toMatchObject({
        baseURL: "http://env-host:8080/v1",
      });
    });

    it("never forwards a dimensions parameter", async () => {
      const embedder = new HuggingFaceEmbedder({
        huggingfaceBaseUrl: "http://localhost:8080/v1",
        embeddingDims: 384,
      });
      await embedder.embed("hello");

      expect(mockEmbeddingsCreate.mock.calls[0][0]).not.toHaveProperty(
        "dimensions",
      );
    });
  });

  describe("basic functionality", () => {
    const cfg = { huggingfaceBaseUrl: "http://localhost:8080/v1" };

    it("embed() returns the embedding vector", async () => {
      const embedder = new HuggingFaceEmbedder(cfg);
      expect(await embedder.embed("hello")).toEqual(mockEmbedding);
    });

    it("embedBatch() returns [] for empty input without calling the API", async () => {
      const embedder = new HuggingFaceEmbedder(cfg);
      expect(await embedder.embedBatch([])).toEqual([]);
      expect(mockEmbeddingsCreate).not.toHaveBeenCalled();
    });

    it("embedBatch() sorts results by index", async () => {
      mockEmbeddingsCreate.mockResolvedValue({
        data: [
          { index: 1, embedding: [0.3, 0.4] },
          { index: 0, embedding: [0.1, 0.2] },
        ],
      });
      const embedder = new HuggingFaceEmbedder(cfg);
      expect(await embedder.embedBatch(["a", "b"])).toEqual([
        [0.1, 0.2],
        [0.3, 0.4],
      ]);
    });

    it("embedBatch() throws when the count mismatches the input", async () => {
      mockEmbeddingsCreate.mockResolvedValue({
        data: [{ index: 0, embedding: [0.1, 0.2] }],
      });
      const embedder = new HuggingFaceEmbedder(cfg);
      await expect(embedder.embedBatch(["a", "b"])).rejects.toThrow(
        /returned 1 embeddings for 2 texts/,
      );
    });

    it("embed() throws when the endpoint returns no embeddings", async () => {
      mockEmbeddingsCreate.mockResolvedValue({ data: [] });
      const embedder = new HuggingFaceEmbedder(cfg);
      await expect(embedder.embed("hello")).rejects.toThrow(
        /returned no embeddings/,
      );
    });
  });
});
