/// <reference types="jest" />
import { TogetherEmbedder } from "../../src/embeddings/together";
import dotenv from "dotenv";

dotenv.config();

jest.setTimeout(30000); // Increase timeout to 30 seconds

describe("TogetherEmbedder", () => {
  describe("Constructor", () => {
    it("should throw error when API key is missing", () => {
      expect(() => {
        new TogetherEmbedder({});
      }).toThrow("Together AI requires an API key");
    });

    it("should use default model when not specified", () => {
      const embedder = new TogetherEmbedder({
        apiKey: "test-key",
      });
      expect(embedder).toBeDefined();
    });

    it("should use custom model when specified", () => {
      const embedder = new TogetherEmbedder({
        apiKey: "test-key",
        model: "custom-model",
      });
      expect(embedder).toBeDefined();
    });
  });

  describe("Embedding Operations", () => {
    // Skip these tests if no API key is provided
    const skipIfNoApiKey = process.env.TOGETHER_API_KEY ? it : it.skip;
    let embedder: TogetherEmbedder;

    beforeEach(() => {
      if (process.env.TOGETHER_API_KEY) {
        embedder = new TogetherEmbedder({
          apiKey: process.env.TOGETHER_API_KEY,
          model: "togethercomputer/m2-bert-80M-8k-retrieval",
        });
      }
    });

    skipIfNoApiKey("should embed a single text", async () => {
      const text = "Hello, this is a test sentence for embedding.";
      const embedding = await embedder.embed(text);

      expect(embedding).toBeDefined();
      expect(Array.isArray(embedding)).toBe(true);
      expect(embedding.length).toBeGreaterThan(0);
      expect(typeof embedding[0]).toBe("number");
    });

    skipIfNoApiKey("should embed multiple texts", async () => {
      const texts = [
        "First test sentence for embedding.",
        "Second test sentence for embedding.",
        "Third test sentence for embedding.",
      ];
      const embeddings = await embedder.embedBatch(texts);

      expect(embeddings).toBeDefined();
      expect(Array.isArray(embeddings)).toBe(true);
      expect(embeddings.length).toBe(texts.length);
      
      embeddings.forEach((embedding) => {
        expect(Array.isArray(embedding)).toBe(true);
        expect(embedding.length).toBeGreaterThan(0);
        expect(typeof embedding[0]).toBe("number");
      });
    });

    skipIfNoApiKey("should return consistent embedding dimensions", async () => {
      const text1 = "First test sentence.";
      const text2 = "Second test sentence.";
      
      const embedding1 = await embedder.embed(text1);
      const embedding2 = await embedder.embed(text2);

      expect(embedding1.length).toBe(embedding2.length);
    });
  });
}); 