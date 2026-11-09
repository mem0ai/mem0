import OpenAI from "openai";
import { VllmLLM } from "../llms/vllm";
import { LLMFactory } from "../utils/factory";

const createMock = jest.fn();

jest.mock("openai", () => {
  return jest.fn().mockImplementation(() => ({
    chat: {
      completions: {
        create: createMock,
      },
    },
  }));
});

const MockOpenAI = OpenAI as unknown as jest.Mock;

describe("VllmLLM", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    delete process.env.VLLM_API_KEY;
    delete process.env.VLLM_BASE_URL;
    createMock.mockResolvedValue({
      choices: [
        {
          message: {
            content: "hello",
            role: "assistant",
          },
        },
      ],
    });
  });

  it("uses vLLM defaults with a configured baseURL", async () => {
    const llm = new VllmLLM({ baseURL: "http://localhost:8000/v1" });

    await llm.generateChat([{ role: "user", content: "Hi" }]);

    expect(MockOpenAI).toHaveBeenCalledWith({
      apiKey: "vllm-api-key",
      baseURL: "http://localhost:8000/v1",
    });
    expect(createMock).toHaveBeenCalledWith({
      messages: [{ role: "user", content: "Hi" }],
      model: "Qwen/Qwen2.5-32B-Instruct",
    });
  });

  it("reads vLLM API settings from the environment", () => {
    process.env.VLLM_API_KEY = "env-key";
    process.env.VLLM_BASE_URL = "http://vllm.example/v1";

    new VllmLLM({});

    expect(MockOpenAI).toHaveBeenCalledWith({
      apiKey: "env-key",
      baseURL: "http://vllm.example/v1",
    });
  });

  it("accepts Python-style vllm_base_url configs", () => {
    new VllmLLM({ vllm_base_url: "http://localhost:8001/v1" });

    expect(MockOpenAI).toHaveBeenCalledWith({
      apiKey: "vllm-api-key",
      baseURL: "http://localhost:8001/v1",
    });
  });

  it("registers the vllm provider with LLMFactory", () => {
    const llm = LLMFactory.create("vllm", {
      baseURL: "http://localhost:8000/v1",
    });

    expect(llm).toBeInstanceOf(VllmLLM);
  });

  it("defaults to the local vLLM server when no baseURL is provided", () => {
    new VllmLLM({});

    expect(MockOpenAI).toHaveBeenCalledWith({
      apiKey: "vllm-api-key",
      baseURL: "http://localhost:8000/v1",
    });
  });

  it("uses VLLM_BASE_URL when config merging leaves baseURL unset", () => {
    process.env.VLLM_BASE_URL = "http://env-vllm.example/v1";

    new VllmLLM({ model: "Qwen/Qwen2.5-32B-Instruct" });

    expect(MockOpenAI).toHaveBeenCalledWith({
      apiKey: "vllm-api-key",
      baseURL: "http://env-vllm.example/v1",
    });
  });

  it("wraps OpenAI-compatible client errors with provider context", async () => {
    createMock.mockRejectedValueOnce(new Error("network down"));
    const llm = new VllmLLM({ baseURL: "http://localhost:8000/v1" });

    await expect(
      llm.generateResponse([{ role: "user", content: "Hi" }]),
    ).rejects.toThrow("vLLM LLM failed: network down");
  });
});
