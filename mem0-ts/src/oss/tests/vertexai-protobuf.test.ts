/// <reference types="jest" />

/**
 * The sibling `vertexai-embedder.test.ts` stubs `helpers.toValue`/`fromValue`
 * as identity functions, so it never exercises the real protobuf `Value`
 * encode/decode path. Here we mock only `PredictionServiceClient` (no
 * network, no credentials) and keep the REAL `helpers`, so a malformed
 * instance shape or a broken decode actually fails.
 */

const mockPredict = jest.fn();
const mockGetProjectId = jest.fn();

jest.mock("@google-cloud/aiplatform", () => {
  const actual = jest.requireActual("@google-cloud/aiplatform");
  return {
    ...actual,
    __esModule: true,
    PredictionServiceClient: jest.fn().mockImplementation(() => ({
      predict: mockPredict,
      getProjectId: mockGetProjectId,
    })),
  };
});

import { VertexAIEmbedder } from "../src/embeddings/vertexai";
import { helpers } from "@google-cloud/aiplatform";

/** A `google.protobuf.Value` always carries `kind`+`structValue`/etc; a plain
 *  JS object never does. This is what "real encoding happened" looks like. */
function expectEncodedValue(value: unknown) {
  expect(value).toEqual(expect.objectContaining({ kind: expect.any(String) }));
}

describe("VertexAIEmbedder protobuf boundary (real helpers.toValue/fromValue)", () => {
  beforeEach(() => {
    mockPredict.mockReset();
    mockGetProjectId.mockReset();
    mockGetProjectId.mockResolvedValue("adc-project");
  });

  it("encodes the instance as a genuine protobuf Value carrying {content, task_type}", async () => {
    mockPredict.mockResolvedValue([
      {
        predictions: [helpers.toValue({ embeddings: { values: [0.1, 0.2] } })],
      },
    ]);
    const embedder = new VertexAIEmbedder({ googleProjectId: "test-project" });

    await embedder.embed("hello world", "search");

    const { instances } = mockPredict.mock.calls[0][0];
    expect(instances).toHaveLength(1);
    expectEncodedValue(instances[0]);

    // Decode with the REAL fromValue -- proves the encoded instance is
    // readable and matches exactly what Vertex expects on the wire.
    expect(helpers.fromValue(instances[0])).toEqual({
      content: "hello world",
      task_type: "RETRIEVAL_QUERY",
    });
  });

  it("encodes parameters as a genuine protobuf Value carrying {outputDimensionality}", async () => {
    mockPredict.mockResolvedValue([
      {
        predictions: [helpers.toValue({ embeddings: { values: [0.1] } })],
      },
    ]);
    const embedder = new VertexAIEmbedder({
      googleProjectId: "test-project",
      embeddingDims: 768,
    });

    await embedder.embed("hello");

    const { parameters } = mockPredict.mock.calls[0][0];
    expectEncodedValue(parameters);
    expect(helpers.fromValue(parameters)).toEqual({
      outputDimensionality: 768,
    });
  });

  it("decodes a real toValue()-encoded prediction back into the embedding array", async () => {
    const values = [0.11, -0.22, 0.33, 0.0];
    mockPredict.mockResolvedValue([
      {
        predictions: [helpers.toValue({ embeddings: { values } })],
      },
    ]);
    const embedder = new VertexAIEmbedder({ googleProjectId: "test-project" });

    const result = await embedder.embed("hello");

    expect(result).toEqual(values);
  });

  it("rejects a prediction that isn't a real encoded protobuf Value", async () => {
    // A raw JS object (what the identity-stubbed sibling test effectively
    // assumed `predict()` returns) is not a valid protobuf Value -- the real
    // fromValue() throws on it instead of silently passing it through.
    mockPredict.mockResolvedValue([
      { predictions: [{ embeddings: { values: [0.1, 0.2] } }] },
    ]);
    const embedder = new VertexAIEmbedder({ googleProjectId: "test-project" });

    await expect(embedder.embed("hello")).rejects.toThrow();
  });

  it("embedBatch() round-trips multiple real encoded predictions", async () => {
    const vectors = [
      [0.1, 0.2],
      [0.3, 0.4],
    ];
    mockPredict.mockImplementation(
      (req: { instances: unknown[] }) =>
        Promise.resolve([
          {
            predictions: req.instances.map((_, i) =>
              helpers.toValue({ embeddings: { values: vectors[i] } }),
            ),
          },
        ]) as any,
    );
    const embedder = new VertexAIEmbedder({
      googleProjectId: "test-project",
      model: "text-embedding-005",
    });

    const result = await embedder.embedBatch(["a", "b"]);

    expect(result).toEqual(vectors);
    const { instances } = mockPredict.mock.calls[0][0];
    expect(instances.map((i: unknown) => helpers.fromValue(i as any))).toEqual([
      { content: "a", task_type: "RETRIEVAL_DOCUMENT" },
      { content: "b", task_type: "RETRIEVAL_DOCUMENT" },
    ]);
  });
});
