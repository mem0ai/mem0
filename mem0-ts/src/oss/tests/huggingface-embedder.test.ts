/// <reference types="jest" />
/**
 * HuggingFace Embedder - unit tests (mocked InferenceClient).
 */

const mockFeatureExtraction = jest.fn();
const mockInferenceClient = jest.fn().mockImplementation(() => ({
  featureExtraction: mockFeatureExtraction,
}));

jest.mock("@huggingface/inference", () => ({
  InferenceClient: mockInferenceClient,
}));

import { HuggingFaceEmbedder } from "../src/embeddings/huggingface";

const mockEmbedding = [0.1, 0.2, 0.3, 0.4, 0.5];

describe("HuggingFaceEmbedder (unit)", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    jest.clearAllMocks();
    process.env = { ...originalEnv };
    delete process.env.HF_TOKEN;
    delete process.env.HUGGINGFACE_API_KEY;
    mockFeatureExtraction.mockResolvedValue(mockEmbedding);
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it("uses config apiKey and the default model", async () => {
    const embedder = new HuggingFaceEmbedder({
      apiKey: "hf-test-key",
    });

    await embedder.embed("hello");

    expect(mockInferenceClient).toHaveBeenCalledWith("hf-test-key");
    expect(mockFeatureExtraction).toHaveBeenCalledWith({
      model: "sentence-transformers/multi-qa-MiniLM-L6-cos-v1",
      inputs: "hello",
    });
  });

  it("falls back to HF_TOKEN when apiKey is not provided", () => {
    process.env.HF_TOKEN = "hf-env-token";

    new HuggingFaceEmbedder({});

    expect(mockInferenceClient).toHaveBeenCalledWith("hf-env-token");
  });

  it("passes model, endpointUrl, dimensions, and modelProperties", async () => {
    const embedder = new HuggingFaceEmbedder({
      apiKey: "hf-test-key",
      model: "BAAI/bge-small-en-v1.5",
      baseURL: "https://example.endpoints.huggingface.cloud",
      embeddingDims: 384,
      modelProperties: { provider: "hf-inference" },
    });

    await embedder.embed("hello");

    expect(mockFeatureExtraction).toHaveBeenCalledWith({
      model: "BAAI/bge-small-en-v1.5",
      inputs: "hello",
      endpointUrl: "https://example.endpoints.huggingface.cloud",
      dimensions: 384,
      provider: "hf-inference",
    });
  });

  it("unwraps single-item embedding responses", async () => {
    mockFeatureExtraction.mockResolvedValueOnce([mockEmbedding]);

    const embedder = new HuggingFaceEmbedder({ apiKey: "hf-test-key" });

    await expect(embedder.embed("hello")).resolves.toEqual(mockEmbedding);
  });

  it("embedBatch() returns vectors for multiple inputs", async () => {
    const batch = [
      [0.1, 0.2],
      [0.3, 0.4],
    ];
    mockFeatureExtraction.mockResolvedValueOnce(batch);

    const embedder = new HuggingFaceEmbedder({ apiKey: "hf-test-key" });

    const result = await embedder.embedBatch(["text1", "text2"]);

    expect(mockFeatureExtraction).toHaveBeenCalledWith({
      model: "sentence-transformers/multi-qa-MiniLM-L6-cos-v1",
      inputs: ["text1", "text2"],
    });
    expect(result).toEqual(batch);
  });

  it("embedBatch() returns an empty result for empty input without calling the API", async () => {
    const embedder = new HuggingFaceEmbedder({ apiKey: "hf-test-key" });

    await expect(embedder.embedBatch([])).resolves.toEqual([]);

    expect(mockFeatureExtraction).not.toHaveBeenCalled();
  });

  it("embedBatch() throws when provider returns fewer embeddings than texts", async () => {
    mockFeatureExtraction.mockResolvedValueOnce([[0.1, 0.2]]);

    const embedder = new HuggingFaceEmbedder({ apiKey: "hf-test-key" });

    await expect(embedder.embedBatch(["text1", "text2"])).rejects.toThrow(
      /returned 1 embeddings for 2 texts/,
    );
  });

  it("wraps API errors with a clear message", async () => {
    mockFeatureExtraction.mockRejectedValueOnce(new Error("Unauthorized"));

    const embedder = new HuggingFaceEmbedder({ apiKey: "bad-key" });

    await expect(embedder.embed("hello")).rejects.toThrow(
      "HuggingFace embedder failed: Unauthorized",
    );
  });

  it("throws for unsupported token-level feature extraction responses", async () => {
    mockFeatureExtraction.mockResolvedValueOnce([[[0.1, 0.2]]]);

    const embedder = new HuggingFaceEmbedder({ apiKey: "hf-test-key" });

    await expect(embedder.embed("hello")).rejects.toThrow(
      /unsupported embedding response/,
    );
  });
});
