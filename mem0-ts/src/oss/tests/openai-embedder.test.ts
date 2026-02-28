/// <reference types="jest" />
import { OpenAIEmbedder } from "../src/embeddings/openai";

describe("OpenAIEmbedder", () => {
  it("should forward baseURL to OpenAI client", () => {
    const embedder = new OpenAIEmbedder({
      apiKey: "test-key",
      baseURL: "http://localhost:8080/v1",
      model: "test-model",
    });

    const openai = (embedder as any).openai;
    expect(openai.baseURL).toBe("http://localhost:8080/v1");
  });

  it("should use default baseURL when not specified", () => {
    const embedder = new OpenAIEmbedder({
      apiKey: "test-key",
    });

    const openai = (embedder as any).openai;
    expect(openai.baseURL).toBe("https://api.openai.com/v1");
  });
});
