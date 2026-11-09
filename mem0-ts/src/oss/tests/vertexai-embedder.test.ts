/// <reference types="jest" />

const mockPredict = jest.fn();
const mockGetProjectId = jest.fn();
const mockClientConstructor = jest.fn();

jest.mock("@google-cloud/aiplatform", () => {
  return {
    __esModule: true,
    PredictionServiceClient: jest.fn().mockImplementation((...args) => {
      mockClientConstructor(...args);
      return {
        predict: mockPredict,
        getProjectId: mockGetProjectId,
      };
    }),
    helpers: {
      toValue: jest.fn().mockImplementation((val) => val),
      fromValue: jest.fn().mockImplementation((val) => val),
    },
  };
});

import { VertexAIEmbedder } from "../src/embeddings/vertexai";

const mockEmbedding = [0.1, 0.2, 0.3, 0.4];

/** Echoes one embedding back per instance in the request. */
function predictEchoingInstances() {
  return (req: { instances: unknown[] }) =>
    Promise.resolve([
      {
        predictions: req.instances.map(() => ({
          embeddings: { values: mockEmbedding },
        })),
      },
    ]);
}

describe("VertexAIEmbedder", () => {
  beforeEach(() => {
    mockPredict.mockReset();
    mockClientConstructor.mockReset();
    mockGetProjectId.mockReset();
    mockGetProjectId.mockResolvedValue("adc-project");
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

  describe("embedBatch() request sizing", () => {
    // gemini-embedding-001 (the default model) rejects any predict() call
    // carrying more than one input text, so the batch loop must degrade to one
    // request per text rather than the 250-instance chunk the older models take.
    it("sends one instance per request for gemini-embedding models", async () => {
      mockPredict.mockImplementation(predictEchoingInstances());
      const embedder = new VertexAIEmbedder({
        googleProjectId: "test-project",
      });

      const texts = ["a", "b", "c"];
      const result = await embedder.embedBatch(texts);

      expect(result).toEqual(texts.map(() => mockEmbedding));
      expect(mockPredict).toHaveBeenCalledTimes(3);
      for (const call of mockPredict.mock.calls) {
        expect(call[0].instances.length).toBe(1);
        // batch defaults to the "add" action -> RETRIEVAL_DOCUMENT
        expect(call[0].instances[0].task_type).toBe("RETRIEVAL_DOCUMENT");
        expect(call[0].parameters).toEqual({ outputDimensionality: 256 });
      }
      expect(
        mockPredict.mock.calls.map((c) => c[0].instances[0].content),
      ).toEqual(texts);
    });

    it("chunks at 250 instances for text-embedding models", async () => {
      mockPredict.mockImplementation(predictEchoingInstances());
      const embedder = new VertexAIEmbedder({
        googleProjectId: "test-project",
        model: "text-embedding-005",
      });

      const texts = Array.from({ length: 255 }, (_, i) => `text-${i}`);
      const result = await embedder.embedBatch(texts, "search");

      expect(result.length).toBe(255);
      expect(mockPredict).toHaveBeenCalledTimes(2);
      expect(mockPredict.mock.calls[0][0].instances.length).toBe(250);
      expect(mockPredict.mock.calls[0][0].instances[0].task_type).toBe(
        "RETRIEVAL_QUERY",
      );
      expect(mockPredict.mock.calls[1][0].instances.length).toBe(5);
    });

    it("rejects an unknown memory action", async () => {
      const embedder = new VertexAIEmbedder({
        googleProjectId: "test-project",
      });

      await expect(
        embedder.embedBatch(["a"], "delete" as unknown as "add"),
      ).rejects.toThrow("Invalid memory action: delete");
    });
  });

  describe("client initialization", () => {
    const PROJECT_ENV_VARS = [
      "GCP_PROJECT_ID",
      "GOOGLE_CLOUD_PROJECT",
      "GCLOUD_PROJECT",
    ];
    let savedEnv: Record<string, string | undefined>;

    beforeEach(() => {
      savedEnv = {};
      for (const key of PROJECT_ENV_VARS) {
        savedEnv[key] = process.env[key];
        delete process.env[key];
      }
    });

    afterEach(() => {
      for (const key of PROJECT_ENV_VARS) {
        if (savedEnv[key] === undefined) delete process.env[key];
        else process.env[key] = savedEnv[key];
      }
    });

    it("resolves the project ID from credentials when none is configured", async () => {
      const embedder = new VertexAIEmbedder({});

      await embedder.embed("hello");

      expect(mockGetProjectId).toHaveBeenCalledTimes(1);
      expect(mockPredict.mock.calls[0][0].endpoint).toBe(
        "projects/adc-project/locations/us-central1/publishers/google/models/gemini-embedding-001",
      );
    });

    it("surfaces a helpful error when no project ID can be resolved", async () => {
      mockGetProjectId.mockRejectedValue(
        new Error("Unable to detect a Project Id"),
      );
      const embedder = new VertexAIEmbedder({});

      await expect(embedder.embed("hello")).rejects.toThrow(
        "Vertex AI could not determine a Google Cloud project ID",
      );
    });

    it("builds one client for concurrent calls", async () => {
      const embedder = new VertexAIEmbedder({
        googleProjectId: "test-project",
      });

      await Promise.all([
        embedder.embed("a"),
        embedder.embed("b"),
        embedder.embed("c"),
      ]);

      expect(mockClientConstructor).toHaveBeenCalledTimes(1);
    });

    it("retries initialization after a failure", async () => {
      mockGetProjectId.mockRejectedValueOnce(new Error("transient"));
      const embedder = new VertexAIEmbedder({});

      await expect(embedder.embed("hello")).rejects.toThrow(
        "Vertex AI could not determine a Google Cloud project ID",
      );
      await expect(embedder.embed("hello")).resolves.toEqual(mockEmbedding);
    });
  });
});
