const mockRerank = jest.fn();

jest.mock("cohere-ai", () => ({
  CohereClient: jest.fn().mockImplementation(() => ({
    rerank: mockRerank,
  })),
}));

import { CohereClient } from "cohere-ai";
import { CohereReranker } from "./cohere";

describe("CohereReranker", () => {
  beforeEach(() => {
    mockRerank.mockReset();
    (CohereClient as unknown as jest.Mock).mockClear();
  });

  it("throws when no API key is provided or configured", () => {
    const originalEnv = process.env.COHERE_API_KEY;
    delete process.env.COHERE_API_KEY;

    expect(() => new CohereReranker({})).toThrow(/Cohere API key is required/);

    if (originalEnv !== undefined) process.env.COHERE_API_KEY = originalEnv;
  });

  it("sends the query, documents, topN, and default model to Cohere", async () => {
    mockRerank.mockResolvedValue({ results: [] });
    const reranker = new CohereReranker({ apiKey: "key" });

    await reranker.rerank("capital of US?", ["a", "b", "c"], 2);

    expect(mockRerank).toHaveBeenCalledWith({
      model: "rerank-v3.5",
      query: "capital of US?",
      documents: ["a", "b", "c"],
      topN: 2,
      returnDocuments: false,
      maxChunksPerDoc: undefined,
    });
  });

  it("defaults topN to documents.length when neither the call nor config sets a top_k", async () => {
    mockRerank.mockResolvedValue({ results: [] });
    const reranker = new CohereReranker({ apiKey: "key" });

    await reranker.rerank("q", ["a", "b", "c"]);

    expect(mockRerank).toHaveBeenCalledWith(
      expect.objectContaining({ topN: 3 }),
    );
  });

  it("forwards returnDocuments and maxChunksPerDoc from config", async () => {
    mockRerank.mockResolvedValue({ results: [] });
    const reranker = new CohereReranker({
      apiKey: "key",
      returnDocuments: true,
      maxChunksPerDoc: 5,
    });

    await reranker.rerank("q", ["a"]);

    expect(mockRerank).toHaveBeenCalledWith(
      expect.objectContaining({ returnDocuments: true, maxChunksPerDoc: 5 }),
    );
  });

  it("returns Cohere's ranked results as {index, rerankScore}", async () => {
    mockRerank.mockResolvedValue({
      results: [
        { index: 2, relevanceScore: 0.9 },
        { index: 0, relevanceScore: 0.31 },
      ],
    });
    const reranker = new CohereReranker({ apiKey: "key" });

    const results = await reranker.rerank("q", ["x", "y", "z"]);

    expect(results).toEqual([
      { index: 2, rerankScore: 0.9 },
      { index: 0, rerankScore: 0.31 },
    ]);
  });

  it("uses a custom model when provided", async () => {
    mockRerank.mockResolvedValue({ results: [] });
    const reranker = new CohereReranker({
      apiKey: "key",
      model: "rerank-v4.0-pro",
    });

    await reranker.rerank("q", ["a"]);

    expect(mockRerank).toHaveBeenCalledWith(
      expect.objectContaining({ model: "rerank-v4.0-pro" }),
    );
  });

  it("returns an empty array without calling Cohere when there are no documents", async () => {
    const reranker = new CohereReranker({ apiKey: "key" });

    const results = await reranker.rerank("q", []);

    expect(results).toEqual([]);
    expect(mockRerank).not.toHaveBeenCalled();
  });

  it("falls back to the original order with rerankScore 0.0 when the Cohere API call fails", async () => {
    mockRerank.mockRejectedValue(new Error("cohere is down"));
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
    const reranker = new CohereReranker({ apiKey: "key" });

    const results = await reranker.rerank("q", ["a", "b", "c"]);

    expect(results).toEqual([
      { index: 0, rerankScore: 0.0 },
      { index: 1, rerankScore: 0.0 },
      { index: 2, rerankScore: 0.0 },
    ]);
    expect(warnSpy).toHaveBeenCalled();

    warnSpy.mockRestore();
  });

  it("slices the fallback results by topK when the Cohere API call fails", async () => {
    mockRerank.mockRejectedValue(new Error("cohere is down"));
    jest.spyOn(console, "warn").mockImplementation(() => {});
    const reranker = new CohereReranker({ apiKey: "key", topK: 2 });

    const results = await reranker.rerank("q", ["a", "b", "c"]);

    expect(results).toEqual([
      { index: 0, rerankScore: 0.0 },
      { index: 1, rerankScore: 0.0 },
    ]);

    (console.warn as jest.Mock).mockRestore();
  });
});
