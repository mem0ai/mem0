/// <reference types="jest" />

describe("Ollama Lazy Import", () => {
  describe("OllamaLLM", () => {
    it("should be importable without ollama package installed", async () => {
      // This test verifies that the module can be imported without throwing
      // The actual ollama import only happens when the class methods are called
      const { OllamaLLM } = await import("../src/oss/src/llms/ollama");
      expect(OllamaLLM).toBeDefined();
    });

    it("should instantiate without throwing", () => {
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const { OllamaLLM } = require("../src/oss/src/llms/ollama");
      const llm = new OllamaLLM({
        model: "llama3.1:8b",
        config: { url: "http://localhost:11434" },
      });
      expect(llm).toBeDefined();
    });
  });

  describe("OllamaEmbedder", () => {
    it("should be importable without ollama package installed", async () => {
      // This test verifies that the module can be imported without throwing
      const { OllamaEmbedder } = await import("../src/oss/src/embeddings/ollama");
      expect(OllamaEmbedder).toBeDefined();
    });

    it("should instantiate without throwing", () => {
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const { OllamaEmbedder } = require("../src/oss/src/embeddings/ollama");
      const embedder = new OllamaEmbedder({
        model: "nomic-embed-text:latest",
        url: "http://localhost:11434",
      });
      expect(embedder).toBeDefined();
    });
  });

  describe("Factory imports", () => {
    it("should import factory without requiring ollama", async () => {
      // The factory imports OllamaLLM and OllamaEmbedder, but since they use
      // dynamic imports, this should not throw even if ollama is not installed
      const { LLMFactory, EmbedderFactory } = await import(
        "../src/oss/src/utils/factory"
      );
      expect(LLMFactory).toBeDefined();
      expect(EmbedderFactory).toBeDefined();
    });

    it("should create non-ollama providers without ollama installed", () => {
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const { VectorStoreFactory } = require("../src/oss/src/utils/factory");
      const store = VectorStoreFactory.create("memory", {
        collectionName: "test",
        dimension: 1536,
      });
      expect(store).toBeDefined();
    });
  });
});
