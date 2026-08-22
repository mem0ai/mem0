/// <reference types="jest" />
/**
 * LM Studio Embedder — unit tests (mocked OpenAI).
 */

import { LMStudioEmbedder } from "../src/embeddings/lmstudio";

const mockEmbedding = [0.1, 0.2, 0.3, 0.4, 0.5];
const mockCreate = jest.fn().mockResolvedValue({
  data: [{ embedding: mockEmbedding }],
});

let capturedConstructorArgs: any;

jest.mock("openai", () => {
  return jest.fn().mockImplementation((args: any) => {
    capturedConstructorArgs = args;
    return {
      embeddings: { create: mockCreate },
    };
  });
});

describe("LMStudioEmbedder (unit)", () => {
  beforeEach(() => {
    mockCreate.mockClear();
    capturedConstructorArgs = undefined;
    delete process.env.LMSTUDIO_BASE_URL;
  });

  afterEach(() => {
    delete process.env.LMSTUDIO_BASE_URL;
  });

  it("uses the default base URL when neither config nor env var is set", async () => {
    const embedder = new LMStudioEmbedder({ model: "test-model" });

    await embedder.embed("hello");

    expect(capturedConstructorArgs).toMatchObject({
      baseURL: "http://localhost:1234/v1",
    });
  });

  it("uses LMSTUDIO_BASE_URL when config does not provide a base URL", async () => {
    process.env.LMSTUDIO_BASE_URL = "http://example.test:5678/v1";

    const embedder = new LMStudioEmbedder({ model: "test-model" });

    await embedder.embed("hello");

    expect(capturedConstructorArgs).toMatchObject({
      baseURL: "http://example.test:5678/v1",
    });
  });

  it("prefers an explicit config baseURL over LMSTUDIO_BASE_URL", async () => {
    process.env.LMSTUDIO_BASE_URL = "http://example.test:5678/v1";

    const embedder = new LMStudioEmbedder({
      model: "test-model",
      baseURL: "http://config.test:9999/v1",
    });

    await embedder.embed("hello");

    expect(capturedConstructorArgs).toMatchObject({
      baseURL: "http://config.test:9999/v1",
    });
  });

  it("embed() calls OpenAI with encoding_format float and returns vector", async () => {
    const embedder = new LMStudioEmbedder({
      model: "nomic-embed-text-v1.5-GGUF",
      baseURL: "http://localhost:1234/v1",
    });

    const result = await embedder.embed("Sample text to embed.");

    expect(mockCreate).toHaveBeenCalledTimes(1);
    expect(mockCreate.mock.calls[0][0]).toEqual({
      model: "nomic-embed-text-v1.5-GGUF",
      input: "Sample text to embed.",
      encoding_format: "float",
    });
    expect(result).toEqual(mockEmbedding);
  });

  it("embed() normalizes newlines", async () => {
    const embedder = new LMStudioEmbedder({
      model: "test-model",
      baseURL: "http://localhost:1234/v1",
    });

    await embedder.embed("Line one\nLine two");

    expect(mockCreate.mock.calls[0][0].input).toBe("Line one Line two");
  });

  it("embed() wraps API errors with a clear message", async () => {
    mockCreate.mockRejectedValueOnce(new Error("Connection refused"));

    const embedder = new LMStudioEmbedder({
      model: "test-model",
      baseURL: "http://localhost:1234/v1",
    });

    await expect(embedder.embed("text")).rejects.toThrow(
      "LM Studio embedder failed: Connection refused",
    );
  });

  it("embedBatch() returns vectors for multiple inputs", async () => {
    const mockBatch = [
      [0.1, 0.2],
      [0.3, 0.4],
    ];
    mockCreate.mockResolvedValueOnce({
      data: [{ embedding: mockBatch[0] }, { embedding: mockBatch[1] }],
    });

    const embedder = new LMStudioEmbedder({
      model: "test-model",
      baseURL: "http://localhost:1234/v1",
    });

    const result = await embedder.embedBatch(["text1", "text2"]);

    expect(mockCreate).toHaveBeenCalledTimes(1);
    expect(mockCreate.mock.calls[0][0].input).toEqual(["text1", "text2"]);
    expect(result).toEqual(mockBatch);
  });
});
