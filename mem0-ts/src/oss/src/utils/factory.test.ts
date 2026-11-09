jest.mock("zeroentropy", () => ({ ZeroEntropy: jest.fn() }));
jest.mock("@huggingface/transformers", () => ({
  AutoModelForSequenceClassification: { from_pretrained: jest.fn() },
  AutoTokenizer: { from_pretrained: jest.fn() },
}));

import { RerankerFactory } from "./factory";
import { CohereReranker } from "../rerankers/cohere";
import { LLMReranker } from "../rerankers/llm";
import { ZeroEntropyReranker } from "../rerankers/zeroentropy";
import { CrossEncoderReranker } from "../rerankers/cross_encoder";

describe("RerankerFactory", () => {
  const originalOpenAiKey = process.env.OPENAI_API_KEY;

  afterEach(() => {
    if (originalOpenAiKey === undefined) {
      delete process.env.OPENAI_API_KEY;
    } else {
      process.env.OPENAI_API_KEY = originalOpenAiKey;
    }
  });

  it("creates a CohereReranker for provider 'cohere'", () => {
    const reranker = RerankerFactory.create("cohere", { apiKey: "key" });
    expect(reranker).toBeInstanceOf(CohereReranker);
  });

  it("matches the provider name case-insensitively", () => {
    const reranker = RerankerFactory.create("Cohere", { apiKey: "key" });
    expect(reranker).toBeInstanceOf(CohereReranker);
  });

  it("creates a ZeroEntropyReranker for provider 'zero_entropy'", () => {
    const reranker = RerankerFactory.create("zero_entropy", {
      apiKey: "key",
    });
    expect(reranker).toBeInstanceOf(ZeroEntropyReranker);
  });

  it("creates a CrossEncoderReranker for provider 'sentence_transformer'", () => {
    const reranker = RerankerFactory.create("sentence_transformer", {});
    expect(reranker).toBeInstanceOf(CrossEncoderReranker);
  });

  it("creates a CrossEncoderReranker for provider 'huggingface'", () => {
    const reranker = RerankerFactory.create("huggingface", {});
    expect(reranker).toBeInstanceOf(CrossEncoderReranker);
  });

  it("creates an LLMReranker for provider 'llm_reranker', building a default openai LLM from top-level config", () => {
    const reranker = RerankerFactory.create("llm_reranker", {
      apiKey: "key",
    });
    expect(reranker).toBeInstanceOf(LLMReranker);
  });

  it("creates an LLMReranker that builds its own LLM from a nested config.llm", () => {
    const reranker = RerankerFactory.create("llm_reranker", {
      llm: { provider: "openai", config: { apiKey: "x" } },
    });
    expect(reranker).toBeInstanceOf(LLMReranker);
  });

  it("prefers the nested llm.provider over the top-level provider when building the llm_reranker's LLM", () => {
    // If the top-level `provider` were used instead of the nested one, this
    // would throw ("Unsupported LLM provider: not-a-real-provider").
    const reranker = RerankerFactory.create("llm_reranker", {
      provider: "not-a-real-provider",
      llm: { provider: "openai", config: { apiKey: "key" } },
    });
    expect(reranker).toBeInstanceOf(LLMReranker);
  });

  it("throws for the 'llm_reranker' provider when the default LLM has no API key available", () => {
    delete process.env.OPENAI_API_KEY;

    expect(() => RerankerFactory.create("llm_reranker", {})).toThrow();
  });

  it("throws for an unsupported provider", () => {
    expect(() => RerankerFactory.create("banana", {})).toThrow(
      /unsupported reranker provider/i,
    );
  });
});
