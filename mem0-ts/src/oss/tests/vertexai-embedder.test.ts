/// <reference types="jest" />

const mockPredict = jest.fn();

jest.mock("@google-cloud/aiplatform", () => {
  return {
    __esModule: true,
    PredictionServiceClient: jest.fn().mockImplementation(() => ({
      predict: mockPredict,
    })),
    helpers: {
      toValue: jest.fn().mockImplementation((val) => val),
      fromValue: jest.fn().mockImplementation((val) => val),
    },
  };
});

import { VertexAIEmbedder } from "../src/embeddings/vertexai";

const mockEmbedding = [0.1, 0.2, 0.3, 0.4];

describe("VertexAIEmbedder", () => {
  beforeEach(() => {
    mockPredict.mockReset();
    mockPredict.mockResolvedValue([
      {
        predictions: [
          {
            embeddings: {
              values: mockEmbedding,
            },
          },
        ],
      },
    ]);
  });

  describe("basic functionality", () => {
    it("embed() returns the embedding vector", async () => {
      const embedder = new VertexAIEmbedder({
        googleProjectId: "test-project",
      });

      const result = await embedder.embed("hello");
      expect(result).toEqual(mockEmbedding);
      expect(mockPredict).toHaveBeenCalledTimes(1);

      const callArgs = mockPredict.mock.calls[0][0];
      expect(callArgs.endpoint).toBe(
        "projects/test-project/locations/us-central1/publishers/google/models/gemini-embedding-001",
      );
      // task_type belongs on the instance (snake_case), parameters carries
      // only outputDimensionality.
      expect(callArgs.instances).toEqual([
        { content: "hello", task_type: "SEMANTIC_SIMILARITY" },
      ]);
      expect(callArgs.parameters).toEqual({ outputDimensionality: 256 });
    });

    it("embed() with memory action search uses RETRIEVAL_QUERY", async () => {
      const embedder = new VertexAIEmbedder({
        googleProjectId: "test-project",
      });

      await embedder.embed("hello", "search");
      const callArgs = mockPredict.mock.calls[0][0];
      expect(callArgs.instances[0].task_type).toBe("RETRIEVAL_QUERY");
    });

    it("embed() with memory action add uses RETRIEVAL_DOCUMENT", async () => {
      const embedder = new VertexAIEmbedder({
        googleProjectId: "test-project",
      });

      await embedder.embed("hello", "add");
      const callArgs = mockPredict.mock.calls[0][0];
      expect(callArgs.instances[0].task_type).toBe("RETRIEVAL_DOCUMENT");
    });

    it("embedBatch() chunking and sequential loops", async () => {
      const embedder = new VertexAIEmbedder({
        googleProjectId: "test-project",
      });

      const texts = Array.from({ length: 255 }, (_, i) => `text-${i}`);

      mockPredict.mockImplementation((req) => {
        const predictions = req.instances.map(() => ({
          embeddings: {
            values: mockEmbedding,
          },
        }));
        return Promise.resolve([{ predictions }]);
      });

      const result = await embedder.embedBatch(texts);
      expect(result.length).toBe(255);
      expect(mockPredict).toHaveBeenCalledTimes(2);

      const firstCallArgs = mockPredict.mock.calls[0][0];
      expect(firstCallArgs.instances.length).toBe(250);
      // batch defaults to the "add" action -> RETRIEVAL_DOCUMENT on every instance
      expect(firstCallArgs.instances[0].task_type).toBe("RETRIEVAL_DOCUMENT");
      expect(firstCallArgs.parameters).toEqual({ outputDimensionality: 256 });

      const secondCallArgs = mockPredict.mock.calls[1][0];
      expect(secondCallArgs.instances.length).toBe(5);
    });

    it("throws error when predictions are empty", async () => {
      mockPredict.mockResolvedValue([{}]);
      const embedder = new VertexAIEmbedder({
        googleProjectId: "test-project",
      });

      await expect(embedder.embed("hello")).rejects.toThrow(
        "No predictions returned from Vertex AI",
      );
    });
  });
});
