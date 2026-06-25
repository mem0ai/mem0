/// <reference types="jest" />
/**
 * FastEmbed Embedder — unit tests (mocked FastEmbed client).
 * Verifies async generator handling for embed and embedBatch.
 */

const mockInit = jest.fn();
const mockEmbed = jest.fn();

jest.mock("fastembed", () => {
  return {
    __esModule: true,
    EmbeddingModel: {
      BGESmallENV15: "fast-bge-small-en-v1.5",
    },
    FlagEmbedding: {
      init: mockInit,
    },
  };
});

import { FastEmbedEmbedder } from "../src/embeddings/fastembed";

const mockVectorBatch = [
  [0.1, 0.2],
  [0.3, 0.4],
];
const mockEmbedding = [0.1, 0.2, 0.3];

const createEmbeddingGenerator = async function* (batches: number[][][]) {
  for (const batch of batches) {
    yield batch;
  }
};

describe("FastEmbedEmbedder (unit)", () => {
  beforeEach(() => {
    mockInit.mockReset();
    mockEmbed.mockReset();

    mockInit.mockResolvedValue({
      embed: mockEmbed,
    });
  });

  it("embed() initializes lazily, normalizes newlines, and returns the first vector", async () => {
    mockEmbed.mockReturnValue(
      createEmbeddingGenerator([[mockEmbedding], mockVectorBatch]),
    );
    const embedder = new FastEmbedEmbedder({
      model: "fast-bge-small-en-v1.5",
    });

    expect(mockInit).not.toHaveBeenCalled();

    const result = await embedder.embed("Example\ntext");

    expect(mockInit).toHaveBeenCalledTimes(1);
    expect(mockInit).toHaveBeenCalledWith({
      model: "fast-bge-small-en-v1.5",
    });
    expect(mockEmbed).toHaveBeenCalledTimes(1);
    expect(mockEmbed.mock.calls[0][0]).toEqual(["Example text"]);
    expect(result).toEqual(mockEmbedding);
  });

  it("embedBatch() consumes all async embedding batches and reuses the initialized model", async () => {
    mockEmbed.mockReturnValueOnce(createEmbeddingGenerator([[mockEmbedding]]));
    mockEmbed.mockReturnValueOnce(
      createEmbeddingGenerator([[mockEmbedding], mockVectorBatch]),
    );
    const embedder = new FastEmbedEmbedder({});

    await embedder.embed("warmup");
    const result = await embedder.embedBatch([
      "first text",
      "second text",
      "third text",
    ]);

    expect(mockEmbed).toHaveBeenCalledWith([
      "first text",
      "second text",
      "third text",
    ]);
    expect(mockInit).toHaveBeenCalledTimes(1);
    expect(result).toEqual([mockEmbedding, ...mockVectorBatch]);
  });

  it("embed() throws when FastEmbed yields no embeddings", async () => {
    mockEmbed.mockReturnValue(createEmbeddingGenerator([]));
    const embedder = new FastEmbedEmbedder({});

    await expect(embedder.embed("missing")).rejects.toThrow(
      "FastEmbed embed() returned no embeddings",
    );
  });
});
