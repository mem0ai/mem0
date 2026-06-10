import { createMem0, Mem0Provider } from "../src";
import { Mem0GenericLanguageModel } from "../src/mem0-generic-language-model";
import { Mem0ClassSelector } from "../src/mem0-provider-selector";

describe("V3 Provider Contract", () => {
  describe("Mem0Provider factory", () => {
    let provider: Mem0Provider;

    beforeEach(() => {
      provider = createMem0({
        provider: "openai",
        mem0ApiKey: "test-key",
        apiKey: "test-openai-key",
      });
    });

    it("should have specificationVersion v3", () => {
      expect(provider.specificationVersion).toBe("v3");
    });

    it("should expose languageModel, chat, and completion methods", () => {
      expect(typeof provider.languageModel).toBe("function");
      expect(typeof provider.chat).toBe("function");
      expect(typeof provider.completion).toBe("function");
    });

    it("should be callable as a function", () => {
      const model = provider("gpt-4o");
      expect(model).toBeDefined();
      expect(model.specificationVersion).toBe("v3");
    });

    it("should throw when called with new keyword", () => {
      expect(() => new (provider as any)("gpt-4o")).toThrow(
        "The Mem0 model function cannot be called with the new keyword."
      );
    });
  });

  describe("Mem0GenericLanguageModel V3 interface", () => {
    let model: Mem0GenericLanguageModel;

    beforeEach(() => {
      model = new Mem0GenericLanguageModel(
        "gpt-4o",
        { user_id: "test-user" },
        {
          provider: "openai",
          mem0ApiKey: "test-key",
          apiKey: "test-openai-key",
        }
      );
    });

    it("should implement specificationVersion v3", () => {
      expect(model.specificationVersion).toBe("v3");
    });

    it("should not have deprecated V2 properties", () => {
      expect((model as any).defaultObjectGenerationMode).toBeUndefined();
      expect((model as any).supportsImageUrls).toBeUndefined();
    });

    it("should have supportedUrls as a record", () => {
      expect(model.supportedUrls).toBeDefined();
      expect(typeof model.supportedUrls).toBe("object");
      expect(model.supportedUrls["*"]).toBeDefined();
      expect(Array.isArray(model.supportedUrls["*"])).toBe(true);
    });

    it("should have doGenerate and doStream methods", () => {
      expect(typeof model.doGenerate).toBe("function");
      expect(typeof model.doStream).toBe("function");
    });

    it("should have provider and modelId properties", () => {
      expect(model.provider).toBe("openai");
      expect(model.modelId).toBe("gpt-4o");
    });
  });

  describe("Mem0ClassSelector", () => {
    const supportedProviders = ["openai", "anthropic", "cohere", "groq", "google", "gemini"];

    it.each(supportedProviders)("should accept %s as a valid provider", (providerName) => {
      const selector = new Mem0ClassSelector(
        "test-model",
        { provider: providerName, apiKey: "test-key" }
      );
      expect(selector).toBeDefined();
    });

    it("should throw for unsupported provider", () => {
      expect(
        () => new Mem0ClassSelector("test-model", { provider: "invalid-provider" })
      ).toThrow("Model not supported: invalid-provider");
    });

    it("should create a V3 provider instance", () => {
      const selector = new Mem0ClassSelector(
        "gpt-4o",
        { provider: "openai", apiKey: "test-key" }
      );
      const provider = selector.createProvider();
      expect(provider.specificationVersion).toBe("v3");
      expect(typeof provider.doGenerate).toBe("function");
      expect(typeof provider.doStream).toBe("function");
    });
  });

  describe("Provider modelType routing", () => {
    it("should create chat model with chat modelType", () => {
      const provider = createMem0({
        provider: "openai",
        mem0ApiKey: "test-key",
        apiKey: "test-openai-key",
      });

      const chatModel = provider.chat("gpt-4o");
      expect(chatModel).toBeDefined();
      expect(chatModel.specificationVersion).toBe("v3");
      expect((chatModel as any).config.modelType).toBe("chat");
    });

    it("should create completion model with completion modelType", () => {
      const provider = createMem0({
        provider: "openai",
        mem0ApiKey: "test-key",
        apiKey: "test-openai-key",
      });

      const completionModel = provider.completion("gpt-4o");
      expect(completionModel).toBeDefined();
      expect(completionModel.specificationVersion).toBe("v3");
      expect((completionModel as any).config.modelType).toBe("completion");
    });
  });

  describe("Default baseURL", () => {
    it("should default to https, not http", () => {
      const provider = createMem0({
        provider: "openai",
        mem0ApiKey: "test-key",
      });
      const model = provider("gpt-4o") as Mem0GenericLanguageModel;
      expect((model as any).config.baseURL).toMatch(/^https:\/\//);
    });
  });
});
