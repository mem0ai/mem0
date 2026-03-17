/// <reference types="jest" />
import { OpenAILLM } from "../src/llms/openai";
import { OpenAIEmbedder } from "../src/embeddings/openai";
import { LLMConfig, EmbeddingConfig } from "../src/types";

describe("OpenAILLM Config Validation", () => {
  const originalConsoleWarn = console.warn;

  beforeEach(() => {
    console.warn = jest.fn();
  });

  afterEach(() => {
    console.warn = originalConsoleWarn;
  });

  it("should throw error when apiKey is missing", () => {
    expect(() => {
      new OpenAILLM({} as LLMConfig);
    }).toThrow("OpenAI LLM config validation failed: 'apiKey' is required.");
  });

  it("should throw error with helpful message when openaiApiKey is used instead of apiKey", () => {
    expect(() => {
      new OpenAILLM({ openaiApiKey: "test-key" } as unknown as LLMConfig);
    }).toThrow(
      "OpenAI LLM config validation failed: 'apiKey' is required. Did you mean 'apiKey' (not 'openaiApiKey')?"
    );
  });

  it("should warn when openaiApiKey is provided alongside apiKey", () => {
    new OpenAILLM({ apiKey: "test-key", openaiApiKey: "wrong-key" } as unknown as LLMConfig);
    expect(console.warn).toHaveBeenCalledWith(
      "Warning: 'openaiApiKey' is not a valid config key. Use 'apiKey' instead."
    );
  });

  it("should warn when baseUrl is provided", () => {
    new OpenAILLM({ apiKey: "test-key", baseUrl: "https://example.com" } as unknown as LLMConfig);
    expect(console.warn).toHaveBeenCalledWith(
      "Warning: 'baseUrl' is not a valid config key. Use 'baseURL' instead."
    );
  });

  it("should warn when url is provided without baseURL", () => {
    new OpenAILLM({ apiKey: "test-key", url: "https://example.com" } as unknown as LLMConfig);
    expect(console.warn).toHaveBeenCalledWith(
      "Warning: 'url' is not a valid config key. Use 'baseURL' instead."
    );
  });

  it("should succeed with valid apiKey", () => {
    const llm = new OpenAILLM({ apiKey: "test-key" } as LLMConfig);
    expect(llm).toBeDefined();
  });

  it("should succeed with valid apiKey and baseURL", () => {
    const llm = new OpenAILLM({ apiKey: "test-key", baseURL: "https://api.openai.com/v1" } as LLMConfig);
    expect(llm).toBeDefined();
  });
});

describe("OpenAIEmbedder Config Validation", () => {
  const originalConsoleWarn = console.warn;

  beforeEach(() => {
    console.warn = jest.fn();
  });

  afterEach(() => {
    console.warn = originalConsoleWarn;
  });

  it("should throw error when apiKey is missing", () => {
    expect(() => {
      new OpenAIEmbedder({} as EmbeddingConfig);
    }).toThrow("OpenAI Embedder config validation failed: 'apiKey' is required.");
  });

  it("should throw error with helpful message when openaiApiKey is used instead of apiKey", () => {
    expect(() => {
      new OpenAIEmbedder({ openaiApiKey: "test-key" } as unknown as EmbeddingConfig);
    }).toThrow(
      "OpenAI Embedder config validation failed: 'apiKey' is required. Did you mean 'apiKey' (not 'openaiApiKey')?"
    );
  });

  it("should warn when openaiApiKey is provided alongside apiKey", () => {
    new OpenAIEmbedder({ apiKey: "test-key", openaiApiKey: "wrong-key" } as unknown as EmbeddingConfig);
    expect(console.warn).toHaveBeenCalledWith(
      "Warning: 'openaiApiKey' is not a valid config key. Use 'apiKey' instead."
    );
  });

  it("should warn when baseUrl is provided", () => {
    new OpenAIEmbedder({ apiKey: "test-key", baseUrl: "https://example.com" } as unknown as EmbeddingConfig);
    expect(console.warn).toHaveBeenCalledWith(
      "Warning: 'baseUrl' is not a valid config key. Use 'baseURL' instead."
    );
  });

  it("should succeed with valid apiKey", () => {
    const embedder = new OpenAIEmbedder({ apiKey: "test-key" } as EmbeddingConfig);
    expect(embedder).toBeDefined();
  });

  it("should succeed with valid apiKey and baseURL", () => {
    const embedder = new OpenAIEmbedder({ apiKey: "test-key", baseURL: "https://api.openai.com/v1" } as EmbeddingConfig);
    expect(embedder).toBeDefined();
  });
});
