import { DeepSeekLLM } from "../llms/deepseek";
import { OpenAILLM } from "../llms/openai";

describe("DeepSeekLLM", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    jest.resetModules();
    process.env = { ...originalEnv };
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  it("should throw error when API key is not provided", () => {
    delete process.env.DEEPSEEK_API_KEY;
    expect(() => new DeepSeekLLM({} as any)).toThrow(
      "DeepSeek API key is required",
    );
  });

  it("should create an instance extending OpenAILLM", () => {
    process.env.DEEPSEEK_API_KEY = "test-api-key";
    const deepseek = new DeepSeekLLM({});
    expect(deepseek).toBeInstanceOf(OpenAILLM);
    expect(deepseek).toBeInstanceOf(DeepSeekLLM);
  });

  it("should use DEEPSEEK_API_KEY from environment", () => {
    delete process.env.DEEPSEEK_API_BASE;
    process.env.DEEPSEEK_API_KEY = "env-api-key";
    const deepseek = new DeepSeekLLM({});
    expect(deepseek).toBeInstanceOf(DeepSeekLLM);
  });

  it("should use default model deepseek-chat", () => {
    process.env.DEEPSEEK_API_KEY = "test-api-key";
    const deepseek = new DeepSeekLLM({ model: "deepseek-chat" });
    expect(deepseek).toBeInstanceOf(DeepSeekLLM);
  });

  it("should accept custom base URL", () => {
    process.env.DEEPSEEK_API_KEY = "test-api-key";
    const deepseek = new DeepSeekLLM({
      baseURL: "https://custom-proxy.example.com",
    });
    expect(deepseek).toBeInstanceOf(DeepSeekLLM);
  });

  it("should accept custom model", () => {
    process.env.DEEPSEEK_API_KEY = "test-api-key";
    const deepseek = new DeepSeekLLM({ model: "deepseek-coder" });
    expect(deepseek).toBeInstanceOf(DeepSeekLLM);
  });
});
