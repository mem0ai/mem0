/// <reference types="jest" />
/**
 * Ollama Embedder — unit tests (mocked Ollama client).
 */

import { OllamaEmbedder } from "../src/embeddings/ollama";

const mockEmbedding = [0.1, 0.2, 0.3, 0.4, 0.5];
const mockEmbed = jest.fn().mockResolvedValue({
  model: "nomic-embed-text:latest",
  embeddings: [mockEmbedding],
});
const mockList = jest.fn().mockResolvedValue({
  models: [{ name: "nomic-embed-text:latest" }],
});
const mockPull = jest.fn().mockResolvedValue({});

jest.mock("ollama", () => ({
  Ollama: jest.fn().mockImplementation(() => ({
    embed: mockEmbed,
    list: mockList,
    pull: mockPull,
  })),
}));

describe("OllamaEmbedder (unit)", () => {
  beforeEach(() => {
    mockEmbed.mockClear();
    mockList.mockClear();
    mockPull.mockClear();
  });

  it("embed() calls ollama.embed with model and input, returns first embedding", async () => {
    const embedder = new OllamaEmbedder({
      model: "nomic-embed-text:latest",
    });

    const result = await embedder.embed("Sample text to embed.");

    expect(mockEmbed).toHaveBeenCalledTimes(1);
    expect(mockEmbed.mock.calls[0][0]).toEqual({
      model: "nomic-embed-text:latest",
      input: "Sample text to embed.",
    });
    expect(result).toEqual(mockEmbedding);
  });

  it("embed() coerces non-string input to JSON string", async () => {
    const embedder = new OllamaEmbedder({
      model: "nomic-embed-text:latest",
    });

    // Force a non-string through the type boundary
    await embedder.embed(42 as any);

    expect(mockEmbed.mock.calls[0][0].input).toBe("42");
  });

  it("embedBatch() returns vectors for multiple inputs", async () => {
    const embedder = new OllamaEmbedder({
      model: "nomic-embed-text:latest",
    });

    const result = await embedder.embedBatch(["text1", "text2"]);

    expect(mockEmbed).toHaveBeenCalledTimes(2);
    expect(result).toEqual([mockEmbedding, mockEmbedding]);
  });

  it("ensureModelExists() does not pull when model is already present", async () => {
    const embedder = new OllamaEmbedder({
      model: "nomic-embed-text:latest",
    });

    await embedder.embed("trigger ensureModelExists");

    expect(mockList).toHaveBeenCalled();
    expect(mockPull).not.toHaveBeenCalled();
  });

  it("ensureModelExists() pulls model when not found locally", async () => {
    mockList.mockResolvedValueOnce({ models: [] });

    const embedder = new OllamaEmbedder({
      model: "nomic-embed-text:latest",
    });

    await embedder.embed("trigger ensureModelExists");

    expect(mockPull).toHaveBeenCalledWith({ model: "nomic-embed-text:latest" });
  });

  it("ensureModelExists() normalizes model name with :latest tag", async () => {
    mockList.mockResolvedValue({
      models: [{ name: "nomic-embed-text:latest" }],
    });

    const embedder = new OllamaEmbedder({
      model: "nomic-embed-text",
    });

    await embedder.embed("trigger ensureModelExists");

    expect(mockPull).not.toHaveBeenCalled();
  });

  it("embed() throws when embeddings array is empty", async () => {
    mockEmbed.mockResolvedValueOnce({
      model: "nomic-embed-text:latest",
      embeddings: [],
    });

    const embedder = new OllamaEmbedder({
      model: "nomic-embed-text:latest",
    });

    await expect(embedder.embed("text")).rejects.toThrow(
      "Ollama embed() returned no embeddings",
    );
  });
});
