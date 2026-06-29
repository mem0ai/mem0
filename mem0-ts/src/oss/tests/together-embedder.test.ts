/// <reference types="jest" />

const mockEmbeddingsCreate = jest.fn();
const mockOpenAI = jest.fn().mockImplementation(() => ({
  embeddings: { create: mockEmbeddingsCreate },
}));

jest.mock("openai", () => ({
  __esModule: true,
  default: mockOpenAI,
}));

import { TogetherEmbedder } from "../src/embeddings/together";

const mockEmbedding = [0.1, 0.2, 0.3];
const originalEnv = process.env;

describe("TogetherEmbedder (unit)", () => {
  beforeEach(() => {
    jest.resetModules();
    process.env = { ...originalEnv };
    delete process.env.TOGETHER_API_KEY;
    mockOpenAI.mockClear();
    mockEmbeddingsCreate.mockReset();
    mockEmbeddingsCreate.mockResolvedValue({
      data: [{ index: 0, embedding: mockEmbedding }],
    });
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it("uses Together defaults with an API key from config", async () => {
    const embedder = new TogetherEmbedder({ apiKey: "test-key" });

    await embedder.embed("hello");

    expect(mockOpenAI).toHaveBeenCalledWith({
      apiKey: "test-key",
      baseURL: "https://api.together.xyz/v1",
    });
    expect(mockEmbeddingsCreate).toHaveBeenCalledWith({
      model: "togethercomputer/m2-bert-80M-8k-retrieval",
      input: "hello",
      encoding_format: "float",
    });
  });

  it("uses TOGETHER_API_KEY when config apiKey is not provided", async () => {
    process.env.TOGETHER_API_KEY = "env-key";

    const embedder = new TogetherEmbedder({});

    await embedder.embed("hello");

    expect(mockOpenAI).toHaveBeenCalledWith({
      apiKey: "env-key",
      baseURL: "https://api.together.xyz/v1",
    });
  });

  it("supports custom model and baseURL without forwarding embeddingDims", async () => {
    const embedder = new TogetherEmbedder({
      apiKey: "test-key",
      model: "custom-together-embed",
      baseURL: "https://proxy.example.com/v1",
      embeddingDims: 512,
    });

    await embedder.embed("hello");

    expect(mockOpenAI).toHaveBeenCalledWith({
      apiKey: "test-key",
      baseURL: "https://proxy.example.com/v1",
    });
    expect(mockEmbeddingsCreate).toHaveBeenCalledWith({
      model: "custom-together-embed",
      input: "hello",
      encoding_format: "float",
    });
  });

  it("uses url as a baseURL fallback", async () => {
    const embedder = new TogetherEmbedder({
      apiKey: "test-key",
      url: "https://url-fallback.example.com/v1",
    });

    await embedder.embed("hello");

    expect(mockOpenAI).toHaveBeenCalledWith({
      apiKey: "test-key",
      baseURL: "https://url-fallback.example.com/v1",
    });
  });

  it("sorts batch embeddings by response index", async () => {
    mockEmbeddingsCreate.mockResolvedValueOnce({
      data: [
        { index: 1, embedding: [0.3, 0.4] },
        { index: 0, embedding: [0.1, 0.2] },
      ],
    });

    const embedder = new TogetherEmbedder({ apiKey: "test-key" });

    await expect(embedder.embedBatch(["first", "second"])).resolves.toEqual([
      [0.1, 0.2],
      [0.3, 0.4],
    ]);
  });

  it("throws when no API key is available", () => {
    expect(() => new TogetherEmbedder({})).toThrow(
      "Together API key is required",
    );
  });
});
