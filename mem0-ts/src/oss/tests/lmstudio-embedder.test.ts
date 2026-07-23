/// <reference types="jest" />
/**
 * LM Studio Embedder — unit tests (mocked OpenAI).
 */

import OpenAI from "openai";
import { LMStudioEmbedder } from "../src/embeddings/lmstudio";

const mockEmbedding = [0.1, 0.2, 0.3, 0.4, 0.5];
const mockCreate = jest.fn().mockResolvedValue({
  data: [{ embedding: mockEmbedding }],
});
const MockOpenAI = OpenAI as unknown as jest.Mock;

jest.mock("openai", () => {
  return jest.fn().mockImplementation(() => ({
    embeddings: { create: mockCreate },
  }));
});

describe("LMStudioEmbedder (unit)", () => {
  const originalEnv = process.env.LMSTUDIO_BASE_URL;

  beforeEach(() => {
    mockCreate.mockClear();
    MockOpenAI.mockClear();
    delete process.env.LMSTUDIO_BASE_URL;
  });

  afterAll(() => {
    if (originalEnv === undefined) {
      delete process.env.LMSTUDIO_BASE_URL;
    } else {
      process.env.LMSTUDIO_BASE_URL = originalEnv;
    }
  });

  it("honors LMSTUDIO_BASE_URL when config baseURL is unset", () => {
    process.env.LMSTUDIO_BASE_URL = "http://remote-lms:1234/v1";
    new LMStudioEmbedder({ model: "nomic-embed-text" });
    expect(MockOpenAI).toHaveBeenCalledWith(
      expect.objectContaining({ baseURL: "http://remote-lms:1234/v1" }),
    );
  });

  it("prefers config baseURL over LMSTUDIO_BASE_URL", () => {
    process.env.LMSTUDIO_BASE_URL = "http://env-host:1234/v1";
    new LMStudioEmbedder({
      model: "nomic-embed-text",
      baseURL: "http://cfg-host:1234/v1",
    });
    expect(MockOpenAI).toHaveBeenCalledWith(
      expect.objectContaining({ baseURL: "http://cfg-host:1234/v1" }),
    );
  });

  it("defaults to localhost when config and env are unset", () => {
    new LMStudioEmbedder({ model: "nomic-embed-text" });
    expect(MockOpenAI).toHaveBeenCalledWith(
      expect.objectContaining({ baseURL: "http://localhost:1234/v1" }),
    );
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
