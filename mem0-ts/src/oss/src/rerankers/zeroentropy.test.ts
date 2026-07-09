const mockRerank = jest.fn();

jest.mock("zeroentropy", () => ({
  ZeroEntropy: jest.fn().mockImplementation(() => ({
    models: { rerank: mockRerank },
  })),
}));

import { ZeroEntropy } from "zeroentropy";
import { ZeroEntropyReranker } from "./zeroentropy";

describe("ZeroEntropyReranker", () => {
  beforeEach(() => {
    mockRerank.mockReset();
    (ZeroEntropy as unknown as jest.Mock).mockClear();
  });

  it("throws when no API key is provided or configured", () => {
    const originalEnv = process.env.ZERO_ENTROPY_API_KEY;
    delete process.env.ZERO_ENTROPY_API_KEY;

    expect(() => new ZeroEntropyReranker({})).toThrow(
      /Zero Entropy API key is required/,
    );

    if (originalEnv !== undefined)
      process.env.ZERO_ENTROPY_API_KEY = originalEnv;
  });

  it("sends the query, documents, and default model to ZeroEntropy without a top_n parameter", async () => {
    mockRerank.mockResolvedValue({ results: [] });
    const reranker = new ZeroEntropyReranker({ apiKey: "key" });

    await reranker.rerank("capital of US?", ["a", "b", "c"], 2);

    expect(mockRerank).toHaveBeenCalledWith({
      model: "zerank-1",
      query: "capital of US?",
      documents: ["a", "b", "c"],
    });
  });

  it("maps ZeroEntropy's results (relevance_score) to {index, rerankScore}", async () => {
    mockRerank.mockResolvedValue({
      results: [
        { index: 2, relevance_score: 0.9 },
        { index: 0, relevance_score: 0.31 },
      ],
    });
    const reranker = new ZeroEntropyReranker({ apiKey: "key" });

    const results = await reranker.rerank("q", ["x", "y", "z"]);

    expect(results).toEqual([
      { index: 2, rerankScore: 0.9 },
      { index: 0, rerankScore: 0.31 },
    ]);
  });

  it("sorts unsorted API results by descending relevance score client-side", async () => {
    mockRerank.mockResolvedValue({
      results: [
        { index: 0, relevance_score: 0.2 },
        { index: 1, relevance_score: 0.9 },
        { index: 2, relevance_score: 0.5 },
      ],
    });
    const reranker = new ZeroEntropyReranker({ apiKey: "key" });

    const results = await reranker.rerank("q", ["a", "b", "c"]);

    expect(results.map((r) => r.index)).toEqual([1, 2, 0]);
    expect(results.map((r) => r.rerankScore)).toEqual([0.9, 0.5, 0.2]);
  });

  it("slices to topK client-side after sorting", async () => {
    mockRerank.mockResolvedValue({
      results: [
        { index: 0, relevance_score: 0.2 },
        { index: 1, relevance_score: 0.9 },
        { index: 2, relevance_score: 0.5 },
      ],
    });
    const reranker = new ZeroEntropyReranker({ apiKey: "key" });

    const results = await reranker.rerank("q", ["a", "b", "c"], 2);

    expect(results).toEqual([
      { index: 1, rerankScore: 0.9 },
      { index: 2, rerankScore: 0.5 },
    ]);
  });

  it("uses a custom model when provided", async () => {
    mockRerank.mockResolvedValue({ results: [] });
    const reranker = new ZeroEntropyReranker({
      apiKey: "key",
      model: "zerank-1-small",
    });

    await reranker.rerank("q", ["a"]);

    expect(mockRerank).toHaveBeenCalledWith(
      expect.objectContaining({ model: "zerank-1-small" }),
    );
  });

  it("returns an empty array without calling ZeroEntropy when there are no documents", async () => {
    const reranker = new ZeroEntropyReranker({ apiKey: "key" });

    const results = await reranker.rerank("q", []);

    expect(results).toEqual([]);
    expect(mockRerank).not.toHaveBeenCalled();
  });

  it("falls back to the original order with rerankScore 0.0 when the API call fails", async () => {
    mockRerank.mockRejectedValue(new Error("zero entropy is down"));
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
    const reranker = new ZeroEntropyReranker({ apiKey: "key" });

    const results = await reranker.rerank("q", ["a", "b", "c"]);

    expect(results).toEqual([
      { index: 0, rerankScore: 0.0 },
      { index: 1, rerankScore: 0.0 },
      { index: 2, rerankScore: 0.0 },
    ]);
    expect(warnSpy).toHaveBeenCalled();

    warnSpy.mockRestore();
  });
});
