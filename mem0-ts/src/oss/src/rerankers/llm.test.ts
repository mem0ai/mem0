import { LLM } from "../llms/base";
import { LLMReranker } from "./llm";

// Duplicated rather than imported from ./llm.ts so this test catches drift.
const EXPECTED_SYSTEM_PROMPT = `You are a relevance scoring assistant. Given a query and a document, score how relevant the document is to the query.

Score the relevance on a scale from 0.0 to 1.0, where:
- 1.0 = Perfectly relevant and directly answers the query
- 0.8-0.9 = Highly relevant with good information
- 0.6-0.7 = Moderately relevant with some useful information
- 0.4-0.5 = Slightly relevant with limited useful information
- 0.0-0.3 = Not relevant or no useful information

Respond with only a single numerical score between 0.0 and 1.0. Do not include any explanation or additional text.`;

/**
 * Fake LLM that scores a document by looking up the document text inside the
 * prompt. Test document tokens must be distinct and must not be substrings of
 * the prompt boilerplate (e.g. avoid "a"/"b"), or the lookup resolves the
 * wrong doc.
 */
function makeLLM(scoreByDoc: Record<string, string>): LLM {
  return {
    generateResponse: async (
      messages: Array<{ role: string; content: string }>,
    ) => {
      const prompt = messages.map((m) => m.content).join("\n");
      const doc = Object.keys(scoreByDoc).find((d) => prompt.includes(d));
      return doc ? scoreByDoc[doc] : "no number here";
    },
    generateChat: async () => ({ content: "", role: "assistant" }),
  };
}

describe("LLMReranker", () => {
  it("sorts documents by descending relevance score", async () => {
    const llm = makeLLM({ cats: "0.2", dogs: "0.9", fish: "0.5" });
    const reranker = new LLMReranker({}, llm);

    const results = await reranker.rerank("pets", ["cats", "dogs", "fish"]);

    expect(results.map((r) => r.index)).toEqual([1, 2, 0]);
    expect(results.map((r) => r.rerankScore)).toEqual([0.9, 0.5, 0.2]);
  });

  it("clamps scores to the [0, 1] range", async () => {
    const llm = makeLLM({ zebra: "1.5", walrus: "-0.3" });
    const reranker = new LLMReranker({}, llm);

    const results = await reranker.rerank("q", ["zebra", "walrus"]);

    const byIndex = new Map(results.map((r) => [r.index, r.rerankScore]));
    expect(byIndex.get(0)).toBe(1); // "zebra" 1.5 -> clamped to 1
    expect(byIndex.get(1)).toBe(0); // "walrus" -0.3 -> clamped to 0
  });

  it("truncates results to topK", async () => {
    const llm = makeLLM({ alpha: "0.1", bravo: "0.8", charlie: "0.5" });
    const reranker = new LLMReranker({}, llm);

    const results = await reranker.rerank(
      "q",
      ["alpha", "bravo", "charlie"],
      2,
    );

    expect(results).toHaveLength(2);
    expect(results.map((r) => r.index)).toEqual([1, 2]); // bravo(0.8), charlie(0.5)
  });

  it("falls back to config.topK when the rerank() call omits one", async () => {
    const llm = makeLLM({ alpha: "0.1", bravo: "0.8", charlie: "0.5" });
    const reranker = new LLMReranker({ topK: 1 }, llm);

    const results = await reranker.rerank("q", ["alpha", "bravo", "charlie"]);

    expect(results).toHaveLength(1);
    expect(results[0].index).toBe(1); // bravo(0.8)
  });

  it("falls back to a neutral score of 0.5 (not 0) when the LLM output has no number", async () => {
    const llm = makeLLM({ junk: "I cannot rate this" });
    const reranker = new LLMReranker({}, llm);

    const results = await reranker.rerank("q", ["junk"]);

    expect(results[0].rerankScore).toBe(0.5);
  });

  it("prefers a decimal match over an integer match when extracting the score", async () => {
    const llm = makeLLM({ item: "The score is 0.73 out of 1" });
    const reranker = new LLMReranker({}, llm);

    const results = await reranker.rerank("q", ["item"]);

    expect(results[0].rerankScore).toBe(0.73);
  });

  it("falls back to an integer match when no decimal is present", async () => {
    const llm = makeLLM({ item: "I'd say this is a solid 1" });
    const reranker = new LLMReranker({}, llm);

    const results = await reranker.rerank("q", ["item"]);

    expect(results[0].rerankScore).toBe(1);
  });

  it("assigns a neutral 0.5 score (not 0.0) when a per-document LLM call fails, and still returns that document", async () => {
    const llm: LLM = {
      generateResponse: jest
        .fn()
        .mockResolvedValueOnce("0.9") // scores "good"
        .mockRejectedValueOnce(new Error("rate limited")), // scores "bad"
      generateChat: async () => ({ content: "", role: "assistant" }),
    };
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
    const reranker = new LLMReranker({}, llm);

    const results = await reranker.rerank("q", ["good", "bad"]);

    expect(results).toHaveLength(2);
    const byIndex = new Map(results.map((r) => [r.index, r.rerankScore]));
    expect(byIndex.get(0)).toBe(0.9);
    expect(byIndex.get(1)).toBe(0.5);
    expect(warnSpy).toHaveBeenCalled();

    warnSpy.mockRestore();
  });

  it("sends the exact system prompt and a separate user message with the query and document", async () => {
    const generateResponse = jest.fn().mockResolvedValue("0.5");
    const llm: LLM = {
      generateResponse,
      generateChat: async () => ({ content: "", role: "assistant" }),
    };
    const reranker = new LLMReranker({}, llm);

    await reranker.rerank("what is the capital?", [
      "Paris is the capital of France.",
    ]);

    expect(generateResponse).toHaveBeenCalledWith([
      { role: "system", content: EXPECTED_SYSTEM_PROMPT },
      {
        role: "user",
        content:
          "Query: what is the capital?\n\nDocument: Paris is the capital of France.",
      },
    ]);
  });

  it("truncates the query and document to 4000 characters before sending", async () => {
    const generateResponse = jest.fn().mockResolvedValue("0.5");
    const llm: LLM = {
      generateResponse,
      generateChat: async () => ({ content: "", role: "assistant" }),
    };
    const reranker = new LLMReranker({}, llm);
    const longQuery = "q".repeat(5000);
    const longDoc = "d".repeat(5000);

    await reranker.rerank(longQuery, [longDoc]);

    const userMessage = generateResponse.mock.calls[0][0][1];
    const sentQuery = userMessage.content.match(/^Query: (q+)/)[1];
    const sentDoc = userMessage.content.match(/Document: (d+)/)[1];
    expect(sentQuery).toHaveLength(4000);
    expect(sentDoc).toHaveLength(4000);
  });

  it("throws when no LLM is provided", () => {
    expect(() => new LLMReranker({}, undefined as unknown as LLM)).toThrow();
  });
});
