/// <reference types="jest" />
/**
 * Voyage AI Embedder — unit tests (mocked OpenAI-compatible client).
 */

import { VoyageAIEmbedder } from "../src/embeddings/voyage";
import { EmbedderFactory } from "../src/utils/factory";

const mockEmbedding = [0.1, 0.2, 0.3];
const mockCreate = jest.fn().mockResolvedValue({
  data: [{ index: 0, embedding: mockEmbedding }],
});
const mockOpenAIConstructor = jest.fn().mockImplementation(() => ({
  embeddings: { create: mockCreate },
}));

jest.mock("openai", () => ({
  __esModule: true,
  default: jest
    .fn()
    .mockImplementation((...args: unknown[]) => mockOpenAIConstructor(...args)),
}));

describe("VoyageAIEmbedder (unit)", () => {
  beforeEach(() => {
    mockCreate.mockClear();
    mockOpenAIConstructor.mockClear();
    delete process.env.VOYAGE_API_KEY;
  });

  it("defaults to the Voyage API base URL and voyage-3-large model", async () => {
    const embedder = new VoyageAIEmbedder({ apiKey: "voyage-test-key" });

    await embedder.embed("hello");

    expect(mockOpenAIConstructor).toHaveBeenCalledWith(
      expect.objectContaining({
        apiKey: "voyage-test-key",
        baseURL: "https://api.voyageai.com/v1",
      }),
    );
    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({ model: "voyage-3-large", input: "hello" }),
    );
  });

  it("embed() returns the first embedding vector", async () => {
    const embedder = new VoyageAIEmbedder({ apiKey: "k" });
    const result = await embedder.embed("text");
    expect(result).toEqual(mockEmbedding);
  });

  it("respects explicit model and baseURL overrides", async () => {
    const embedder = new VoyageAIEmbedder({
      apiKey: "k",
      model: "voyage-3-lite",
      baseURL: "https://proxy.example.com/v1",
    });

    await embedder.embed("x");

    expect(mockOpenAIConstructor).toHaveBeenCalledWith(
      expect.objectContaining({ baseURL: "https://proxy.example.com/v1" }),
    );
    expect(mockCreate.mock.calls[0][0].model).toBe("voyage-3-lite");
  });

  it("falls back to the VOYAGE_API_KEY environment variable", () => {
    process.env.VOYAGE_API_KEY = "env-voyage-key";
    new VoyageAIEmbedder({});
    expect(mockOpenAIConstructor).toHaveBeenCalledWith(
      expect.objectContaining({ apiKey: "env-voyage-key" }),
    );
  });

  it("throws a clear error when no API key is available", () => {
    expect(() => new VoyageAIEmbedder({})).toThrow(/VOYAGE_API_KEY/);
  });

  it("does not send OpenAI-specific dimensions/encoding params", async () => {
    const embedder = new VoyageAIEmbedder({ apiKey: "k", embeddingDims: 1024 });
    await embedder.embed("x");
    const payload = mockCreate.mock.calls[0][0];
    expect(payload).not.toHaveProperty("dimensions");
    expect(payload).not.toHaveProperty("encoding_format");
  });

  it("embedBatch() returns vectors ordered by index", async () => {
    mockCreate.mockResolvedValueOnce({
      data: [
        { index: 1, embedding: [2] },
        { index: 0, embedding: [1] },
      ],
    });
    const embedder = new VoyageAIEmbedder({ apiKey: "k" });
    const result = await embedder.embedBatch(["a", "b"]);
    expect(result).toEqual([[1], [2]]);
  });
});

describe("EmbedderFactory voyageai wiring", () => {
  it('creates a VoyageAIEmbedder for provider "voyageai"', () => {
    const embedder = EmbedderFactory.create("voyageai", { apiKey: "k" });
    expect(embedder).toBeInstanceOf(VoyageAIEmbedder);
  });
});
